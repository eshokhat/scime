"""
engine_reporter.py
------------------
Academic-quality output formatter for the research pipeline.
Exports to console, LaTeX, CSV, and run_metadata.json.
"""

import json
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)


def _stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


class Reporter:
    """
    Centralised output handler: console + LaTeX + CSV + metadata.

    Usage
    -----
    reporter = Reporter()
    reporter.section("Hypothesis 1")
    reporter.stat_line("Mann-Whitney U", u_stat, p_val)
    reporter.table(df, label="h1_results", caption="Mann-Whitney results for H1")
    reporter.save_run_metadata({"total_papers": 42000})
    """

    def __init__(self):
        self.tables_dir = config.TABLES_DIR

    # --- Console ---

    def section(self, title: str, width: int = 95):
        bar = "=" * width
        print(f"\n{bar}\n{title}\n{bar}")

    def subsection(self, title: str, width: int = 95):
        print(f"\n--- {title} ---")
        print("-" * width)

    def stat_line(self, label: str, value, p_value: float = None):
        """
        Print a single statistic, optionally with p-value and significance stars.
        Example: Mann-Whitney U              : 12345.00   p = 0.000312  ***
        """
        line = f"  {label:<30}: {value}"
        if p_value is not None:
            line += f"   p = {p_value:.6f}  {_stars(p_value)}"
        print(line)

    def regression_summary(self, results, title: str):
        """Print a clean regression summary (linearmodels / statsmodels)."""
        self.subsection(title)
        print(f"  R2 (Within)  : {results.rsquared_within:.4f}")
        print(f"  Observations : {int(results.nobs)}")
        print(f"  Dyads        : {int(results.entity_info['total'])}")
        print()
        print(results.summary.tables[1])

    # --- DataFrame export ---

    def table(
        self, df: pd.DataFrame, label: str, caption: str = "", index: bool = True
    ):
        """
        Print to console, save as CSV and LaTeX in outputs/tables/.
        """
        print(f"\n[Table: {label}]")
        print(df.to_string())

        csv_path = self.tables_dir / f"{label}.csv"
        df.to_csv(csv_path, index=index)
        logger.info("Table saved -> %s", csv_path)

        tex_path = self.tables_dir / f"{label}.tex"
        latex_str = df.to_latex(
            index=index,
            caption=caption or label,
            label=f"tab:{label}",
            float_format="%.4f",
            escape=True,
        )
        tex_path.write_text(latex_str, encoding="utf-8")
        logger.info("LaTeX table saved -> %s", tex_path)

    def contingency_table(
        self,
        df: pd.DataFrame,
        odds_ratio: float,
        p_value: float,
        ci_low: float,
        ci_high: float,
    ):
        """Specialised printer for 2x2 contingency results (H4)."""
        self.subsection("Contingency Table")
        print(f"  {'Group':<18} | {'Neutral':>10} | {'Sensitive':>10}")
        print("  " + "-" * 45)
        for idx in df.index:
            print(
                f"  {idx:<18} | {df.loc[idx, 'neutral']:>10.1f} | {df.loc[idx, 'sensitive']:>10.1f}"
            )
        print()
        self.stat_line(
            "Odds Ratio", f"{odds_ratio:.4f} [95% CI: {ci_low:.2f} - {ci_high:.2f}]"
        )
        self.stat_line("Fisher p-value", "", p_value)

    # --- Run metadata ---

    def save_run_metadata(self, extra: dict = None):
        """Write outputs/run_metadata.json with timestamp and library versions."""
        try:
            import duckdb

            duckdb_version = duckdb.__version__
        except Exception:
            duckdb_version = "unknown"

        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "python_version": sys.version,
            "platform": platform.platform(),
            "pandas_version": pd.__version__,
            "duckdb_version": duckdb_version,
        }
        if extra:
            metadata.update(extra)

        out_path = config.OUTPUTS_DIR / "run_metadata.json"
        out_path.write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )
        logger.info("Run metadata saved -> %s", out_path)
        print(f"\n[Metadata] Run info saved -> {out_path}")
        return metadata
