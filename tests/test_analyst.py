"""
test_analyst.py
---------------
Logic tests for engine/processor.py — NetworkAnalyst.

Sections
--------
1. TestNetworkAnalystInit          — constructor, context manager, mena_countries
2. TestDeliberateNPThresholdConfig — DELIBERATE_NP_THRESHOLD is read from config
                                     and gates which papers enter each analysis
3. TestScaleWeightTiers            — 0.8/0.2 multiplier in config.WEIGHTS['SCALE']
4. TestEigenvectorCentralityMocked — nx.eigenvector_centrality is called with
                                     a graph that carries weighted edges
5. TestNetworkAnalystPublicMethods — smoke / contract tests for every public method

All tests are stateless.  DB access is satisfied by the in-memory `test_db`
fixture from conftest.py.  networkx calls are mocked where the test must
inspect the graph object passed to the algorithm.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from engine.processor import NetworkAnalyst, ThematicAnalyst


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


class TestNetworkAnalystInit:
    """NetworkAnalyst starts in a well-defined state after construction."""

    def test_mena_countries_populated(self, mock_network_analyst):
        assert len(mock_network_analyst.mena_countries) > 0

    def test_israel_in_mena_countries(self, mock_network_analyst):
        assert "israel" in mock_network_analyst.mena_countries

    def test_mena_countries_length_matches_config(self, mock_network_analyst):
        assert len(mock_network_analyst.mena_countries) == len(config.COUNTRIES_LIST)

    def test_affinity_cache_starts_empty(self, mock_network_analyst):
        assert mock_network_analyst._affinity_cache == {}

    def test_context_manager_returns_self(self, monkeypatch):
        """Uses a fresh isolated connection so the shared test_db is not closed."""
        import duckdb
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        with NetworkAnalyst() as na:
            assert isinstance(na, NetworkAnalyst)

    def test_context_manager_exit_does_not_raise(self, monkeypatch):
        """Uses a fresh isolated connection so the shared test_db is not closed."""
        import duckdb
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        with NetworkAnalyst():
            pass

    def test_close_is_idempotent(self, monkeypatch):
        """
        Calling close() twice must not raise.
        Uses a fresh isolated connection so the shared test_db is not affected.
        """
        import duckdb
        fresh_con = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh_con)
        analyst = NetworkAnalyst()
        analyst.close()
        analyst.close()  # second call must be silent


# ---------------------------------------------------------------------------
# 2. DELIBERATE_NP_THRESHOLD config reads
# ---------------------------------------------------------------------------


class TestDeliberateNPThresholdConfig:
    """
    NetworkAnalyst must gate paper inclusion on config.DELIBERATE_NP_THRESHOLD.

    Test DB paper sizes:
      eid1 np=2  (israel–egypt,              2015)
      eid2 np=2  (israel–morocco,            2020)
      eid3 np=2  (egypt–jordan,              2015)
      eid4 np=3  (israel–egypt–morocco,      2021)
      eid5 np=8  (8-country mega-project,    2015)
    """

    def test_threshold_two_excludes_np3_paper(self, mock_network_analyst, monkeypatch):
        """
        With max_countries=2 (= threshold=2), eid4 (np=3) is excluded.
        israel–egypt in 2021 must have C* = 0.
        """
        df = mock_network_analyst.calculate_dyad_affinity(
            "israel", "egypt", max_countries=2
        )
        row = df[df["year"] == 2021]
        if not row.empty:
            assert math.isclose(row.iloc[0]["c_star"], 0.0, abs_tol=1e-9)

    def test_threshold_three_includes_np3_paper(self, mock_network_analyst):
        """
        With max_countries=3 (threshold ≥ 3), eid4 (np=3) is included.
        israel–egypt 2021 C* = 1/3.
        """
        df = mock_network_analyst.calculate_dyad_affinity(
            "israel", "egypt", max_countries=3
        )
        row = df[df["year"] == 2021]
        assert not row.empty
        assert math.isclose(row.iloc[0]["c_star"], 1 / 3, rel_tol=1e-5)

    def test_threshold_excludes_mega_project(self, mock_network_analyst):
        """
        max_countries=5 excludes eid5 (np=8).
        israel–egypt 2015 C* must equal eid1 only = 1.0.
        """
        df = mock_network_analyst.calculate_dyad_affinity(
            "israel", "egypt", max_countries=5
        )
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["c_star"], 1.0, rel_tol=1e-6)

    def test_unrestricted_includes_mega_project(self, mock_network_analyst):
        """
        No max_countries cap: eid5 (np=8) is included.
        israel–egypt 2015 C* = 1.0 + 1/28 ≈ 1.035714.
        """
        df = mock_network_analyst.calculate_dyad_affinity("israel", "egypt")
        row = df[df["year"] == 2015].iloc[0]
        expected = 1.0 + (2 / 56)  # eid1 + eid5
        assert math.isclose(row["c_star"], expected, rel_tol=1e-5)

    def test_sensitivity_stats_increases_with_n(self, mock_network_analyst):
        """C* totals can only increase as the threshold grows (more papers qualify)."""
        prev_isr = 0.0
        for n in [2, 3, 8]:
            df = mock_network_analyst.fetch_sensitivity_stats(n)
            isr = df[df["group_type"] == "Israel-Involved"]["c_star"].sum()
            assert isr >= prev_isr
            prev_isr = isr

    def test_affinity_cache_keyed_by_threshold(self, mock_network_analyst, monkeypatch):
        """
        _affinity_cache is a dict keyed on DELIBERATE_NP_THRESHOLD.
        After fetching at threshold=3 and threshold=5, both keys must exist.
        """
        mock_network_analyst.clear_affinity_cache()

        monkeypatch.setattr(config, "DELIBERATE_NP_THRESHOLD", 3)
        monkeypatch.setattr(config, "DELIBERATE_N", 3)
        mock_network_analyst.fetch_regional_affinity_data()
        assert 3 in mock_network_analyst._affinity_cache

        monkeypatch.setattr(config, "DELIBERATE_NP_THRESHOLD", 5)
        monkeypatch.setattr(config, "DELIBERATE_N", 5)
        mock_network_analyst.fetch_regional_affinity_data()
        assert 5 in mock_network_analyst._affinity_cache

    def test_clear_affinity_cache_empties_dict(self, mock_network_analyst, monkeypatch):
        monkeypatch.setattr(config, "DELIBERATE_NP_THRESHOLD", 4)
        monkeypatch.setattr(config, "DELIBERATE_N", 4)
        mock_network_analyst.fetch_regional_affinity_data()  # populates cache
        mock_network_analyst.clear_affinity_cache()
        assert mock_network_analyst._affinity_cache == {}

    def test_cached_result_consistent_with_fresh_query(
        self, mock_network_analyst, monkeypatch
    ):
        """Second call (from cache) must return the same DataFrame as the first."""
        monkeypatch.setattr(config, "DELIBERATE_NP_THRESHOLD", 4)
        monkeypatch.setattr(config, "DELIBERATE_N", 4)
        mock_network_analyst.clear_affinity_cache()
        first = mock_network_analyst.fetch_regional_affinity_data().reset_index(drop=True)
        second = mock_network_analyst.fetch_regional_affinity_data().reset_index(drop=True)
        pd.testing.assert_frame_equal(first, second)


# ---------------------------------------------------------------------------
# 3. Scale weight tiers  0.8 / 0.2
# ---------------------------------------------------------------------------


class TestScaleWeightTiers:
    """
    config.WEIGHTS['SCALE'] carries the 0.8/0.2 multipliers that up-weight
    Deliberate-Network papers and down-weight consortia contributions.
    """

    def test_scale_small_is_0_8(self):
        assert config.WEIGHTS["SCALE"]["small"] == pytest.approx(0.8)

    def test_scale_cons_is_0_2(self):
        assert config.WEIGHTS["SCALE"]["cons"] == pytest.approx(0.2)

    def test_small_group_alias_equals_small(self):
        """small_group is a backward-compat alias and must equal 'small'."""
        assert config.WEIGHTS["SCALE"]["small_group"] == config.WEIGHTS["SCALE"]["small"]

    def test_consortia_alias_equals_cons(self):
        assert config.WEIGHTS["SCALE"]["consortia"] == config.WEIGHTS["SCALE"]["cons"]

    def test_weights_sum_to_one(self):
        """0.8 + 0.2 = 1.0 — the two tiers span the full weight."""
        total = config.WEIGHTS["SCALE"]["small"] + config.WEIGHTS["SCALE"]["cons"]
        assert math.isclose(total, 1.0, rel_tol=1e-12)

    def test_deliberate_weight_exceeds_consortia_weight(self):
        """Papers in the Deliberate Network are up-weighted."""
        assert config.WEIGHTS["SCALE"]["small"] > config.WEIGHTS["SCALE"]["cons"]

    def test_scope_international_is_0_7(self):
        """International (multi-country) scope weight must be 0.7."""
        assert config.WEIGHTS["SCOPE"]["intl"] == pytest.approx(0.7)

    def test_scope_domestic_is_1_0(self):
        assert config.WEIGHTS["SCOPE"]["domestic"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. Eigenvector Centrality on weighted edges
# ---------------------------------------------------------------------------


class TestEigenvectorCentralityMocked:
    """
    compute_network_centrality must pass a weighted graph to
    nx.eigenvector_centrality so that collaboration-strength differences
    between dyads influence the centrality scores.
    """

    def test_returns_dict_for_active_year(self, mock_network_analyst):
        result = mock_network_analyst.compute_network_centrality(2015)
        assert isinstance(result, dict)

    def test_returns_empty_dict_for_empty_year(self, mock_network_analyst):
        """2000 has no papers in the synthetic DB → empty graph → {}."""
        result = mock_network_analyst.compute_network_centrality(2000)
        assert result == {}

    def test_centrality_keys_are_strings(self, mock_network_analyst):
        result = mock_network_analyst.compute_network_centrality(2015)
        for key in result:
            assert isinstance(key, str)

    def test_centrality_values_are_floats(self, mock_network_analyst):
        result = mock_network_analyst.compute_network_centrality(2015)
        for val in result.values():
            assert isinstance(val, float)

    def test_nx_ec_called_with_weighted_graph(self, mock_network_analyst):
        """
        Spy on nx.eigenvector_centrality: the graph argument must carry
        'weight' edge attributes so that Salton-index differences propagate
        into the centrality scores.
        """
        captured: dict = {}

        def _spy(G, *args, **kwargs):
            captured["G"] = G
            return {n: 1.0 / max(len(G), 1) for n in G.nodes()}

        with patch("networkx.eigenvector_centrality", _spy):
            mock_network_analyst.compute_network_centrality(2015)

        if "G" in captured and captured["G"].number_of_edges() > 0:
            edges_with_data = list(captured["G"].edges(data=True))
            assert any("weight" in d for _, _, d in edges_with_data), (
                "Graph edges must carry a 'weight' attribute "
                "for Salton-weighted Eigenvector Centrality."
            )

    def test_convergence_failure_returns_empty_dict(self, mock_network_analyst):
        """PowerIterationFailedConvergence must be caught; result must be {}."""
        with patch(
            "networkx.eigenvector_centrality",
            side_effect=nx.PowerIterationFailedConvergence(1000),
        ):
            result = mock_network_analyst.compute_network_centrality(2015)
        assert result == {}

    def test_active_year_centrality_sums_positive(self, mock_network_analyst):
        """For a year with papers, the sum of EC values must be > 0 when non-empty."""
        result = mock_network_analyst.compute_network_centrality(2015)
        if result:
            assert sum(result.values()) > 0.0


# ---------------------------------------------------------------------------
# 5. Public-method contracts
# ---------------------------------------------------------------------------


class TestNetworkAnalystPublicMethods:
    """Smoke + contract tests: return types, required columns, row counts."""

    def test_get_basic_metrics_returns_dict(self, mock_network_analyst):
        assert isinstance(mock_network_analyst.get_basic_metrics(), dict)

    def test_get_basic_metrics_total_papers_key(self, mock_network_analyst):
        assert "total_papers" in mock_network_analyst.get_basic_metrics()

    def test_get_basic_metrics_count_is_five(self, mock_network_analyst):
        """Synthetic DB has exactly 5 papers."""
        assert mock_network_analyst.get_basic_metrics()["total_papers"] == 5

    def test_fetch_sensitivity_stats_returns_df(self, mock_network_analyst):
        assert isinstance(mock_network_analyst.fetch_sensitivity_stats(4), pd.DataFrame)

    def test_fetch_sensitivity_stats_two_groups(self, mock_network_analyst):
        df = mock_network_analyst.fetch_sensitivity_stats(4)
        assert set(df["group_type"]) == {"Israel-Involved", "Non-Israel"}

    def test_calculate_dyad_affinity_returns_df(self, mock_network_analyst):
        df = mock_network_analyst.calculate_dyad_affinity("israel", "egypt")
        assert isinstance(df, pd.DataFrame)

    def test_calculate_dyad_affinity_required_columns(self, mock_network_analyst):
        df = mock_network_analyst.calculate_dyad_affinity("israel", "egypt")
        for col in ["year", "p_i", "p_j", "c_star", "affinity_s"]:
            assert col in df.columns

    def test_regional_affinity_returns_df(self, mock_network_analyst):
        assert isinstance(mock_network_analyst.fetch_regional_affinity_data(), pd.DataFrame)

    def test_regional_affinity_required_columns(self, mock_network_analyst):
        df = mock_network_analyst.fetch_regional_affinity_data()
        for col in ["year", "c_i", "c_j", "s_unr", "s_del", "delta_c"]:
            assert col in df.columns

    def test_regional_affinity_delta_c_in_unit_interval(self, mock_network_analyst):
        df = mock_network_analyst.fetch_regional_affinity_data()
        nonzero = df[df["s_unr"] > 0]
        assert (nonzero["delta_c"] >= 0).all()
        assert (nonzero["delta_c"] <= 1).all()

    def test_get_h3_query_returns_non_empty_string(self, mock_network_analyst):
        q = mock_network_analyst._get_h3_query(2015)
        assert isinstance(q, str) and len(q) > 50

    def test_get_h3_query_embeds_year(self, mock_network_analyst):
        assert "2011" in mock_network_analyst._get_h3_query(2011)

    def test_get_h3_query_embeds_deliberate_n(self, mock_network_analyst, monkeypatch):
        monkeypatch.setattr(config, "DELIBERATE_N", 7)
        assert "7" in mock_network_analyst._get_h3_query(2015)


# ---------------------------------------------------------------------------
# 6. ThematicAnalyst — contingency table shape
# ---------------------------------------------------------------------------


class TestThematicAnalystContingencyTable:
    """
    ThematicAnalyst.get_contingency_table() must return a 2×2 DataFrame
    with the correct index and column labels.
    """

    @pytest.fixture
    def thematic_analyst(self, test_db, monkeypatch):
        import duckdb as _ddb
        monkeypatch.setattr(_ddb, "connect", lambda *a, **kw: test_db)
        return ThematicAnalyst()

    def test_returns_dataframe(self, thematic_analyst):
        assert isinstance(thematic_analyst.get_contingency_table(), pd.DataFrame)

    def test_index_has_israel_arab(self, thematic_analyst):
        assert "israel_arab" in thematic_analyst.get_contingency_table().index

    def test_index_has_control(self, thematic_analyst):
        assert "control" in thematic_analyst.get_contingency_table().index

    def test_columns_neutral_and_sensitive(self, thematic_analyst):
        df = thematic_analyst.get_contingency_table()
        assert "neutral" in df.columns
        assert "sensitive" in df.columns

    def test_all_values_non_negative(self, thematic_analyst):
        df = thematic_analyst.get_contingency_table()
        assert (df >= 0).all().all()

    def test_shape_is_2x2(self, thematic_analyst):
        assert thematic_analyst.get_contingency_table().shape == (2, 2)
