"""
engine/orchestrator.py
----------------------
High-level pipeline runner for the MENA Scientific Collaboration study.

``ResearchPipeline`` orchestrates all four hypothesis stages, delegating
data retrieval to ``NetworkAnalyst`` / ``ThematicAnalyst`` and visualisation
to ``ScientificVisualizer``.

Usage
-----
    from engine.orchestrator import ResearchPipeline
    from engine.reporter import Reporter

    reporter = Reporter()
    pipeline = ResearchPipeline(reporter=reporter)
    _, optimal_n = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=7)
    pipeline.evaluate_h1_mirage()
    ...
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .reporter import Reporter

import networkx as nx
import numpy as np
import pandas as pd
import pymannkendall as mk
import statsmodels.api as sm
from linearmodels.panel import PanelOLS
from networkx.algorithms.community import greedy_modularity_communities
from networkx.algorithms.community.quality import modularity
from scipy.stats import fisher_exact, mannwhitneyu

import config
from engine.processor import NetworkAnalyst, ThematicAnalyst
from engine.utils import elbow_detection, is_fractured_dyad
from engine.visuals import ScientificVisualizer

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """
    Orchestrates the full four-hypothesis analytical pipeline.

    Hypothesis stages
    -----------------
    H1  : The Mirage — mega-consortia inflate Israel's apparent ties.
    H2a : Arab Spring destabilisation (Two-Way FE DiD).
    H2b : Abraham Accords normalisation (Multi-Group DiD).
    H2c : Structural break discovery (rolling R² scan).
    H3  : Topological peripheralization (Eigenvector Centrality trend).
    H4  : Thematic compartmentalisation (Fisher's Exact Test).
    """

    def __init__(self, reporter: Optional["Reporter"] = None) -> None:
        self.analyst = NetworkAnalyst()
        self.visualizer = ScientificVisualizer()
        self.reporter = reporter
        self.normalized_states: set[str] = {
            "united arab emirates",
            "bahrain",
            "morocco",
            "egypt",
            "jordan",
        }
        logger.info("ResearchPipeline initialised.")

    # ------------------------------------------------------------------
    # Backward-compat property: old code/tests used w.analyzer, new
    # canonical name is w.analyst.  Both point to the same object.
    # ------------------------------------------------------------------

    @property
    def analyzer(self) -> NetworkAnalyst:
        return self.analyst

    @analyzer.setter
    def analyzer(self, value: NetworkAnalyst) -> None:
        self.analyst = value

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _report_panel_results(
        self,
        results,
        title: str,
        group_analysis_func: Callable,
    ) -> None:
        """Print a standardised panel-regression summary."""
        logger.info("%s — R²(within)=%.4f, N=%d", title,
                    results.rsquared_within, results.nobs)
        print(f"\n--- {title} ---")
        print(f"R-squared (Within): {results.rsquared_within:.4f}")
        print(f"Observations: {results.nobs} | Dyads: {results.entity_info['total']}")
        print("\n[DETAILED COEFFICIENTS]")
        print(results.summary.tables[1])
        group_analysis_func(results)
        print("-" * 95)

    def _run_did_panel(
        self,
        df: pd.DataFrame,
        predictor_cols: list[str],
        title: str,
        label: str,
        caption: str,
        group_col: str,
        event_year: int,
        plot_title: str,
        plot_filename: str,
        group_analysis_func: Callable = lambda _: None,
    ) -> None:
        """
        Fit a Two-Way Fixed Effects DiD model and export results.

        Shared implementation for H2a and H2b.
        """
        df_panel = df.set_index(["dyad_id", "year"])
        X = sm.add_constant(df_panel[predictor_cols])
        results = PanelOLS(
            df_panel["s_del"], X, entity_effects=True, time_effects=True
        ).fit(cov_type="clustered", cluster_entity=True)

        self._report_panel_results(results, title, group_analysis_func)

        if self.reporter:
            coef_df = pd.DataFrame(
                {
                    "coef": results.params,
                    "se": results.std_errors,
                    "t": results.tstats,
                    "p": results.pvalues,
                }
            )
            self.reporter.table(coef_df, label=label, caption=caption)

        self.visualizer.plot_did_comparison(
            df, group_col, event_year, plot_title, plot_filename
        )

    @staticmethod
    def _find_elbow(x_vals: list[int], y_vals: list[float]) -> int:
        """
        Elbow detection — delegates to ``engine.utils.elbow_detection``.

        Retained as a static method for backward compatibility with existing
        tests that call ``ScientificWorkflow._find_elbow``.
        """
        return elbow_detection(x_vals, y_vals)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def run_threshold_sensitivity_test(
        self, min_n: int = 2, max_n: int = 25
    ) -> tuple[pd.DataFrame, int]:
        """
        Empirically calibrate ``DELIBERATE_NP_THRESHOLD`` via elbow detection.

        For each candidate N in ``[min_n, max_n]``:
        1. Compute total C* for Israel-Involved and Non-Israel dyads.
        2. Compute the marginal growth rate of the Israel-Involved C* curve.
        3. Identify the elbow — point of diminishing returns.

        Updates ``config.DELIBERATE_NP_THRESHOLD`` and ``config.DELIBERATE_N``
        in-place, then clears the affinity cache so all subsequent queries use
        the calibrated threshold.

        Returns
        -------
        res_df : pd.DataFrame
            Full sensitivity table (one row per N).
        optimal_n : int
            Empirically calibrated threshold.
        """
        logger.info("Threshold sensitivity test: N = %d … %d", min_n, max_n)
        print(f"\n{'=' * 95}")
        print(f"THRESHOLD SENSITIVITY ANALYSIS  [N = {min_n} … {max_n}]")
        print(f"{'=' * 95}")

        rows = []
        for n in range(min_n, max_n + 1):
            try:
                df_n = self.analyst.fetch_sensitivity_stats(n)
            except Exception as exc:
                logger.error("Sensitivity stats failed at N=%d: %s", n, exc)
                continue

            isr_val = df_n[df_n["group_type"] == "Israel-Involved"]["c_star"].sum()
            arab_val = df_n[df_n["group_type"] == "Non-Israel"]["c_star"].sum()
            ratio = isr_val / arab_val if arab_val > 0 else 0.0
            rows.append(
                {
                    "n_threshold": n,
                    "israel_involved_c_star": isr_val,
                    "non_israel_c_star": arab_val,
                    "ratio_isr_non": ratio,
                }
            )

        if not rows:
            raise RuntimeError("No sensitivity rows computed — check database connection.")

        res_df = pd.DataFrame(rows)
        res_df["growth_isr"] = res_df["israel_involved_c_star"].pct_change().fillna(0)

        optimal_n = elbow_detection(
            res_df["n_threshold"].tolist(),
            res_df["israel_involved_c_star"].tolist(),
        )

        # Propagate to both canonical name and backward-compat alias.
        config.DELIBERATE_NP_THRESHOLD = optimal_n
        config.DELIBERATE_N = optimal_n
        self.analyst.clear_affinity_cache()

        logger.info("DELIBERATE_NP_THRESHOLD calibrated to N = %d", optimal_n)
        print(f"\n  Elbow detected at N = {optimal_n}")
        print(
            f"  config.DELIBERATE_NP_THRESHOLD updated: "
            f"all hypothesis queries will use nₚ ≤ {optimal_n}\n"
        )
        header = (
            f"  {'N':<5} | {'Isr-Involved C*':>16} | {'Non-Israel C*':>14} "
            f"| {'Ratio':>8} | {'Growth%':>8}"
        )
        print(header)
        print("  " + "-" * 62)
        for _, row in res_df.iterrows():
            marker = " ← optimal" if int(row["n_threshold"]) == optimal_n else ""
            print(
                f"  {int(row['n_threshold']):<5} | {row['israel_involved_c_star']:>16.4f} | "
                f"{row['non_israel_c_star']:>14.4f} | {row['ratio_isr_non']:>8.4f} | "
                f"{row['growth_isr'] * 100:>7.1f}%{marker}"
            )

        self.visualizer.plot_threshold_sensitivity(res_df, optimal_n)

        if self.reporter:
            self.reporter.table(
                res_df,
                label="threshold_sensitivity",
                caption=(
                    f"Threshold Sensitivity Analysis: Deliberate Collaboration Filter "
                    f"(N = {min_n}–{max_n}). Optimal elbow at N = {optimal_n}."
                ),
                index=False,
            )

        return res_df, optimal_n

    # ------------------------------------------------------------------
    # Step 1 — per-dyad affinity normalisation
    # ------------------------------------------------------------------

    def execute_step1_normalization(
        self, target: str, compare: str
    ) -> pd.DataFrame:
        """
        Compute and display per-dyad affinity for both Unrestricted and
        Deliberate Networks (Step 1 of the methodology).
        """
        logger.info("Step 1 normalization: %s – %s", target, compare)
        print(
            f"\n{'=' * 95}\n"
            f"STEP 1: NETWORK NORMALIZATION ({target.upper()} – {compare.upper()})\n"
            f"{'=' * 95}"
        )

        df_unr = self.analyst.calculate_dyad_affinity(target, compare, max_countries=None)
        df_del = self.analyst.calculate_dyad_affinity(
            target, compare, max_countries=config.DELIBERATE_N
        )

        merged = df_unr.merge(
            df_del[["year", "affinity_s"]], on="year", suffixes=("_unr", "_del")
        )

        self.visualizer.plot_affinity_trends(merged, target, compare)

        header = (
            f"{'Year':<6} | {'P_i':<8} | {'P_j':<8} | {'C* (Unr)':<10} "
            f"| {'S (Unr)':<12} | {'S (Del)':<12}"
        )
        print(header + "\n" + "-" * 95)
        for _, row in merged.iterrows():
            print(
                f"{int(row['year']):<6} | {int(row['p_i']):<8} | {int(row['p_j']):<8} | "
                f"{row['c_star']:<10.4f} | {row['affinity_s_unr']:<12.6f} | "
                f"{row['affinity_s_del']:<12.6f}"
            )

        return merged

    # ------------------------------------------------------------------
    # H1 — The Mirage
    # ------------------------------------------------------------------

    def evaluate_h1_mirage(self) -> None:
        """
        H1: Test whether Israel–adversary dyads rely disproportionately on
        mega-consortia (The Mirage Hypothesis).

        Statistical test: one-sided Mann-Whitney U (Fractured > Control).
        """
        logger.info("Evaluating H1: The Mirage")
        print(
            f"\n{'=' * 95}\nHYPOTHESIS 1: THE MIRAGE (Structural Outsiderism)\n{'=' * 95}"
        )
        df = self.analyst.fetch_regional_affinity_data()

        fractured_mask = df.apply(
            lambda r: is_fractured_dyad(r["c_i"], r["c_j"], self.normalized_states),
            axis=1,
        )
        isr_dist = df[fractured_mask]["delta_c"]
        control_dist = df[~fractured_mask]["delta_c"]

        u_stat, p_val = mannwhitneyu(isr_dist, control_dist, alternative="greater")

        self.visualizer.plot_h1_mirage(isr_dist.median(), control_dist.median())
        self.visualizer.plot_h1_mirage_2(df)

        print(f"  Fractured (Israel–Non-Normalized) Median ΔC : {isr_dist.median():.4f}")
        print(f"  Control (All Other) Median ΔC               : {control_dist.median():.4f}")
        print(f"  Fractured Dyads: {len(isr_dist)} | Control Dyads: {len(control_dist)}")
        print(f"  Mann-Whitney U: {u_stat:.1f} | P-value: {p_val:.6f}")
        logger.info("H1 — Mann-Whitney U=%.1f, p=%.6f", u_stat, p_val)

        if self.reporter:
            h1_df = pd.DataFrame(
                [
                    {
                        "group": "Fractured (Israel–Non-Normalized)",
                        "median_delta_c": round(isr_dist.median(), 6),
                        "n_dyads": len(isr_dist),
                        "mann_whitney_u": round(u_stat, 2),
                        "p_value": round(p_val, 6),
                    },
                    {
                        "group": "Control",
                        "median_delta_c": round(control_dist.median(), 6),
                        "n_dyads": len(control_dist),
                        "mann_whitney_u": "",
                        "p_value": "",
                    },
                ]
            )
            self.reporter.table(
                h1_df,
                label="h1_mann_whitney",
                caption="H1: Mega-Science Reliance — Mann-Whitney U Test Results",
                index=False,
            )

    # ------------------------------------------------------------------
    # H2a — Arab Spring
    # ------------------------------------------------------------------

    def evaluate_h2a_destabilization(self) -> None:
        """
        H2a: Causal impact of the Arab Spring via Two-Way FE DiD.

        Model: S_ij,t = β₀ + β₁(Destabilized×Post2011) + β₂(Israel×Post2011)
                        + γ_ij + τ_t + ε_ij,t
        """
        logger.info("Evaluating H2a: Arab Spring DiD")
        print(f"\n{'=' * 95}\nHYPOTHESIS 2a: ARAB SPRING IMPACT\n{'=' * 95}")
        df = self.analyst.format_did_panel_data()

        def _group_summary(res) -> None:
            try:
                wald = res.wald_test(formula="destab_post = israel_post")
                print(f"\n  Wald Test (Destab vs Israel): p = {wald.pval:.4f}")
                logger.info("H2a Wald test p=%.4f", wald.pval)
            except Exception:
                pass

        self._run_did_panel(
            df=df,
            predictor_cols=["destab_post", "israel_post"],
            title="H2a: Arab Spring — Two-Way FE DiD",
            label="h2a_regression",
            caption="H2a: Arab Spring Impact — Panel OLS Coefficients",
            group_col="h2a_group",
            event_year=config.GEOPOLITICAL_MARKERS["ARAB_SPRING"],
            plot_title="H2a: Arab Spring Impact Analysis",
            plot_filename="h2a_did.png",
            group_analysis_func=_group_summary,
        )

    # ------------------------------------------------------------------
    # H2b — Abraham Accords
    # ------------------------------------------------------------------

    def evaluate_h2b_normalization(self) -> None:
        """
        H2b: Impact of the Abraham Accords via Multi-Group DiD.

        Model: S_ij,t = β₀ + β₁(Norm×Post2020) + β₂(NonNorm×Post2020)
                        + γ_ij + τ_t + ε_ij,t
        """
        logger.info("Evaluating H2b: Abraham Accords DiD")
        print(f"\n{'=' * 95}\nHYPOTHESIS 2b: ABRAHAM ACCORDS IMPACT\n{'=' * 95}")
        df = self.analyst.prepare_h2b_dataset()

        self._run_did_panel(
            df=df,
            predictor_cols=["norm_post", "nonnorm_post"],
            title="H2b: Abraham Accords — Two-Way FE DiD",
            label="h2b_regression",
            caption="H2b: Abraham Accords Impact — Panel OLS Coefficients",
            group_col="h2b_group",
            event_year=config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"],
            plot_title="H2b: Abraham Accords Impact Analysis",
            plot_filename="h2b_did.png",
        )

    # ------------------------------------------------------------------
    # H2c — Structural break discovery
    # ------------------------------------------------------------------

    def evaluate_h2c_break_detection(
        self,
        subset_filter: Optional[Callable] = None,
        label: str = "Regional",
    ) -> int:
        """
        H2c: Locate the structural break via rolling R² scan.

        For each candidate year, fits a post-dummy panel regression to the
        Deliberate Network and identifies the year maximising within-R².

        Returns
        -------
        int
            Best-break year.
        """
        logger.info("Evaluating H2c: Structural Break (%s)", label)
        print(
            f"\n{'=' * 95}\n"
            f"HYPOTHESIS 2c: STRUCTURAL BREAK DISCOVERY ({label.upper()})\n"
            f"{'=' * 95}"
        )
        df = self.analyst.format_did_panel_data()

        if subset_filter:
            df = df[df.apply(subset_filter, axis=1)]

        df_panel = df.set_index(["dyad_id", "year"])
        history = []

        for year in range(config.START_YEAR, config.END_YEAR + 1):
            df_panel["temp_post"] = (
                df_panel.index.get_level_values("year") >= year
            ).astype(int)
            X = sm.add_constant(df_panel[["temp_post"]])
            try:
                res = PanelOLS(
                    df_panel["s_del"], X, entity_effects=True, time_effects=False
                ).fit()
                history.append({"year": year, "r2": res.rsquared_within})
            except Exception as exc:
                logger.warning("H2c scan failed at year=%d: %s", year, exc)

        history_df = pd.DataFrame(history)
        best_year: int = int(history_df.loc[history_df["r2"].idxmax(), "year"])
        max_r2: float = float(history_df["r2"].max())

        logger.info("H2c [%s]: break at %d (R²=%.4f)", label, best_year, max_r2)
        print(
            f"RESULT [{label}]: Optimal break detected at {best_year} "
            f"(R² Within: {max_r2:.4f})"
        )

        self.visualizer.plot_structural_break_search(history_df, best_year, label)
        fit_filename = f"h2c_fit_{label.lower().replace(' ', '_')}.png"
        self.visualizer.plot_segmented_break_fit(df, label, best_year, fit_filename)

        # Release the temporary column to avoid memory retention on large panels.
        del df_panel["temp_post"]

        return best_year

    # ------------------------------------------------------------------
    # H3 — Topological peripheralization
    # ------------------------------------------------------------------

    def evaluate_h3_topology(self, target_country: str = "israel") -> None:
        """
        H3: Track structural position via Eigenvector Centrality over time.

        Statistical test: Mann-Kendall trend test on the annual EC series.
        A negative τ with p < 0.05 confirms monotonic peripheralization.
        """
        logger.info("Evaluating H3: Topological Peripheralization (%s)", target_country)
        print(f"\n{'=' * 95}\nHYPOTHESIS 3: TOPOLOGICAL PERIPHERALIZATION\n{'=' * 95}")

        ec_series: list[tuple[int, float]] = []
        bc_series: list[tuple[int, float]] = []
        cluster_report: list[dict] = []

        key_years = {
            config.START_YEAR,
            config.GEOPOLITICAL_MARKERS["SECOND_INTIFADA"],
            config.GEOPOLITICAL_MARKERS["ARAB_SPRING"],
            config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"],
            config.END_YEAR,
        }

        for year in range(config.START_YEAR, config.END_YEAR + 1):
            try:
                query = self.analyst._get_h3_query(year)
                edges_df = self.analyst.conn.sql(query).df()
            except Exception as exc:
                logger.warning("H3 query failed at year=%d: %s", year, exc)
                continue

            G = self.analyst._build_annual_graph(edges_df)
            if not G.nodes():
                continue

            density: float = nx.density(G)
            avg_clustering: float = nx.average_clustering(G, weight="weight")

            ec_scores: dict[str, float] = self.analyst._eigenvector_centrality(G)
            ec_score: float = ec_scores.get(target_country, 0.0)
            ec_series.append((year, ec_score))

            bc_scores: dict[str, float] = nx.betweenness_centrality(
                G, weight="weight", normalized=True
            )
            bc_score: float = bc_scores.get(target_country, 0.0)
            bc_series.append((year, bc_score))

            if year in key_years:
                communities = list(greedy_modularity_communities(G, weight="weight"))
                mod_score: float = modularity(G, communities, weight="weight")
                isr_comm = next(
                    (c for c in communities if target_country in c), set()
                )
                peers = ", ".join([c for c in isr_comm if c != target_country][:5])

                _ec_ranked = sorted(ec_scores.values(), reverse=True)
                _bc_ranked = sorted(bc_scores.values(), reverse=True)
                cluster_report.append(
                    {
                        "Year": year,
                        "Density": density,
                        "Avg_Clust": avg_clustering,
                        "Q": mod_score,
                        "EC": ec_score,
                        "EC_rank": (
                            (_ec_ranked.index(ec_score) + 1)
                            if ec_score in _ec_ranked
                            else len(_ec_ranked) + 1
                        ),
                        "BC": bc_score,
                        "BC_rank": (
                            (_bc_ranked.index(bc_score) + 1)
                            if bc_score in _bc_ranked
                            else len(_bc_ranked) + 1
                        ),
                        "Peers": peers if peers else "Isolated",
                    }
                )
                self.visualizer.plot_network_topology(
                    G, year, ec_scores, title_prefix="H3:"
                )

            # Release per-year graph objects promptly to avoid accumulation.
            del edges_df, G, ec_scores, bc_scores

        years_list = [y for y, _ in ec_series]
        ec_vals = [v for _, v in ec_series]
        bc_vals = [v for _, v in bc_series]

        print(
            f"\n{'Year':<6} | {'Density':<8} | {'Clust':<8} | {'Q':<8} | "
            f"{'EC':<10} | {'EC_rank':<8} | {'BC':<10} | {'BC_rank':<8} | Peers"
        )
        print("-" * 110)
        for r in cluster_report:
            print(
                f"{r['Year']:<6} | {r['Density']:<8.4f} | {r['Avg_Clust']:<8.4f} | "
                f"{r['Q']:<8.4f} | {r['EC']:<10.4f} | {r['EC_rank']:<8} | "
                f"{r['BC']:<10.4f} | {r['BC_rank']:<8} | {r['Peers']}"
            )

        mk_ec = mk.original_test(ec_vals)
        mk_bc = mk.original_test(bc_vals)
        logger.info(
            "H3 Mann-Kendall EC: tau=%.4f p=%.6f | BC: tau=%.4f p=%.6f",
            mk_ec.Tau, mk_ec.p, mk_bc.Tau, mk_bc.p,
        )
        print(
            f"\n  Mann-Kendall EC ({target_country.upper()}): "
            f"{mk_ec.trend.upper()} (p={mk_ec.p:.6f}, tau={mk_ec.Tau:.4f})"
        )
        print(
            f"  Mann-Kendall BC ({target_country.upper()}): "
            f"{mk_bc.trend.upper()} (p={mk_bc.p:.6f}, tau={mk_bc.Tau:.4f})"
        )

        self.visualizer.plot_h3_centrality_comparison(
            years_list, ec_vals, bc_vals, target_country
        )

        if self.reporter:
            self.reporter.table(
                pd.DataFrame(cluster_report),
                label="h3_centrality_keyYears",
                caption=f"H3: Network Centrality of {target_country.title()} at Key Years",
                index=False,
            )
            self.reporter.table(
                pd.DataFrame(
                    [
                        {
                            "metric": "Eigenvector Centrality",
                            "trend": mk_ec.trend,
                            "tau": mk_ec.Tau,
                            "p_value": mk_ec.p,
                            "s": mk_ec.s,
                        },
                        {
                            "metric": "Betweenness Centrality",
                            "trend": mk_bc.trend,
                            "tau": mk_bc.Tau,
                            "p_value": mk_bc.p,
                            "s": mk_bc.s,
                        },
                    ]
                ),
                label="h3_mann_kendall",
                caption="H3: Mann-Kendall Trend Tests — EC vs BC",
                index=False,
            )

    # ------------------------------------------------------------------
    # H4 — Thematic compartmentalisation
    # ------------------------------------------------------------------

    def evaluate_h4_thematic_bias(self) -> None:
        """
        H4: Test whether Israel–Arab collaboration is disproportionately
        concentrated in politically neutral disciplines (Fisher's Exact Test).

        OR > 1 with p < 0.05 confirms artificial thematic confinement.
        """
        logger.info("Evaluating H4: Thematic Compartmentalisation")
        print(
            f"\n{'=' * 95}\n"
            f"HYPOTHESIS 4: THEMATIC COMPARTMENTALIZATION\n"
            f"{'=' * 95}"
        )
        df = self.analyst.get_thematic_contingency_table()

        contingency = [
            [df.loc["israel_arab", "neutral"], df.loc["israel_arab", "sensitive"]],
            [df.loc["control", "neutral"], df.loc["control", "sensitive"]],
        ]
        odds_ratio, p_value = fisher_exact(contingency)

        a, b = contingency[0][0], contingency[0][1]
        c, d = contingency[1][0], contingency[1][1]
        # Guard against zero cells in the CI formula.
        if a > 0 and b > 0 and c > 0 and d > 0:
            se_log_or = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
            ci_low = float(np.exp(np.log(odds_ratio) - 1.96 * se_log_or))
            ci_high = float(np.exp(np.log(odds_ratio) + 1.96 * se_log_or))
        else:
            ci_low = ci_high = float("nan")
            logger.warning("H4: zero cell in contingency table — CI undefined.")

        logger.info(
            "H4 — OR=%.4f [%.2f–%.2f], p=%.6f",
            odds_ratio, ci_low, ci_high, p_value,
        )

        print(f"\n  {'Group':<20} | {'Neutral':>10} | {'Sensitive':>10}")
        print("  " + "-" * 46)
        for idx in df.index:
            print(
                f"  {idx:<20} | {df.loc[idx, 'neutral']:>10.1f} | "
                f"{df.loc[idx, 'sensitive']:>10.1f}"
            )
        print(
            f"\n  Odds Ratio : {odds_ratio:.4f} "
            f"[95% CI: {ci_low:.2f} – {ci_high:.2f}]"
        )
        print(f"  Fisher p   : {p_value:.6f}")

        if self.reporter:
            self.reporter.contingency_table(df, odds_ratio, p_value, ci_low, ci_high)
            self.reporter.table(
                pd.DataFrame(
                    [
                        {
                            "odds_ratio": round(odds_ratio, 4),
                            "ci_low": round(ci_low, 4),
                            "ci_high": round(ci_high, 4),
                            "p_value": round(p_value, 6),
                        }
                    ]
                ),
                label="h4_fisher_exact",
                caption="H4: Thematic Compartmentalisation — Fisher Exact Test",
                index=False,
            )

        self.visualizer.plot_h4_thematic(df)
