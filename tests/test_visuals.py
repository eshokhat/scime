"""
test_visuals.py
---------------
Smoke tests: every ScientificVisualizer method must complete without
raising an exception and must produce the expected output file.

These tests do NOT assert pixel-level image content — they verify that:
  1. The method runs without error on valid inputs.
  2. The output file is created in config.FIGURES_DIR.
  3. The output file is non-empty (non-zero bytes).
"""

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _affinity_df():
    """Minimal DataFrame matching the output of calculate_dyad_affinity."""
    return pd.DataFrame(
        {
            "year": list(range(2000, 2026)),
            "affinity_s_unr": np.random.uniform(0, 0.01, 26),
            "affinity_s_del": np.random.uniform(0, 0.008, 26),
        }
    )


def _regional_df():
    """Minimal DataFrame matching fetch_regional_affinity_data()."""
    rows = []
    for year in range(2000, 2026):
        rows.append(
            {
                "year": year,
                "c_i": "egypt",
                "c_j": "israel",
                "s_unr": 0.01,
                "s_del": 0.005,
                "delta_c": 0.5,
            }
        )
        rows.append(
            {
                "year": year,
                "c_i": "egypt",
                "c_j": "jordan",
                "s_unr": 0.008,
                "s_del": 0.006,
                "delta_c": 0.25,
            }
        )
    return pd.DataFrame(rows)


def _sensitivity_df():
    ns = list(range(2, 16))
    base = [float(n) ** 0.5 for n in ns]
    growth = pd.Series(base).pct_change().fillna(0).tolist()
    return pd.DataFrame(
        {
            "n_threshold": ns,
            "israel_involved_c_star": base,
            "non_israel_c_star": [b * 0.6 for b in base],
            "ratio_isr_non": [1.4] * len(ns),
            "growth_isr": growth,
        }
    )


def _assert_file_created(figures_dir: Path, filename: str):
    path = figures_dir / filename
    assert path.exists(), f"Expected file not created: {filename}"
    assert path.stat().st_size > 0, f"File is empty: {filename}"


class TestAffinityTrend:
    def test_creates_png(self, visualizer_in_tmp):
        df = _affinity_df()
        visualizer_in_tmp.plot_affinity_trends(df, "israel", "egypt")
        _assert_file_created(visualizer_in_tmp.figures_dir, "affinity_israel_egypt.png")


class TestH1Plots:
    def test_mirage_bar_creates_png(self, visualizer_in_tmp):
        visualizer_in_tmp.plot_h1_mirage(0.42, 0.18)
        _assert_file_created(visualizer_in_tmp.figures_dir, "h1_mirage_comparison.png")

    def test_mirage_distribution_creates_png(self, visualizer_in_tmp):
        visualizer_in_tmp.plot_h1_mirage_2(_regional_df())
        _assert_file_created(
            visualizer_in_tmp.figures_dir, "h1_mirage_distribution.png"
        )


class TestH2Plots:
    def _did_df(self, group_col, groups):
        rows = []
        for yr in range(2000, 2026):
            for g in groups:
                rows.append(
                    {"year": yr, group_col: g, "s_del": np.random.uniform(0, 0.01)}
                )
        return pd.DataFrame(rows)

    def test_did_comparison_h2a(self, visualizer_in_tmp):
        df = self._did_df("h2a_group", ["destabilized", "israel", "stable_control"])
        visualizer_in_tmp.plot_did_comparison(
            df, "h2a_group", 2011, "H2a Test", "h2a_test.png"
        )
        _assert_file_created(visualizer_in_tmp.figures_dir, "h2a_test.png")

    def test_structural_break_search_creates_png(self, visualizer_in_tmp):
        history = pd.DataFrame(
            {
                "year": list(range(1995, 2026)),
                "r2": np.random.uniform(0, 0.1, 31),
            }
        )
        visualizer_in_tmp.plot_structural_break_search(history, 2011, "TestRegion")
        _assert_file_created(visualizer_in_tmp.figures_dir, "h2c_break_testregion.png")

    def test_segmented_break_fit_creates_png(self, visualizer_in_tmp):
        df = _regional_df()
        visualizer_in_tmp.plot_segmented_break_fit(df, "Test", 2011, "h2c_fit_test.png")
        _assert_file_created(visualizer_in_tmp.figures_dir, "h2c_fit_test.png")


class TestH3Plots:
    def _sample_graph(self):
        G = nx.Graph()
        edges = [
            ("israel", "egypt", 0.5),
            ("israel", "jordan", 0.3),
            ("egypt", "jordan", 0.2),
            ("israel", "morocco", 0.4),
        ]
        for u, v, w in edges:
            G.add_edge(u, v, weight=w)
        return G

    def test_network_topology_creates_png(self, visualizer_in_tmp):
        G = self._sample_graph()
        centrality = nx.eigenvector_centrality(G, weight="weight", max_iter=500)
        visualizer_in_tmp.plot_network_topology(G, 2011, centrality, "H3:")
        _assert_file_created(visualizer_in_tmp.figures_dir, "h3_clusters_2011.png")

    def test_network_topology_empty_graph_does_not_crash(self, visualizer_in_tmp):
        visualizer_in_tmp.plot_network_topology(nx.Graph(), 1990, {})

    def test_centrality_comparison_creates_png(self, visualizer_in_tmp):
        years = list(range(1990, 2026))
        ec = [np.random.uniform(0.1, 0.5) for _ in years]
        bc = [np.random.uniform(0.0, 0.3) for _ in years]
        visualizer_in_tmp.plot_h3_centrality_comparison(years, ec, bc, "israel")
        _assert_file_created(
            visualizer_in_tmp.figures_dir, "h3_centrality_comparison_israel.png"
        )


class TestH4Plot:
    def test_thematic_bias_creates_png(self, visualizer_in_tmp):
        df = pd.DataFrame(
            {"neutral": [120.0, 300.0], "sensitive": [80.0, 150.0]},
            index=["israel_arab", "control"],
        )
        visualizer_in_tmp.plot_h4_thematic(df)
        _assert_file_created(visualizer_in_tmp.figures_dir, "h4_thematic_bias.png")


class TestThresholdSensitivityPlot:
    def test_elbow_plot_creates_png(self, visualizer_in_tmp):
        df = _sensitivity_df()
        visualizer_in_tmp.plot_threshold_sensitivity(df, optimal_n=5)
        _assert_file_created(
            visualizer_in_tmp.figures_dir, "threshold_sensitivity_elbow.png"
        )
