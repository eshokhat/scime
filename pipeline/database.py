"""
database.py
-----------
Normalises the enriched master CSV into relational tables and loads them
into a DuckDB database.

Pipeline
--------
master.csv
    -> master_main.csv      (articles: eid, title, doi, year, journal)
    -> master_countries.csv (eid x country, one row per affiliation)
    -> master_subjects.csv  (eid x subject, one row per subject area)
    + baseline.csv          (country, year, total_output)
    -> database.db          (DuckDB, four tables)
"""

import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger(__name__)


class DatabaseBuilder:
    """
    Reads the enriched master CSV, normalises it into relational tables,
    and loads everything into the DuckDB database.
    """

    def __init__(self):
        self.master_raw = config.MASTER_RAW_FILE
        self.baseline = config.BASELINE_FILE
        self.master_main = config.MASTER_MAIN_FILE
        self.master_countries = config.MASTER_COUNTRIES_FILE
        self.master_subjects = config.MASTER_SUBJECTS_FILE
        self.db_path = config.DB_PATH

    def normalise(self) -> dict:
        """Explode multi-valued columns into long-form relational tables."""
        logger.info("Reading master file: %s", self.master_raw)
        master = pd.read_csv(self.master_raw)

        # Countries — one row per country per paper
        countries_df = master[["eid", "all_countries"]].copy()
        countries_df["country"] = countries_df["all_countries"].str.split("; ")
        countries_df = countries_df.explode("country")
        countries_df["country"] = (
            countries_df["country"].str.strip().replace("Türkiye", "Turkey").str.lower()
        )
        countries_df = countries_df.drop(columns=["all_countries"]).dropna(
            subset=["country"]
        )

        # Subject areas — one row per subject per paper
        subjects_df = master[["eid", "subject_areas"]].copy()
        subjects_df["subject"] = subjects_df["subject_areas"].str.split("|")
        subjects_df = subjects_df.explode("subject")
        subjects_df["subject"] = subjects_df["subject"].str.strip().str.lower()
        subjects_df = subjects_df.drop(columns=["subject_areas"]).dropna(
            subset=["subject"]
        )

        # Main articles table
        master_clean = master.drop(
            columns=["all_countries", "subject_areas"], errors="ignore"
        )

        # Normalise baseline
        baseline = pd.read_csv(self.baseline)
        baseline["country"] = baseline["country"].str.strip().str.lower()

        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        countries_df.to_csv(self.master_countries, index=False)
        subjects_df.to_csv(self.master_subjects, index=False)
        master_clean.to_csv(self.master_main, index=False)
        baseline.to_csv(self.baseline, index=False)

        stats = {
            "articles": len(master_clean),
            "countries": len(countries_df),
            "subjects": len(subjects_df),
            "baseline": len(baseline),
        }
        for table, count in stats.items():
            logger.info("Normalised %-12s -> %d rows", table, count)
        return stats

    def load_to_db(self):
        """Create (or refresh) the DuckDB database from normalised CSVs."""
        logger.info("Connecting to DuckDB: %s", self.db_path)
        con = duckdb.connect(self.db_path)

        table_files = {
            "articles": str(self.master_main),
            "countries": str(self.master_countries),
            "subjects": str(self.master_subjects),
            "baseline": str(self.baseline),
        }
        for table_name, file_path in table_files.items():
            con.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} AS "
                f"SELECT * FROM read_csv_auto('{file_path}') LIMIT 0"
            )
            count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
            if count == 0:
                con.execute(
                    f"INSERT INTO {table_name} SELECT * FROM read_csv_auto('{file_path}')"
                )
                loaded = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
                logger.info("Loaded %-12s -> %d rows", table_name, loaded)
            else:
                logger.info(
                    "Table %-12s already populated (%d rows). Skipping.",
                    table_name,
                    count,
                )

        con.close()
        logger.info("Database ready: %s", self.db_path)

    def build(self):
        """Run normalisation then DB load end-to-end."""
        stats = self.normalise()
        self.load_to_db()
        return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    builder = DatabaseBuilder()
    builder.build()
