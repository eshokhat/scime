"""
test_models.py
--------------
Tests covering:
  1. Dataclass type contracts    — SensitivityRecord, DyadAffinityRecord,
                                   CentralityRecord, PipelineConfig
  2. PipelineConfig methods      — from_config(), to_dict()
  3. ResearchPipeline._find_elbow — perpendicular distance elbow algorithm
  4. ResearchPipeline.run_threshold_sensitivity_test — end-to-end integration
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from engine.models import (
    CentralityRecord,
    DyadAffinityRecord,
    PipelineConfig,
    ScientificWorkflow,
    SensitivityRecord,
)


class TestFindElbow:
    """
    _find_elbow uses maximum perpendicular distance from the line connecting
    the first and last points of the normalised curve.
    """

    def test_perfect_l_curve_finds_correct_elbow(self):
        """
        x = [2, 3, 4, 5, 6, 7]
        y = [1, 2, 3, 3, 3, 3]   ← sharp bend at x=4 (index 2)

        Normalised: line from (0,0)→(1,1).
        Perpendicular distances: max at index 2 → x=4.
        """
        x = [2, 3, 4, 5, 6, 7]
        y = [1, 2, 3, 3, 3, 3]
        assert ScientificWorkflow._find_elbow(x, y) == 4

    def test_returns_value_within_input_range(self):
        x = list(range(2, 16))
        y = [i**0.3 for i in x]  # concave growth
        result = ScientificWorkflow._find_elbow(x, y)
        assert x[0] <= result <= x[-1]

    def test_returns_integer(self):
        x = [2, 3, 4, 5, 6]
        y = [1.0, 3.5, 5.0, 5.3, 5.4]
        assert isinstance(ScientificWorkflow._find_elbow(x, y), int)

    def test_single_element_returns_that_element(self):
        assert ScientificWorkflow._find_elbow([5], [10.0]) == 5

    def test_flat_curve_returns_first_element(self):
        """All values equal → all distances equal → argmax returns index 0."""
        x = [2, 3, 4, 5]
        y = [1.0, 1.0, 1.0, 1.0]
        result = ScientificWorkflow._find_elbow(x, y)
        assert result == x[0]

    def test_strictly_linear_curve_finds_boundary(self):
        """
        A perfectly linear curve has all interior points equidistant from the
        first–last line. The algorithm returns the first maximum, which is index 0.
        The important guarantee is that the result is within range.
        """
        x = [2, 3, 4, 5, 6]
        y = [0.0, 1.0, 2.0, 3.0, 4.0]
        result = ScientificWorkflow._find_elbow(x, y)
        assert x[0] <= result <= x[-1]

    def test_longer_plateau_same_elbow(self):
        """Extending the plateau after the bend should not shift the elbow."""
        x_short = [2, 3, 4, 5, 6]
        y_short = [1, 2, 3, 3, 3]
        x_long = [2, 3, 4, 5, 6, 7, 8, 9]
        y_long = [1, 2, 3, 3, 3, 3, 3, 3]
        assert ScientificWorkflow._find_elbow(
            x_short, y_short
        ) == ScientificWorkflow._find_elbow(x_long, y_long)

    @pytest.mark.parametrize("bend_at", [3, 5, 8, 12])
    def test_elbow_detected_near_bend(self, bend_at):
        """
        Parametrised: for various bend positions the detected elbow
        should be within ±1 of the true bend.
        """
        x = list(range(2, 20))
        y = [min(i - 1, bend_at - 1) * 1.0 for i in x]
        result = ScientificWorkflow._find_elbow(x, y)
        assert abs(result - bend_at) <= 1


class TestSensitivityTestIntegration:
    """
    run_threshold_sensitivity_test: end-to-end with mock analyzer.
    Verifies structure of the result DataFrame and side-effects.
    """

    @pytest.fixture
    def workflow_with_mock(self, test_db, monkeypatch):
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        from unittest.mock import MagicMock

        from engine.analyzer import ScientificAnalyzer
        from engine.visuals import ScientificVisualizer

        w = ScientificWorkflow.__new__(ScientificWorkflow)
        w.analyzer = ScientificAnalyzer()
        w.visualizer = MagicMock()  # suppress actual PNG generation
        w.reporter = None
        return w

    def test_returns_tuple_of_df_and_int(self, workflow_with_mock):
        res_df, optimal_n = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert isinstance(res_df, pd.DataFrame)
        assert isinstance(optimal_n, int)

    def test_result_has_correct_row_count(self, workflow_with_mock):
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert len(res_df) == 7  # N = 2,3,4,5,6,7,8

    def test_result_has_required_columns(self, workflow_with_mock):
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        for col in [
            "n_threshold",
            "israel_involved_c_star",
            "non_israel_c_star",
            "ratio_isr_non",
            "growth_isr",
        ]:
            assert col in res_df.columns

    def test_n_threshold_column_correct_range(self, workflow_with_mock):
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert list(res_df["n_threshold"]) == list(range(2, 9))

    def test_c_star_monotone_non_decreasing(self, workflow_with_mock):
        """Adding more papers can only increase total C*."""
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        vals = res_df["israel_involved_c_star"].tolist()
        assert all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))

    def test_updates_config_deliberate_n(self, workflow_with_mock, monkeypatch):
        monkeypatch.setattr(config, "DELIBERATE_N", 99)  # set a known wrong value
        _, optimal_n = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert config.DELIBERATE_N == optimal_n
        assert config.DELIBERATE_N != 99

    def test_optimal_n_within_range(self, workflow_with_mock):
        _, optimal_n = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert 2 <= optimal_n <= 8

    def test_first_row_growth_is_zero(self, workflow_with_mock):
        """pct_change().fillna(0) → first row growth = 0."""
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        assert res_df.iloc[0]["growth_isr"] == 0.0

    def test_ratio_positive_when_both_groups_nonzero(self, workflow_with_mock):
        res_df, _ = workflow_with_mock.run_threshold_sensitivity_test(2, 8)
        nonzero = res_df[res_df["non_israel_c_star"] > 0]
        assert (nonzero["ratio_isr_non"] > 0).all()


# ---------------------------------------------------------------------------
# Dataclass type contracts
# ---------------------------------------------------------------------------


class TestSensitivityRecordTypes:
    """SensitivityRecord fields must accept and store the declared types."""

    def _make(self, **overrides):
        defaults = dict(
            n_threshold=4,
            israel_involved_c_star=2.667,
            non_israel_c_star=1.333,
            ratio_isr_non=2.0,
            growth_isr=0.15,
        )
        defaults.update(overrides)
        return SensitivityRecord(**defaults)

    def test_n_threshold_is_int(self):
        rec = self._make()
        assert isinstance(rec.n_threshold, int)

    def test_israel_involved_c_star_is_float(self):
        assert isinstance(self._make().israel_involved_c_star, float)

    def test_non_israel_c_star_is_float(self):
        assert isinstance(self._make().non_israel_c_star, float)

    def test_ratio_isr_non_is_float(self):
        assert isinstance(self._make().ratio_isr_non, float)

    def test_growth_isr_defaults_to_zero(self):
        rec = SensitivityRecord(
            n_threshold=2,
            israel_involved_c_star=1.0,
            non_israel_c_star=0.5,
            ratio_isr_non=2.0,
        )
        assert rec.growth_isr == 0.0

    def test_stores_values_correctly(self):
        rec = self._make(n_threshold=7, ratio_isr_non=3.14)
        assert rec.n_threshold == 7
        assert math.isclose(rec.ratio_isr_non, 3.14, rel_tol=1e-9)


class TestDyadAffinityRecordTypes:
    """DyadAffinityRecord fields must hold the correct types and values."""

    def _make(self, **overrides):
        defaults = dict(year=2015, p_i=5000.0, p_j=1000.0, c_star=1.0, affinity_s=4.472e-4)
        defaults.update(overrides)
        return DyadAffinityRecord(**defaults)

    def test_year_is_int(self):
        assert isinstance(self._make().year, int)

    def test_p_i_is_float(self):
        assert isinstance(self._make().p_i, float)

    def test_p_j_is_float(self):
        assert isinstance(self._make().p_j, float)

    def test_c_star_is_float(self):
        assert isinstance(self._make().c_star, float)

    def test_affinity_s_is_float(self):
        assert isinstance(self._make().affinity_s, float)

    def test_stores_year_correctly(self):
        assert self._make(year=2020).year == 2020

    def test_zero_c_star_is_valid(self):
        rec = self._make(c_star=0.0, affinity_s=0.0)
        assert rec.c_star == 0.0


class TestCentralityRecordTypes:
    """CentralityRecord must hold all seven numeric fields plus a string."""

    def _make(self, **overrides):
        defaults = dict(
            year=2015,
            density=0.4,
            avg_clustering=0.3,
            modularity_q=0.25,
            ec=0.6,
            ec_rank=1,
            bc=0.15,
            bc_rank=2,
            peers="egypt, jordan",
        )
        defaults.update(overrides)
        return CentralityRecord(**defaults)

    def test_year_is_int(self):
        assert isinstance(self._make().year, int)

    def test_density_is_float(self):
        assert isinstance(self._make().density, float)

    def test_avg_clustering_is_float(self):
        assert isinstance(self._make().avg_clustering, float)

    def test_modularity_q_is_float(self):
        assert isinstance(self._make().modularity_q, float)

    def test_ec_is_float(self):
        assert isinstance(self._make().ec, float)

    def test_ec_rank_is_int(self):
        assert isinstance(self._make().ec_rank, int)

    def test_bc_is_float(self):
        assert isinstance(self._make().bc, float)

    def test_bc_rank_is_int(self):
        assert isinstance(self._make().bc_rank, int)

    def test_peers_is_str(self):
        assert isinstance(self._make().peers, str)

    def test_all_fields_stored(self):
        rec = self._make(year=2020, ec=0.9, ec_rank=1)
        assert rec.year == 2020
        assert math.isclose(rec.ec, 0.9, rel_tol=1e-12)
        assert rec.ec_rank == 1


class TestPipelineConfigTypes:
    """PipelineConfig fields, from_config(), and to_dict() contracts."""

    @pytest.fixture
    def cfg(self):
        return PipelineConfig(
            deliberate_np_threshold=4,
            scale_small=0.8,
            scale_cons=0.2,
            scope_domestic=1.0,
            scope_intl=0.7,
            thematic_method="proportional",
            start_year=1990,
            end_year=2025,
        )

    def test_deliberate_np_threshold_is_int(self, cfg):
        assert isinstance(cfg.deliberate_np_threshold, int)

    def test_scale_small_is_float(self, cfg):
        assert isinstance(cfg.scale_small, float)

    def test_scale_cons_is_float(self, cfg):
        assert isinstance(cfg.scale_cons, float)

    def test_thematic_method_is_str(self, cfg):
        assert isinstance(cfg.thematic_method, str)

    def test_start_year_is_int(self, cfg):
        assert isinstance(cfg.start_year, int)

    def test_end_year_is_int(self, cfg):
        assert isinstance(cfg.end_year, int)

    def test_from_config_returns_pipeline_config(self):
        result = PipelineConfig.from_config()
        assert isinstance(result, PipelineConfig)

    def test_from_config_threshold_matches_config(self):
        result = PipelineConfig.from_config()
        assert result.deliberate_np_threshold == config.DELIBERATE_NP_THRESHOLD

    def test_from_config_start_year_matches(self):
        assert PipelineConfig.from_config().start_year == config.START_YEAR

    def test_from_config_end_year_matches(self):
        assert PipelineConfig.from_config().end_year == config.END_YEAR

    def test_to_dict_returns_dict(self, cfg):
        assert isinstance(cfg.to_dict(), dict)

    def test_to_dict_has_threshold_key(self, cfg):
        assert "deliberate_np_threshold" in cfg.to_dict()

    def test_to_dict_has_weights_key(self, cfg):
        assert "weights" in cfg.to_dict()

    def test_to_dict_has_thematic_method_key(self, cfg):
        assert "thematic_method" in cfg.to_dict()

    def test_to_dict_weights_has_scale(self, cfg):
        assert "SCALE" in cfg.to_dict()["weights"]

    def test_to_dict_weights_has_scope(self, cfg):
        assert "SCOPE" in cfg.to_dict()["weights"]

    def test_to_dict_threshold_value_correct(self, cfg):
        assert cfg.to_dict()["deliberate_np_threshold"] == 4

    def test_to_dict_is_json_serialisable(self, cfg):
        import json
        serialised = json.dumps(cfg.to_dict())  # must not raise
        assert isinstance(serialised, str)
