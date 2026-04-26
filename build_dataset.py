"""
build_dataset.py
----------------
Data-ingestion pipeline entry point.

Stages
------
  1 - API Download  (ScopusScraper + BaselineCollector)
  2 - Enrichment    (enrich.py: join ASJC subject areas)
  3 - Database      (database.py: normalise + load DuckDB)

Usage
-----
    python build_dataset.py              # full pipeline
    python build_dataset.py --stage api
    python build_dataset.py --stage enrich
    python build_dataset.py --stage db
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

import config
from pipeline.api import ScopusScraper, update_baseline_csv
from pipeline.database import DatabaseBuilder
from pipeline.enrich import run_enrichment

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(config.OUTPUTS_DIR / "pipeline.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("build_dataset")


def run_stage_api(api_key: str):
    logger.info("=" * 70)
    logger.info("STAGE 1 - API DOWNLOAD")
    logger.info("=" * 70)
    countries = [c.title() for c in config.COUNTRIES_LIST]
    years = list(range(config.START_YEAR, config.END_YEAR + 1))
    logger.info("Collecting pairwise collaboration data ...")
    ScopusScraper(api_key, countries, years).run()
    logger.info("Collecting baseline totals per country ...")
    update_baseline_csv(api_key)
    logger.info("Stage 1 complete.")


def run_stage_enrich():
    logger.info("=" * 70)
    logger.info("STAGE 2 - ENRICHMENT")
    logger.info("=" * 70)
    if not config.FINAL_DB_FILE.exists():
        logger.error(
            "Raw article file not found: %s\n"
            "Run Stage 1 first: python build_dataset.py --stage api",
            config.FINAL_DB_FILE,
        )
        sys.exit(1)
    run_enrichment()
    logger.info("Stage 2 complete.")


def run_stage_db():
    logger.info("=" * 70)
    logger.info("STAGE 3 - DATABASE BUILD")
    logger.info("=" * 70)
    if not config.MASTER_RAW_FILE.exists():
        logger.error(
            "Enriched master file not found: %s\n"
            "Run Stage 2 first: python build_dataset.py --stage enrich",
            config.MASTER_RAW_FILE,
        )
        sys.exit(1)
    stats = DatabaseBuilder().build()
    logger.info("Database build complete. Row counts: %s", stats)
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="MENA Research - Data Ingestion Pipeline"
    )
    parser.add_argument(
        "--stage",
        choices=["api", "enrich", "db"],
        default=None,
        help="Run a single stage. Omit to run the full pipeline.",
    )
    args = parser.parse_args()
    api_key = os.environ.get("SCOPUS_API_KEY")

    if args.stage in (None, "api") and not api_key:
        logger.error(
            "SCOPUS_API_KEY is not set.\n"
            "Add it to %s/.env:  SCOPUS_API_KEY=your_key_here",
            PROJECT_ROOT,
        )
        sys.exit(1)

    t_start = time.perf_counter()
    logger.info("Pipeline started. Stage: %s", args.stage or "full")

    if args.stage == "api":
        run_stage_api(api_key)
    elif args.stage == "enrich":
        run_stage_enrich()
    elif args.stage == "db":
        run_stage_db()
    else:
        run_stage_api(api_key)
        run_stage_enrich()
        run_stage_db()

    logger.info("Pipeline finished in %.1f seconds.", time.perf_counter() - t_start)


if __name__ == "__main__":
    main()
