"""
config.py
---------
Central configuration for the MENA Scientific Collaboration Pipeline.

All experiment-tuning variables live here.  Changing a value in this file
propagates automatically through the entire pipeline — no other file needs
to be edited.

Runtime mutation
----------------
``DELIBERATE_NP_THRESHOLD`` (and its alias ``DELIBERATE_N``) are updated in-place
by the calibration step in ``engine.orchestrator.ResearchPipeline``:

    config.DELIBERATE_NP_THRESHOLD = optimal_n
    config.DELIBERATE_N = optimal_n          # keep alias in sync

Usage
-----
    import config
    print(config.DELIBERATE_NP_THRESHOLD)
    print(config.WEIGHTS["SCALE"]["small"])
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
FIGURES_DIR: Path = OUTPUTS_DIR / "figures"
TABLES_DIR: Path = OUTPUTS_DIR / "tables"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_PATH: str = str(PROJECT_ROOT / "database.db")

TABLES: Dict[str, str] = {
    "articles": "articles",
    "countries": "countries",
    "subjects": "subjects",
    "baseline": "baseline",
}

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

CHECKPOINT_FILE: Path = RAW_DIR / "processed_log.txt"
PROCESSED_LOG_FILE: Path = RAW_DIR / "processed_log.txt"
MASTER_RAW_FILE: Path = RAW_DIR / "master.csv"
BASELINE_FILE: Path = RAW_DIR / "baseline.csv"
FINAL_DB_FILE: Path = RAW_DIR / "full_database_FINAL.csv"
MASTER_MAIN_FILE: Path = PROCESSED_DIR / "master_main.csv"
MASTER_COUNTRIES_FILE: Path = PROCESSED_DIR / "master_countries.csv"
MASTER_SUBJECTS_FILE: Path = PROCESSED_DIR / "master_subjects.csv"

# ---------------------------------------------------------------------------
# Experiment-tuning parameters  ← change here; propagates everywhere
# ---------------------------------------------------------------------------

# $n_p$ threshold: papers with more than this many distinct country
# affiliations are classified as mega-science consortia and receive the
# lower SCALE weight.  Updated at runtime by the elbow-detection step.
DELIBERATE_NP_THRESHOLD: int = 4

# Backward-compatibility alias — always kept in sync with DELIBERATE_NP_THRESHOLD.
DELIBERATE_N: int = DELIBERATE_NP_THRESHOLD

START_YEAR: int = 1990
END_YEAR: int = 2025
MIN_SALTON_THRESHOLD: float = 1e-9

# ---------------------------------------------------------------------------
# Thematic method  ← change here to switch H4 fractional-counting rule
# ---------------------------------------------------------------------------

# "proportional" : w_k = n_k / Σ n_k  (LaTeX-validated default)
# "fixed_0.5"    : mixed papers split 50/50 regardless of field counts
THEMATIC_METHOD: str = "proportional"

# ---------------------------------------------------------------------------
# Geopolitical event markers
# ---------------------------------------------------------------------------

GEOPOLITICAL_MARKERS: Dict[str, int] = {
    "OSLO_ACCORDS": 1993,
    "ISRAEL_JORDAN_PEACE": 1994,
    "SECOND_INTIFADA": 2000,
    "ARAB_SPRING": 2011,
    "ABRAHAM_ACCORDS": 2020,
}

# ---------------------------------------------------------------------------
# Geography & subject classification
# ---------------------------------------------------------------------------

COUNTRIES_LIST: List[str] = [
    "israel",
    "algeria",
    "bahrain",
    "egypt",
    "iran",
    "iraq",
    "jordan",
    "kuwait",
    "lebanon",
    "libya",
    "morocco",
    "oman",
    "palestine",
    "qatar",
    "saudi arabia",
    "syria",
    "tunisia",
    "turkey",
    "united arab emirates",
    "yemen",
]

NEUTRAL_FIELDS: List[str] = [
    "medicine",
    "physics and astronomy",
    "engineering",
    "chemistry",
    "mathematics",
]

# ---------------------------------------------------------------------------
# Collaboration weighting scheme
#
# SCALE  — graded tier penalty applied to C* per paper:
#            small  : nₚ ≤ DELIBERATE_NP_THRESHOLD  → 0.8  (deliberate signal)
#            cons   : nₚ >  DELIBERATE_NP_THRESHOLD  → 0.2  (mega-science tier)
# THEMATIC — how mixed-field papers distribute C* across subject categories:
#            see THEMATIC_METHOD above
# SCOPE  — geographic multiplier applied after SCALE weighting:
#            domestic : single-country papers       → 1.0  (identity)
#            intl     : multi-country papers        → 0.7  (mega-consortia discount)
# ---------------------------------------------------------------------------

WEIGHTS: Dict[str, Any] = {
    "SCALE": {
        "small": 0.8,   # nₚ ≤ DELIBERATE_NP_THRESHOLD  (canonical)
        "cons":  0.2,   # nₚ >  DELIBERATE_NP_THRESHOLD  (canonical)
        # Backward-compat aliases — same objects, different keys
        "small_group": 0.8,
        "consortia":   0.2,
    },
    "THEMATIC": {
        "method": THEMATIC_METHOD,
    },
    "SCOPE": {
        "domestic":    1.0,
        "intl":        0.7,   # canonical
        "international": 0.7, # backward-compat alias
    },
}

# ---------------------------------------------------------------------------
# Ensure output directories exist on import
# ---------------------------------------------------------------------------

for _d in [RAW_DIR, PROCESSED_DIR, OUTPUTS_DIR, FIGURES_DIR, TABLES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
