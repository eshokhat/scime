"""
enrich.py
---------
Enriches the raw Scopus article export with subject-area classifications
by joining against the Scopus Source List (ASJC codes -> human-readable labels).

Input  : config.FINAL_DB_FILE        (full_database_FINAL.csv from api.py)
         config.RAW_DIR/scopus_source*.xlsx|csv  (Scopus Source List)
Output : config.MASTER_RAW_FILE      (master.csv with subject_areas column)
"""

import logging
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger(__name__)

ASJC_MAP = {
    "10": "Multidisciplinary",
    "11": "Agricultural & Biological Sciences",
    "12": "Arts and Humanities",
    "13": "Biochemistry, Genetics & Molecular Biology",
    "14": "Business, Management and Accounting",
    "15": "Chemical Engineering",
    "16": "Chemistry",
    "17": "Computer Science",
    "18": "Decision Sciences",
    "19": "Earth and Planetary Sciences",
    "20": "Economics, Econometrics and Finance",
    "21": "Energy",
    "22": "Engineering",
    "23": "Environmental Science",
    "24": "Immunology and Microbiology",
    "25": "Materials Science",
    "26": "Mathematics",
    "27": "Medicine",
    "28": "Neuroscience",
    "29": "Nursing",
    "30": "Pharmacology, Toxicology and Pharmaceutics",
    "31": "Physics and Astronomy",
    "32": "Psychology",
    "33": "Social Sciences",
    "34": "Veterinary",
    "35": "Dentistry",
    "36": "Health Professions",
}


def _get_category_from_code(code_str: str):
    if not code_str:
        return None
    code_str = str(code_str).strip()
    if len(code_str) < 2:
        return None
    return ASJC_MAP.get(code_str[:2])


def _clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def run_enrichment(
    source_file: Path = None,
    input_file: Path = config.FINAL_DB_FILE,
    output_file: Path = config.MASTER_RAW_FILE,
):
    """Join ASJC subject areas onto the raw article database."""

    # 1. Locate Scopus Sources file
    if source_file is None:
        candidates = [
            f
            for f in config.RAW_DIR.iterdir()
            if "scopus_source" in f.name.lower() and f.suffix in (".xlsx", ".csv")
        ]
        if not candidates:
            logger.error(
                "Scopus Sources file not found in %s. "
                "Download 'Scopus Source List' from https://www.scopus.com/sources",
                config.RAW_DIR,
            )
            return
        source_file = candidates[0]

    logger.info("Reading Scopus Sources file: %s", source_file)
    try:
        if source_file.suffix == ".csv":
            df_source = pd.read_csv(
                source_file,
                on_bad_lines="skip",
                encoding="utf-8",
                sep=None,
                engine="python",
            )
        else:
            df_source = pd.read_excel(source_file)
        df_source.columns = [str(c).strip() for c in df_source.columns]
    except Exception as exc:
        logger.error("Failed to read source file: %s", exc)
        return

    # 2. Locate title and ASJC columns
    title_col = None
    for col in df_source.columns:
        if col.lower() in {"source title", "title", "sourcetitle", "pubname"}:
            title_col = col
            break
    if title_col is None:
        title_col = df_source.columns[1]
        logger.warning(
            "Journal title column not found explicitly; using: %s", title_col
        )

    asjc_col = None
    for col in df_source.columns:
        if "asjc" in col.lower() and "code" in col.lower():
            asjc_col = col
            break
    if asjc_col is None:
        logger.error("ASJC code column not found. Use the full Scopus Source List.")
        return
    logger.info("ASJC code column: %s", asjc_col)

    # 3. Build journal -> subject-areas map
    logger.info("Translating ASJC codes to category labels ...")
    journal_map: dict = {}
    for _, row in df_source.iterrows():
        j_name = _clean_text(row[title_col])
        if not j_name:
            continue
        codes_raw = str(row[asjc_col])
        if codes_raw in {"nan", "None", ""}:
            continue
        codes_raw = codes_raw.replace(";", " ").replace(",", " ")
        subjects = set()
        for code in codes_raw.split():
            cat = _get_category_from_code(code.split(".")[0])
            if cat:
                subjects.add(cat)
        journal_map[j_name] = (
            "|".join(sorted(subjects)) if subjects else "Multidisciplinary"
        )

    logger.info("Journal map built: %d journals indexed.", len(journal_map))

    # 4. Apply to raw article database
    logger.info("Reading article database: %s", input_file)
    try:
        df_data = pd.read_csv(input_file)
    except FileNotFoundError:
        logger.error("Input file not found: %s", input_file)
        return

    df_data["subject_areas"] = df_data["journal"].apply(
        lambda j: journal_map.get(_clean_text(j), "Unknown")
    )
    filled = (df_data["subject_areas"] != "Unknown").sum()
    logger.info(
        "Subject areas assigned: %d / %d (%.1f%%)",
        filled,
        len(df_data),
        filled / len(df_data) * 100,
    )

    # 5. Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_data.to_csv(output_file, index=False)
    logger.info("Enriched dataset saved -> %s", output_file)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    run_enrichment()
