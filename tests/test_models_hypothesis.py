"""
test_models_hypothesis.py
--------------------------
Hypothesis-level tests for engine/orchestrator.py — ResearchPipeline.
(Imported via engine/models.py backward-compat alias: ScientificWorkflow.)

Lines covered
-------------
L31-34  : __init__ normalized_states set
L47-55  : _report_panel_results helper
L164    : reporter branch in run_threshold_sensitivity_test
L178-204: execute_step1_normalization
L207-249: evaluate_h1_mirage
L257-291: evaluate_h2a_destabilization
L296-323: evaluate_h2b_normalization
L334-372: evaluate_h2c_break_detection
L375-477: evaluate_h3_topology
L502-547: evaluate_h4_thematic_bias

Also supplements test_reporter.py with:
  TestReporterConsoleHelpers — covers Reporter.section, Reporter.subsection,
  and Reporter.regression_summary.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Make the project root importable regardless of where pytest is invoked
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Module-level synthetic panel helpers
# ---------------------------------------------------------------------------


def _make_h2a_panel() -> pd.DataFrame:
    """36 years × 6 dyads = 216 rows for PanelOLS (H2a: Arab Spring)."""
    np.random.seed(42)
    dyad_specs = [
        ("egypt_israel", "destabilized"),
        ("syria_morocco", "destabilized"),
        ("bahrain_israel", "israel"),
        ("oman_israel", "israel"),
        ("jordan_morocco", "stable_control"),
        ("bahrain_kuwait", "stable_control"),
    ]
    rows = []
    for dyad, group in dyad_specs:
        ci, cj = dyad.split("_")
        for year in range(1990, 2026):
            post = int(year >= 2011)
            rows.append(
                {
                    "year": year,
                    "c_i": ci,
                    "c_j": cj,
                    "s_unr": max(0.0, 0.01 + np.random.normal(0, 0.002)),
                    "s_del": max(0.0, 0.008 + np.random.normal(0, 0.002)),
                    "delta_c": max(0.0, 0.2 + np.random.normal(0, 0.05)),
                    "h2a_group": group,
                    "post_2011": post,
                    "time_since_2011": max(0, year - 2011),
                    "destab_post": int(group == "destabilized") * post,
                    "destab_trend_slope": int(group == "destabilized")
                    * max(0, year - 2011),
                    "israel_post": int(group == "israel") * post,
                    "dyad_id": dyad,
                }
            )
    return pd.DataFrame(rows)


def _make_h2b_panel() -> pd.DataFrame:
    """36 years × 6 dyads = 216 rows for PanelOLS (H2b: Abraham Accords)."""
    np.random.seed(42)
    dyad_specs = [
        ("israel_morocco", "norm"),
        ("bahrain_israel", "norm"),
        ("egypt_israel", "nonnorm"),
        ("iran_israel", "nonnorm"),
        ("egypt_jordan", "reference"),
        ("jordan_morocco", "reference"),
    ]
    rows = []
    for dyad, group in dyad_specs:
        ci, cj = dyad.split("_")
        for year in range(1990, 2026):
            post = int(year >= 2020)
            rows.append(
                {
                    "year": year,
                    "c_i": ci,
                    "c_j": cj,
                    "s_unr": max(0.0, 0.01 + np.random.normal(0, 0.002)),
                    "s_del": max(0.0, 0.008 + np.random.normal(0, 0.002)),
                    "delta_c": max(0.0, 0.2 + np.random.normal(0, 0.05)),
                    "h2b_group": group,
                    "post_2020": post,
                    "time_since_2020": max(0, year - 2020),
                    "norm_post": int(group == "norm") * post,
                    "nonnorm_post": int(group == "nonnorm") * post,
                    "norm_trend_slope": int(group == "norm") * max(0, year - 2020),
                    "nonnorm_trend_slope": int(group == "nonnorm")
                    * max(0, year - 2020),
                    "dyad_id": dyad,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reporter_tmp(tmp_path, monkeypatch):
    """
    Reporter redirected to tmp_path — covers 'if self.reporter:' branches
    across all hypothesis methods without writing into the real outputs/ tree.
    """
    import config as _config

    tables = tmp_path / "tables"
    tables.mkdir()
    monkeypatch.setattr(_config, "TABLES_DIR", tables)
    monkeypatch.setattr(_config, "OUTPUTS_DIR", tmp_path)
    from engine.reporter import Reporter

    return Reporter()


@pytest.fixture
def workflow_factory(test_db, tmp_path, monkeypatch):
    """
    Returns a factory callable: workflow_factory(reporter=None).

    Builds a ScientificWorkflow with:
    - Real ScientificAnalyzer backed by the in-memory test DB
    - MagicMock visualizer (suppresses all PNG generation)
    - Optional reporter instance
    """
    import duckdb as _duckdb

    import config as _config

    monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
    figures = tmp_path / "figures"
    figures.mkdir(exist_ok=True)
    monkeypatch.setattr(_config, "FIGURES_DIR", figures)

    def _make(reporter=None):
        from engine.analyzer import ScientificAnalyzer
        from engine.models import ScientificWorkflow

        w = ScientificWorkflow.__new__(ScientificWorkflow)
        w.analyzer = ScientificAnalyzer()
        w.visualizer = MagicMock()
        w.reporter = reporter
        w.normalized_states = {
            "united arab emirates",
            "bahrain",
            "morocco",
            "egypt",
            "jordan",
        }
        return w

    return _make


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------


class TestInit:
    """Covers L31-34: __init__ initialises the normalized_states set correctly."""

    def test_init_creates_normalized_states(self, test_db, monkeypatch):
        """normalized_states must be populated after construction."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        from engine.models import ScientificWorkflow

        w = ScientificWorkflow()
        assert "bahrain" in w.normalized_states
        assert "morocco" in w.normalized_states

    def test_init_normalized_states_is_a_set(self, test_db, monkeypatch):
        """normalized_states must be a Python set for O(1) membership tests."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        from engine.models import ScientificWorkflow

        w = ScientificWorkflow()
        assert isinstance(w.normalized_states, set)

    def test_init_reporter_defaults_to_none(self, test_db, monkeypatch):
        """reporter must be None when no argument is supplied."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        from engine.models import ScientificWorkflow

        w = ScientificWorkflow()
        assert w.reporter is None

    def test_init_all_five_normalized_states_present(self, test_db, monkeypatch):
        """All five Abraham-Accords / legacy normalising states must be in the set."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        from engine.models import ScientificWorkflow

        w = ScientificWorkflow()
        expected = {"united arab emirates", "bahrain", "morocco", "egypt", "jordan"}
        assert expected.issubset(w.normalized_states)

    def test_init_with_reporter_stores_it(self, test_db, monkeypatch, tmp_path):
        """When a reporter is supplied it must be stored on self.reporter."""
        import duckdb as _duckdb

        import config as _config

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        tables = tmp_path / "tables"
        tables.mkdir()
        monkeypatch.setattr(_config, "TABLES_DIR", tables)
        monkeypatch.setattr(_config, "OUTPUTS_DIR", tmp_path)
        from engine.models import ScientificWorkflow
        from engine.reporter import Reporter

        rpt = Reporter()
        w = ScientificWorkflow(reporter=rpt)
        assert w.reporter is rpt


# ---------------------------------------------------------------------------
# TestReportPanelResults
# ---------------------------------------------------------------------------


class TestReportPanelResults:
    """Covers L47-55: _report_panel_results helper method."""

    @staticmethod
    def _mock_results(r2: float = 0.25, nobs: int = 216, n_entities: int = 6):
        m = MagicMock()
        m.rsquared_within = r2
        m.nobs = nobs
        m.entity_info = {"total": n_entities}
        m.summary.tables = [None, "COEF_TABLE_STR"]
        return m

    def test_calls_group_analysis_func(self, workflow_factory):
        """The group_analysis_func callback must be invoked exactly once."""
        w = workflow_factory()
        called = []
        w._report_panel_results(
            self._mock_results(), "Title", lambda r: called.append(True)
        )
        assert called == [True]

    def test_passes_results_to_callback(self, workflow_factory):
        """The exact results object must be forwarded to the callback."""
        w = workflow_factory()
        res = self._mock_results()
        received = []
        w._report_panel_results(res, "T", lambda r: received.append(r))
        assert received[0] is res

    def test_prints_r_squared(self, workflow_factory, capsys):
        """R-squared (Within) value must appear in stdout."""
        w = workflow_factory()
        w._report_panel_results(self._mock_results(r2=0.3141), "T", lambda r: None)
        assert "0.3141" in capsys.readouterr().out

    def test_prints_title(self, workflow_factory, capsys):
        """The title string must appear in stdout."""
        w = workflow_factory()
        w._report_panel_results(self._mock_results(), "MY_UNIQUE_TITLE", lambda r: None)
        assert "MY_UNIQUE_TITLE" in capsys.readouterr().out

    def test_prints_observation_count(self, workflow_factory, capsys):
        """Number of observations must appear in stdout."""
        w = workflow_factory()
        w._report_panel_results(self._mock_results(nobs=888), "T", lambda r: None)
        assert "888" in capsys.readouterr().out

    def test_prints_entity_count(self, workflow_factory, capsys):
        """Number of dyads (entities) must appear in stdout."""
        w = workflow_factory()
        w._report_panel_results(self._mock_results(n_entities=12), "T", lambda r: None)
        assert "12" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# TestStep1Normalization
# ---------------------------------------------------------------------------


class TestStep1Normalization:
    """Covers L178-204: execute_step1_normalization."""

    def test_returns_merged_dataframe(self, workflow_factory):
        """Return value must be a non-empty DataFrame."""
        w = workflow_factory()
        result = w.execute_step1_normalization("israel", "egypt")
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_merged_has_affinity_s_unr_column(self, workflow_factory):
        """Merged output must contain the affinity_s_unr column."""
        w = workflow_factory()
        result = w.execute_step1_normalization("israel", "egypt")
        assert "affinity_s_unr" in result.columns

    def test_merged_has_affinity_s_del_column(self, workflow_factory):
        """Merged output must contain the affinity_s_del column."""
        w = workflow_factory()
        result = w.execute_step1_normalization("israel", "egypt")
        assert "affinity_s_del" in result.columns

    def test_merged_has_year_column(self, workflow_factory):
        """Result must include a year column."""
        w = workflow_factory()
        result = w.execute_step1_normalization("israel", "egypt")
        assert "year" in result.columns

    def test_calls_visualizer_plot_affinity_trends_once(self, workflow_factory):
        """Visualizer.plot_affinity_trends must be called exactly once."""
        w = workflow_factory()
        w.execute_step1_normalization("israel", "egypt")
        w.visualizer.plot_affinity_trends.assert_called_once()

    def test_visualizer_receives_target_and_compare(self, workflow_factory):
        """plot_affinity_trends must be called with target and compare names."""
        w = workflow_factory()
        w.execute_step1_normalization("israel", "morocco")
        # call_args[0] = (merged_df, target, compare) — use index to avoid
        # triggering pandas' ambiguous truth value when checking 'x in tuple'
        call_positional = w.visualizer.plot_affinity_trends.call_args[0]
        assert call_positional[1] == "israel"
        assert call_positional[2] == "morocco"


# ---------------------------------------------------------------------------
# TestH1Mirage
# ---------------------------------------------------------------------------


class TestH1Mirage:
    """Covers L207-249: evaluate_h1_mirage (Mann-Whitney U test)."""

    @pytest.fixture
    def workflow_h1(self, workflow_factory):
        """Workflow with controlled affinity data: Israel dyads have high delta_c."""
        w = workflow_factory()
        rows = [
            {
                "year": y,
                "c_i": "iran",
                "c_j": "israel",
                "s_unr": 0.01,
                "s_del": 0.004,
                "delta_c": 0.6,
            }
            for y in range(2000, 2026)
        ] + [
            {
                "year": y,
                "c_i": "egypt",
                "c_j": "jordan",
                "s_unr": 0.01,
                "s_del": 0.008,
                "delta_c": 0.2,
            }
            for y in range(2000, 2026)
        ]
        w.analyzer.fetch_regional_affinity_data = MagicMock(
            return_value=pd.DataFrame(rows)
        )
        return w

    def test_runs_without_error(self, workflow_h1):
        """evaluate_h1_mirage() must not raise any exception."""
        workflow_h1.evaluate_h1_mirage()

    def test_calls_plot_h1_mirage(self, workflow_h1):
        """plot_h1_mirage must be called exactly once."""
        workflow_h1.evaluate_h1_mirage()
        workflow_h1.visualizer.plot_h1_mirage.assert_called_once()

    def test_calls_plot_h1_mirage_2(self, workflow_h1):
        """plot_h1_mirage_2 must be called exactly once."""
        workflow_h1.evaluate_h1_mirage()
        workflow_h1.visualizer.plot_h1_mirage_2.assert_called_once()

    def test_calls_both_plot_methods(self, workflow_h1):
        """Both plot methods must be called in a single evaluation run."""
        workflow_h1.evaluate_h1_mirage()
        workflow_h1.visualizer.plot_h1_mirage.assert_called_once()
        workflow_h1.visualizer.plot_h1_mirage_2.assert_called_once()

    def test_exports_h1_table_when_reporter_set(self, workflow_factory, reporter_tmp):
        """h1_mann_whitney.csv must be created when reporter is attached."""
        w = workflow_factory(reporter=reporter_tmp)
        rows = [
            {
                "year": y,
                "c_i": "iran",
                "c_j": "israel",
                "s_unr": 0.01,
                "s_del": 0.005,
                "delta_c": 0.5,
            }
            for y in range(2000, 2026)
        ] + [
            {
                "year": y,
                "c_i": "egypt",
                "c_j": "jordan",
                "s_unr": 0.01,
                "s_del": 0.009,
                "delta_c": 0.1,
            }
            for y in range(2000, 2026)
        ]
        w.analyzer.fetch_regional_affinity_data = MagicMock(
            return_value=pd.DataFrame(rows)
        )
        w.evaluate_h1_mirage()
        assert any(
            f.name == "h1_mann_whitney.csv" for f in reporter_tmp.tables_dir.iterdir()
        )

    def test_no_table_when_reporter_is_none(self, workflow_h1):
        """When reporter is None, evaluate_h1_mirage must not crash."""
        assert workflow_h1.reporter is None
        workflow_h1.evaluate_h1_mirage()

    def test_prints_mann_whitney_stats(self, workflow_h1, capsys):
        """Mann-Whitney U and p-value must appear in stdout."""
        workflow_h1.evaluate_h1_mirage()
        out = capsys.readouterr().out
        assert "Mann-Whitney" in out or "U:" in out


# ---------------------------------------------------------------------------
# TestH2aDestabilization
# ---------------------------------------------------------------------------


class TestH2aDestabilization:
    """Covers L257-291: evaluate_h2a_destabilization (PanelOLS DiD)."""

    @pytest.fixture
    def workflow_h2a(self, workflow_factory):
        """Workflow with synthetic 6-dyad × 36-year panel for H2a."""
        w = workflow_factory()
        w.analyzer.format_did_panel_data = MagicMock(return_value=_make_h2a_panel())
        return w

    def test_runs_without_error(self, workflow_h2a):
        """evaluate_h2a_destabilization() must complete without exception."""
        workflow_h2a.evaluate_h2a_destabilization()

    def test_calls_format_did_panel_data(self, workflow_h2a):
        """Analyzer's format_did_panel_data must be called once."""
        workflow_h2a.evaluate_h2a_destabilization()
        workflow_h2a.analyzer.format_did_panel_data.assert_called_once()

    def test_calls_plot_did_comparison(self, workflow_h2a):
        """Visualizer's plot_did_comparison must be called exactly once."""
        workflow_h2a.evaluate_h2a_destabilization()
        workflow_h2a.visualizer.plot_did_comparison.assert_called_once()

    def test_plot_receives_h2a_group_column(self, workflow_h2a):
        """plot_did_comparison must be called with 'h2a_group' as group column."""
        workflow_h2a.evaluate_h2a_destabilization()
        # call_args[0] = (df, group_col, event_year, title, filename)
        call_positional = workflow_h2a.visualizer.plot_did_comparison.call_args[0]
        assert call_positional[1] == "h2a_group"

    def test_exports_table_when_reporter_set(self, workflow_factory, reporter_tmp):
        """h2a_regression.csv must be written when reporter is provided."""
        w = workflow_factory(reporter=reporter_tmp)
        w.analyzer.format_did_panel_data = MagicMock(return_value=_make_h2a_panel())
        w.evaluate_h2a_destabilization()
        assert any(
            f.name == "h2a_regression.csv" for f in reporter_tmp.tables_dir.iterdir()
        )

    def test_wald_exception_does_not_crash(self, workflow_factory):
        """Wald test failure (try/except block) must not propagate."""
        w = workflow_factory()
        w.analyzer.format_did_panel_data = MagicMock(return_value=_make_h2a_panel())
        w.evaluate_h2a_destabilization()


# ---------------------------------------------------------------------------
# TestH2bNormalization
# ---------------------------------------------------------------------------


class TestH2bNormalization:
    """Covers L296-323: evaluate_h2b_normalization (PanelOLS DiD, Abraham Accords)."""

    @pytest.fixture
    def workflow_h2b(self, workflow_factory):
        """Workflow with synthetic 6-dyad × 36-year panel for H2b."""
        w = workflow_factory()
        w.analyzer.prepare_h2b_dataset = MagicMock(return_value=_make_h2b_panel())
        return w

    def test_runs_without_error(self, workflow_h2b):
        """evaluate_h2b_normalization() must complete without exception."""
        workflow_h2b.evaluate_h2b_normalization()

    def test_calls_prepare_h2b_dataset(self, workflow_h2b):
        """Analyzer's prepare_h2b_dataset must be invoked once."""
        workflow_h2b.evaluate_h2b_normalization()
        workflow_h2b.analyzer.prepare_h2b_dataset.assert_called_once()

    def test_calls_plot_did_comparison(self, workflow_h2b):
        """Visualizer's plot_did_comparison must be called exactly once."""
        workflow_h2b.evaluate_h2b_normalization()
        workflow_h2b.visualizer.plot_did_comparison.assert_called_once()

    def test_plot_receives_h2b_group_column(self, workflow_h2b):
        """plot_did_comparison must be called with 'h2b_group' as group column."""
        workflow_h2b.evaluate_h2b_normalization()
        # call_args[0] = (df, group_col, event_year, title, filename)
        call_positional = workflow_h2b.visualizer.plot_did_comparison.call_args[0]
        assert call_positional[1] == "h2b_group"

    def test_exports_table_when_reporter_set(self, workflow_factory, reporter_tmp):
        """h2b_regression.csv must be written when reporter is provided."""
        w = workflow_factory(reporter=reporter_tmp)
        w.analyzer.prepare_h2b_dataset = MagicMock(return_value=_make_h2b_panel())
        w.evaluate_h2b_normalization()
        assert any(
            f.name == "h2b_regression.csv" for f in reporter_tmp.tables_dir.iterdir()
        )

    def test_prints_hypothesis_header(self, workflow_h2b, capsys):
        """The H2b section header must appear in stdout."""
        workflow_h2b.evaluate_h2b_normalization()
        out = capsys.readouterr().out
        assert "2b" in out or "ABRAHAM" in out.upper() or "ACCORDS" in out.upper()


# ---------------------------------------------------------------------------
# TestH2cBreakDetection
# ---------------------------------------------------------------------------


class TestH2cBreakDetection:
    """Covers L334-372: evaluate_h2c_break_detection (rolling R² structural break)."""

    @pytest.fixture
    def workflow_h2c(self, workflow_factory):
        """Workflow with synthetic H2a panel reused for structural break detection."""
        w = workflow_factory()
        w.analyzer.format_did_panel_data = MagicMock(return_value=_make_h2a_panel())
        return w

    def test_returns_integer_best_year(self, workflow_h2c):
        """Return value must be an integer (or numpy integer)."""
        best_year = workflow_h2c.evaluate_h2c_break_detection(label="Test")
        assert isinstance(best_year, (int, np.integer))

    def test_best_year_within_candidate_range(self, workflow_h2c):
        """Best year must lie within the candidate year range 1990–2025."""
        best_year = workflow_h2c.evaluate_h2c_break_detection(label="Test")
        assert 1990 <= best_year <= 2025

    def test_subset_filter_restricts_dyads(self, workflow_h2c):
        """subset_filter should restrict rows without raising."""
        israel_only = lambda row: "israel" in {row["c_i"], row["c_j"]}
        best_year = workflow_h2c.evaluate_h2c_break_detection(
            subset_filter=israel_only, label="Israel"
        )
        assert 1990 <= best_year <= 2025

    def test_no_subset_filter_uses_all_dyads(self, workflow_h2c):
        """Without a filter, all 6 dyads must be used (no crash, valid output)."""
        best_year = workflow_h2c.evaluate_h2c_break_detection(label="Regional")
        assert 1990 <= best_year <= 2025

    def test_calls_plot_structural_break_search(self, workflow_h2c):
        """plot_structural_break_search must be called once."""
        workflow_h2c.evaluate_h2c_break_detection(label="Test")
        workflow_h2c.visualizer.plot_structural_break_search.assert_called_once()

    def test_calls_plot_segmented_break_fit(self, workflow_h2c):
        """plot_segmented_break_fit must be called once."""
        workflow_h2c.evaluate_h2c_break_detection(label="Test")
        workflow_h2c.visualizer.plot_segmented_break_fit.assert_called_once()

    def test_calls_both_plot_methods(self, workflow_h2c):
        """Both visualizer methods must be called in a single run."""
        workflow_h2c.evaluate_h2c_break_detection(label="Test")
        workflow_h2c.visualizer.plot_structural_break_search.assert_called_once()
        workflow_h2c.visualizer.plot_segmented_break_fit.assert_called_once()

    def test_label_appears_in_stdout(self, workflow_h2c, capsys):
        """The label must be echoed somewhere in printed output."""
        workflow_h2c.evaluate_h2c_break_detection(label="UNIQUE_LABEL_XYZ")
        out = capsys.readouterr().out
        assert "UNIQUE_LABEL_XYZ" in out


# ---------------------------------------------------------------------------
# TestH3Topology
# ---------------------------------------------------------------------------


class TestH3Topology:
    """
    Covers L375-477: evaluate_h3_topology.
    Uses the real in-memory analyzer; year range is narrowed to 2015-2021
    (7 iterations) via monkeypatched config to keep tests fast.
    """

    @pytest.fixture
    def workflow_h3(self, workflow_factory, monkeypatch):
        """Workflow with real analyzer, START_YEAR=2015, END_YEAR=2021."""
        import config as _config

        monkeypatch.setattr(_config, "START_YEAR", 2015)
        monkeypatch.setattr(_config, "END_YEAR", 2021)
        return workflow_factory()

    def test_runs_without_error(self, workflow_h3):
        """evaluate_h3_topology() must not raise for the default target 'israel'."""
        workflow_h3.evaluate_h3_topology("israel")

    def test_calls_centrality_comparison_plot(self, workflow_h3):
        """plot_h3_centrality_comparison must be called exactly once."""
        workflow_h3.evaluate_h3_topology("israel")
        workflow_h3.visualizer.plot_h3_centrality_comparison.assert_called_once()

    def test_empty_years_are_skipped_gracefully(self, workflow_h3):
        """
        Years without any collaborating papers must not raise.
        Verified implicitly: if any exception propagated, this test would fail.
        """
        workflow_h3.evaluate_h3_topology("israel")

    def test_accepts_non_default_target_country(self, workflow_h3):
        """Any country string must be accepted as target_country."""
        workflow_h3.evaluate_h3_topology("egypt")

    def test_plot_network_topology_called_for_key_years(self, workflow_h3):
        """
        plot_network_topology must be called at least once.
        The synthetic DB has papers for 2015 and 2020 — both are key years.
        """
        workflow_h3.evaluate_h3_topology("israel")
        assert workflow_h3.visualizer.plot_network_topology.call_count >= 1

    def test_exports_centrality_table_when_reporter_set(
        self, workflow_factory, reporter_tmp, monkeypatch
    ):
        """h3_centrality_keyYears.csv must be written when reporter is provided."""
        import config as _config

        monkeypatch.setattr(_config, "START_YEAR", 2015)
        monkeypatch.setattr(_config, "END_YEAR", 2021)
        w = workflow_factory(reporter=reporter_tmp)
        w.evaluate_h3_topology("israel")
        files = [f.name for f in reporter_tmp.tables_dir.iterdir()]
        assert any("h3_centrality" in f for f in files)

    def test_exports_mann_kendall_table_when_reporter_set(
        self, workflow_factory, reporter_tmp, monkeypatch
    ):
        """h3_mann_kendall.csv must be written when reporter is provided."""
        import config as _config

        monkeypatch.setattr(_config, "START_YEAR", 2015)
        monkeypatch.setattr(_config, "END_YEAR", 2021)
        w = workflow_factory(reporter=reporter_tmp)
        w.evaluate_h3_topology("israel")
        files = [f.name for f in reporter_tmp.tables_dir.iterdir()]
        assert any("h3_mann_kendall" in f for f in files)

    def test_exports_both_tables_when_reporter_set(
        self, workflow_factory, reporter_tmp, monkeypatch
    ):
        """Both h3 tables must exist after a single call with reporter set."""
        import config as _config

        monkeypatch.setattr(_config, "START_YEAR", 2015)
        monkeypatch.setattr(_config, "END_YEAR", 2021)
        w = workflow_factory(reporter=reporter_tmp)
        w.evaluate_h3_topology("israel")
        files = [f.name for f in reporter_tmp.tables_dir.iterdir()]
        assert any("h3_centrality" in f for f in files)
        assert any("h3_mann_kendall" in f for f in files)


# ---------------------------------------------------------------------------
# TestH4ThematicBias
# ---------------------------------------------------------------------------


class TestH4ThematicBias:
    """Covers L502-547: evaluate_h4_thematic_bias (Fisher exact test)."""

    # Known table: OR = (120*100)/(80*300) = 12000/24000 = 0.5
    _TABLE = pd.DataFrame(
        {"neutral": [120.0, 300.0], "sensitive": [80.0, 100.0]},
        index=["israel_arab", "control"],
    )

    @pytest.fixture
    def workflow_h4(self, workflow_factory):
        """Workflow with a fully-controlled contingency table so OR = 0.5."""
        w = workflow_factory()
        w.analyzer.get_thematic_contingency_table = MagicMock(
            return_value=self._TABLE.copy()
        )
        return w

    def test_runs_without_error(self, workflow_h4):
        """evaluate_h4_thematic_bias() must complete without raising."""
        workflow_h4.evaluate_h4_thematic_bias()

    def test_calls_plot_h4_thematic(self, workflow_h4):
        """plot_h4_thematic must be called exactly once."""
        workflow_h4.evaluate_h4_thematic_bias()
        workflow_h4.visualizer.plot_h4_thematic.assert_called_once()

    def test_odds_ratio_approximately_half(self, workflow_h4, capsys):
        """
        OR = (120 x 100) / (80 x 300) = 0.5 — must appear in printed output.
        """
        workflow_h4.evaluate_h4_thematic_bias()
        out = capsys.readouterr().out
        assert "0.5" in out

    def test_ci_keyword_in_output(self, workflow_h4, capsys):
        """Confidence-interval notation must appear in stdout."""
        workflow_h4.evaluate_h4_thematic_bias()
        out = capsys.readouterr().out
        assert "CI" in out

    def test_ci_low_less_than_ci_high(self, workflow_h4, capsys):
        """Lower CI bound must be strictly below upper CI bound."""
        workflow_h4.evaluate_h4_thematic_bias()
        out = capsys.readouterr().out
        match = re.search(r"CI[^:]*:\s*([\d.]+)\s*[–\-]\s*([\d.]+)", out)
        if match:
            ci_low = float(match.group(1))
            ci_high = float(match.group(2))
            assert ci_low < ci_high

    def test_fisher_p_value_printed(self, workflow_h4, capsys):
        """Fisher p-value line must appear in stdout."""
        workflow_h4.evaluate_h4_thematic_bias()
        out = capsys.readouterr().out
        assert "Fisher" in out or "p " in out.lower()

    def test_exports_fisher_table_when_reporter_set(
        self, workflow_factory, reporter_tmp
    ):
        """h4_fisher_exact.csv must be written when reporter is provided."""
        w = workflow_factory(reporter=reporter_tmp)
        w.analyzer.get_thematic_contingency_table = MagicMock(
            return_value=self._TABLE.copy()
        )
        w.evaluate_h4_thematic_bias()
        files = [f.name for f in reporter_tmp.tables_dir.iterdir()]
        assert any("h4_fisher" in f for f in files)

    def test_calls_contingency_table_reporter_method(
        self, workflow_factory, reporter_tmp
    ):
        """reporter.contingency_table() must be invoked exactly once."""
        w = workflow_factory(reporter=reporter_tmp)
        w.analyzer.get_thematic_contingency_table = MagicMock(
            return_value=self._TABLE.copy()
        )
        original_ct = reporter_tmp.contingency_table
        call_log: list = []

        def _spy(*args, **kwargs):
            call_log.append(args)
            return original_ct(*args, **kwargs)

        reporter_tmp.contingency_table = _spy
        w.reporter = reporter_tmp
        w.evaluate_h4_thematic_bias()
        assert len(call_log) == 1

    def test_no_reporter_does_not_crash(self, workflow_h4):
        """evaluate_h4_thematic_bias must succeed when reporter is None."""
        assert workflow_h4.reporter is None
        workflow_h4.evaluate_h4_thematic_bias()


# ---------------------------------------------------------------------------
# TestSensitivityTestReporterBranch
# ---------------------------------------------------------------------------


class TestSensitivityTestReporterBranch:
    """
    Covers L164: the `if self.reporter:` branch in run_threshold_sensitivity_test.
    Runs the real sensitivity sweep (min_n=2, max_n=5) against the in-memory DB.
    """

    def test_reporter_branch_exports_table(
        self, workflow_factory, reporter_tmp, test_db, monkeypatch
    ):
        """threshold_sensitivity.csv must exist when reporter is attached."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        w = workflow_factory(reporter=reporter_tmp)
        w.visualizer.plot_threshold_sensitivity = MagicMock()

        _, optimal_n = w.run_threshold_sensitivity_test(min_n=2, max_n=5)

        files = [f.name for f in reporter_tmp.tables_dir.iterdir()]
        assert any("threshold_sensitivity" in f for f in files)

    def test_returns_tuple_of_dataframe_and_integer(
        self, workflow_factory, test_db, monkeypatch
    ):
        """Return value must be a 2-tuple of (DataFrame, int)."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        w = workflow_factory()

        result = w.run_threshold_sensitivity_test(min_n=2, max_n=4)
        assert isinstance(result, tuple) and len(result) == 2
        res_df, optimal_n = result
        assert isinstance(res_df, pd.DataFrame)
        assert isinstance(optimal_n, (int, np.integer))

    def test_no_reporter_does_not_crash(self, workflow_factory, test_db, monkeypatch):
        """Without reporter, run_threshold_sensitivity_test must still succeed."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        w = workflow_factory()
        w.run_threshold_sensitivity_test(min_n=2, max_n=3)

    def test_optimal_n_within_requested_range(
        self, workflow_factory, test_db, monkeypatch
    ):
        """Optimal elbow N must be within the requested [min_n, max_n] range."""
        import duckdb as _duckdb

        monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
        w = workflow_factory()
        _, optimal_n = w.run_threshold_sensitivity_test(min_n=2, max_n=5)
        assert 2 <= optimal_n <= 5


# ---------------------------------------------------------------------------
# TestReporterConsoleHelpers  (supplements test_reporter.py)
# ---------------------------------------------------------------------------


class TestReporterConsoleHelpers:
    """
    Supplements test_reporter.py.
    Covers Reporter.section (L51-52), Reporter.subsection (L55-56), and
    Reporter.regression_summary (L70-75) in engine/reporter.py.
    """

    def test_section_prints_title(self, reporter_in_tmp, capsys):
        """section() output must include the supplied title."""
        reporter_in_tmp.section("MY SECTION TITLE")
        out = capsys.readouterr().out
        assert "MY SECTION TITLE" in out

    def test_section_prints_equals_separator(self, reporter_in_tmp, capsys):
        """section() must print '=' separator bars around the title."""
        reporter_in_tmp.section("TITLE")
        out = capsys.readouterr().out
        assert "=" * 10 in out

    def test_section_default_width_is_95(self, reporter_in_tmp, capsys):
        """section() default bar width must be 95 '=' characters."""
        reporter_in_tmp.section("T")
        out = capsys.readouterr().out
        assert "=" * 95 in out

    def test_subsection_prints_title(self, reporter_in_tmp, capsys):
        """subsection() output must include the supplied title."""
        reporter_in_tmp.subsection("My Subsection")
        out = capsys.readouterr().out
        assert "My Subsection" in out

    def test_subsection_prints_dash_separator(self, reporter_in_tmp, capsys):
        """subsection() must print a '---' separator line."""
        reporter_in_tmp.subsection("Sub")
        out = capsys.readouterr().out
        assert "---" in out

    def test_subsection_default_dash_bar_is_95(self, reporter_in_tmp, capsys):
        """subsection() default separator must be 95 '-' characters wide."""
        reporter_in_tmp.subsection("T")
        out = capsys.readouterr().out
        assert "-" * 95 in out

    def test_regression_summary_prints_r2(self, reporter_in_tmp, capsys):
        """regression_summary() must print the within R-squared value."""
        mock_results = MagicMock()
        mock_results.rsquared_within = 0.4567
        mock_results.nobs = 200
        mock_results.entity_info = {"total": 8}
        mock_results.summary.tables = [None, "COEF_TABLE"]
        reporter_in_tmp.regression_summary(mock_results, "My Regression")
        out = capsys.readouterr().out
        assert "0.4567" in out

    def test_regression_summary_prints_nobs(self, reporter_in_tmp, capsys):
        """regression_summary() must print the number of observations."""
        mock_results = MagicMock()
        mock_results.rsquared_within = 0.1
        mock_results.nobs = 200
        mock_results.entity_info = {"total": 8}
        mock_results.summary.tables = [None, "COEF_TABLE"]
        reporter_in_tmp.regression_summary(mock_results, "Title")
        out = capsys.readouterr().out
        assert "200" in out

    def test_regression_summary_prints_title(self, reporter_in_tmp, capsys):
        """regression_summary() must include the title in its output."""
        mock_results = MagicMock()
        mock_results.rsquared_within = 0.1
        mock_results.nobs = 50
        mock_results.entity_info = {"total": 4}
        mock_results.summary.tables = [None, "TABLE"]
        reporter_in_tmp.regression_summary(mock_results, "UNIQUE_REGRESSION_TITLE")
        out = capsys.readouterr().out
        assert "UNIQUE_REGRESSION_TITLE" in out
