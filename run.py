"""
run.py
------
One-click research pipeline entry point.

Connects to the pre-built DuckDB database and runs all four hypothesis
stages, producing publication-quality figures and tables.

Usage
-----
    python run.py

To change the $n_p$ threshold or weights before running, edit ``config.py``:
    DELIBERATE_NP_THRESHOLD = 5           # change the threshold
    WEIGHTS["SCALE"]["small"] = 0.9       # change the small-group weight
    WEIGHTS["SCALE"]["cons"]  = 0.1       # change the consortia weight
"""

import logging
import sys
from pathlib import Path

import config
from engine.orchestrator import ResearchPipeline
from engine.reporter import Reporter

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            str(config.OUTPUTS_DIR / "pipeline.log"), encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("run")


def main() -> None:
    reporter = Reporter()
    pipeline = ResearchPipeline(reporter=reporter)

    reporter.section("MENA SCIENTIFIC COLLABORATION — ANALYSIS PIPELINE")

    # ── Calibration ────────────────────────────────────────────────────────────
    # Determines DELIBERATE_NP_THRESHOLD empirically via elbow detection.
    # All subsequent queries read config.DELIBERATE_NP_THRESHOLD at call time,
    # so setting it here propagates automatically to every hypothesis method.
    reporter.section("CALIBRATION: DELIBERATE COLLABORATION THRESHOLD (Nₚ)")
    _, optimal_n = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=7)
    logger.info("Threshold calibrated: DELIBERATE_NP_THRESHOLD = %d", optimal_n)

    # ── Step 1 ─────────────────────────────────────────────────────────────────
    reporter.section("STEP 1: AFFINITY NORMALISATION — CASE STUDIES")
    case_studies = [
        ("israel", "morocco"),
        ("israel", "united arab emirates"),
        ("israel", "egypt"),
        ("israel", "jordan"),
        ("israel", "bahrain"),
    ]
    for target, compare in case_studies:
        logger.info("Case study: %s – %s", target, compare)
        pipeline.execute_step1_normalization(target, compare)

    # ── H1 ─────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 1: THE MIRAGE (Structural Outsiderism)")
    pipeline.evaluate_h1_mirage()

    # ── H2a ────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 2a: ARAB SPRING IMPACT")
    pipeline.evaluate_h2a_destabilization()

    # ── H2b ────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 2b: ABRAHAM ACCORDS IMPACT")
    pipeline.evaluate_h2b_normalization()

    # ── H2c ────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 2c: STRUCTURAL BREAK DISCOVERY")
    pipeline.evaluate_h2c_break_detection(label="Full Region")

    def _is_israel_dyad(row):
        return "israel" in {row["c_i"], row["c_j"]}

    pipeline.evaluate_h2c_break_detection(
        subset_filter=_is_israel_dyad, label="Israel-Arab Only"
    )

    # ── H3 ─────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 3: TOPOLOGICAL PERIPHERALIZATION")
    pipeline.evaluate_h3_topology("israel")

    # ── H4 ─────────────────────────────────────────────────────────────────────
    reporter.section("HYPOTHESIS 4: THEMATIC COMPARTMENTALIZATION")
    pipeline.evaluate_h4_thematic_bias()

    # ── Metadata snapshot ──────────────────────────────────────────────────────
    try:
        import duckdb

        con = duckdb.connect(config.DB_PATH, read_only=True)
        total_papers = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        total_countries = con.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
        con.close()
    except Exception:
        total_papers = total_countries = "unavailable"

    from engine.models import PipelineConfig
    run_cfg = PipelineConfig.from_config()

    reporter.save_run_metadata(
        {
            "stage": "analysis",
            "pipeline_config": run_cfg.to_dict(),
            "total_papers": total_papers,
            "total_countries": total_countries,
            "hypotheses_tested": ["H1", "H2a", "H2b", "H2c", "H3", "H4"],
            "figures_dir": str(config.FIGURES_DIR),
            "tables_dir": str(config.TABLES_DIR),
        }
    )

    logger.info("Analysis complete. Figures → %s", config.FIGURES_DIR)
    print(f"\nFigures → {config.FIGURES_DIR}")
    print(f"Tables  → {config.TABLES_DIR}")


if __name__ == "__main__":
    main()
