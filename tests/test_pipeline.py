"""
test_pipeline.py
----------------
Two test groups:

1. DatabaseBuilder.normalise() — pipeline/database.py
   - Multi-value column explosion (all_countries, subject_areas)
   - Country normalisation (Türkiye → Turkey, lowercasing, strip)
   - Column removal from the articles table
   - Baseline country lowercasing
   - Row count correctness in all output tables

2. ResearchPipeline integration — engine/orchestrator.py
   - Dry run: Load → Process → Export flow
   - Reporter creates run_metadata.json
   - H1 / H4 smoke tests on synthetic data
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


@pytest.fixture
def builder_in_tmp(tmp_path, monkeypatch):
    """
    DatabaseBuilder with all file paths redirected to tmp_path.
    Injects synthetic CSVs and returns a configured builder instance.
    """
    import config as _config

    # Redirect all config paths to tmp_path
    monkeypatch.setattr(_config, "MASTER_RAW_FILE", tmp_path / "master.csv")
    monkeypatch.setattr(_config, "BASELINE_FILE", tmp_path / "baseline.csv")
    monkeypatch.setattr(_config, "MASTER_MAIN_FILE", tmp_path / "master_main.csv")
    monkeypatch.setattr(
        _config, "MASTER_COUNTRIES_FILE", tmp_path / "master_countries.csv"
    )
    monkeypatch.setattr(
        _config, "MASTER_SUBJECTS_FILE", tmp_path / "master_subjects.csv"
    )
    monkeypatch.setattr(_config, "PROCESSED_DIR", tmp_path)

    # Synthetic master.csv
    master = pd.DataFrame(
        [
            {
                "eid": "e1",
                "title": "Paper One",
                "doi": "10.1/a",
                "year": 2015,
                "journal": "Journal A",
                "all_countries": "Israel; Egypt",
                "subject_areas": "Engineering|Medicine",
            },
            {
                "eid": "e2",
                "title": "Paper Two",
                "doi": "10.1/b",
                "year": 2020,
                "journal": "Journal B",
                "all_countries": "Türkiye; Iran",
                "subject_areas": "Physics and Astronomy",
            },
            {
                "eid": "e3",
                "title": "Paper Three",
                "doi": "10.1/c",
                "year": 2021,
                "journal": "Journal C",
                "all_countries": "Israel",  # single country (edge case)
                "subject_areas": "Social Sciences",
            },
        ]
    )
    master.to_csv(tmp_path / "master.csv", index=False)

    # Synthetic baseline.csv
    baseline = pd.DataFrame(
        [
            {"country": "ISRAEL", "year": 2015, "total_output": 5000},
            {"country": "Egypt", "year": 2015, "total_output": 1000},
            {"country": "Türkiye", "year": 2020, "total_output": 3000},
        ]
    )
    baseline.to_csv(tmp_path / "baseline.csv", index=False)

    from pipeline.database import DatabaseBuilder

    b = DatabaseBuilder()
    b.master_raw = _config.MASTER_RAW_FILE
    b.baseline = _config.BASELINE_FILE
    b.master_main = _config.MASTER_MAIN_FILE
    b.master_countries = _config.MASTER_COUNTRIES_FILE
    b.master_subjects = _config.MASTER_SUBJECTS_FILE
    return b


class TestCountriesExplosion:
    """all_countries column is split on '; ' and exploded to one row per country."""

    @pytest.fixture(autouse=True)
    def run_normalise(self, builder_in_tmp):
        self.stats = builder_in_tmp.normalise()
        import config as _config

        self.countries = pd.read_csv(_config.MASTER_COUNTRIES_FILE)

    def test_e1_has_two_country_rows(self):
        assert len(self.countries[self.countries["eid"] == "e1"]) == 2

    def test_e1_contains_israel(self):
        vals = self.countries[self.countries["eid"] == "e1"]["country"].tolist()
        assert "israel" in vals

    def test_e1_contains_egypt(self):
        vals = self.countries[self.countries["eid"] == "e1"]["country"].tolist()
        assert "egypt" in vals

    def test_turkiye_normalised_to_turkey(self):
        vals = self.countries[self.countries["eid"] == "e2"]["country"].tolist()
        assert "turkey" in vals
        assert "türkiye" not in vals

    def test_all_countries_are_lowercase(self):
        for val in self.countries["country"].dropna():
            assert val == val.lower(), f"Not lowercase: '{val}'"

    def test_all_countries_stripped(self):
        for val in self.countries["country"].dropna():
            assert val == val.strip(), f"Not stripped: '{val}'"

    def test_total_country_rows_correct(self):
        # e1: 2 countries, e2: 2 countries, e3: 1 country → 5 rows
        assert len(self.countries) == 5


class TestSubjectsExplosion:
    """subject_areas column is split on '|' and exploded to one row per subject."""

    @pytest.fixture(autouse=True)
    def run_normalise(self, builder_in_tmp):
        builder_in_tmp.normalise()
        import config as _config

        self.subjects = pd.read_csv(_config.MASTER_SUBJECTS_FILE)

    def test_e1_has_two_subject_rows(self):
        assert len(self.subjects[self.subjects["eid"] == "e1"]) == 2

    def test_e1_contains_engineering(self):
        vals = self.subjects[self.subjects["eid"] == "e1"]["subject"].tolist()
        assert "engineering" in vals

    def test_e1_contains_medicine(self):
        vals = self.subjects[self.subjects["eid"] == "e1"]["subject"].tolist()
        assert "medicine" in vals

    def test_e2_has_one_subject_row(self):
        assert len(self.subjects[self.subjects["eid"] == "e2"]) == 1

    def test_all_subjects_lowercase(self):
        for val in self.subjects["subject"].dropna():
            assert val == val.lower(), f"Not lowercase: '{val}'"

    def test_total_subject_rows_correct(self):
        # e1: 2, e2: 1, e3: 1 → 4
        assert len(self.subjects) == 4


class TestArticlesClean:
    """master_main.csv must not contain all_countries or subject_areas columns."""

    @pytest.fixture(autouse=True)
    def run_normalise(self, builder_in_tmp):
        builder_in_tmp.normalise()
        import config as _config

        self.articles = pd.read_csv(_config.MASTER_MAIN_FILE)

    def test_all_countries_column_removed(self):
        assert "all_countries" not in self.articles.columns

    def test_subject_areas_column_removed(self):
        assert "subject_areas" not in self.articles.columns

    def test_eid_column_preserved(self):
        assert "eid" in self.articles.columns

    def test_year_column_preserved(self):
        assert "year" in self.articles.columns

    def test_row_count_matches_input(self):
        assert len(self.articles) == 3


class TestBaselineNormalisation:
    """Baseline country names must be lowercased."""

    @pytest.fixture(autouse=True)
    def run_normalise(self, builder_in_tmp):
        builder_in_tmp.normalise()
        import config as _config

        self.baseline = pd.read_csv(_config.BASELINE_FILE)

    def test_all_countries_lowercase(self):
        for val in self.baseline["country"]:
            assert val == val.lower(), f"Not lowercase: '{val}'"

    def test_israel_lowercase(self):
        assert "israel" in self.baseline["country"].tolist()

    def test_total_output_preserved(self):
        row = self.baseline[self.baseline["country"] == "israel"].iloc[0]
        assert row["total_output"] == 5000


class TestNormaliseStats:
    """normalise() must return correct row counts in the stats dict."""

    def test_stats_keys_correct(self, builder_in_tmp):
        stats = builder_in_tmp.normalise()
        assert set(stats.keys()) == {"articles", "countries", "subjects", "baseline"}

    def test_articles_count(self, builder_in_tmp):
        stats = builder_in_tmp.normalise()
        assert stats["articles"] == 3

    def test_countries_count(self, builder_in_tmp):
        stats = builder_in_tmp.normalise()
        assert stats["countries"] == 5

    def test_subjects_count(self, builder_in_tmp):
        stats = builder_in_tmp.normalise()
        assert stats["subjects"] == 4

    def test_baseline_count(self, builder_in_tmp):
        stats = builder_in_tmp.normalise()
        assert stats["baseline"] == 3


# ---------------------------------------------------------------------------
# ResearchPipeline integration tests (engine/orchestrator.py)
# ---------------------------------------------------------------------------


class TestResearchPipelineInit:
    """ResearchPipeline can be constructed and exposes the correct attributes."""

    def test_pipeline_has_analyst_attribute(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        assert hasattr(pipeline, "analyst")

    def test_pipeline_analyzer_alias_points_to_analyst(self, research_pipeline_factory):
        """Backward-compat: pipeline.analyzer must be the same object as pipeline.analyst."""
        pipeline = research_pipeline_factory()
        assert pipeline.analyzer is pipeline.analyst

    def test_pipeline_has_visualizer(self, research_pipeline_factory):
        assert hasattr(research_pipeline_factory(), "visualizer")

    def test_pipeline_reporter_none_by_default(self, research_pipeline_factory):
        assert research_pipeline_factory().reporter is None

    def test_pipeline_with_reporter_stores_it(
        self, research_pipeline_factory, reporter_in_tmp
    ):
        pipeline = research_pipeline_factory(reporter=reporter_in_tmp)
        assert pipeline.reporter is reporter_in_tmp

    def test_normalized_states_is_set(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        assert isinstance(pipeline.normalized_states, set)

    def test_normalized_states_has_five_members(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        expected = {"united arab emirates", "bahrain", "morocco", "egypt", "jordan"}
        assert expected.issubset(pipeline.normalized_states)


class TestResearchPipelineDryRun:
    """
    Dry run of the full pipeline using the in-memory synthetic dataset.

    Verifies the Load → Process → Export flow:
    1. Calibration: run_threshold_sensitivity_test returns (DataFrame, int)
    2. Step 1: execute_step1_normalization returns a merged affinity DataFrame
    3. Reporter: save_run_metadata creates run_metadata.json

    All visualiser calls are suppressed (MagicMock); only data-flow assertions
    are made so that tests remain fast and stateless.
    """

    def test_calibration_returns_dataframe_and_int(self, research_pipeline_factory):
        """Load → run_threshold_sensitivity_test → (DataFrame, int)."""
        pipeline = research_pipeline_factory()
        res_df, optimal_n = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=5)
        assert isinstance(res_df, pd.DataFrame)
        assert isinstance(optimal_n, (int, np.integer))

    def test_calibration_row_count_correct(self, research_pipeline_factory):
        """One row per candidate threshold value."""
        pipeline = research_pipeline_factory()
        res_df, _ = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=6)
        assert len(res_df) == 5  # N ∈ {2, 3, 4, 5, 6}

    def test_calibration_required_columns(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        res_df, _ = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=4)
        for col in [
            "n_threshold",
            "israel_involved_c_star",
            "non_israel_c_star",
            "ratio_isr_non",
            "growth_isr",
        ]:
            assert col in res_df.columns

    def test_calibration_updates_config_deliberate_n(self, research_pipeline_factory):
        """Side-effect: config.DELIBERATE_N must be set to optimal_n."""
        pipeline = research_pipeline_factory()
        _, optimal_n = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=4)
        assert config.DELIBERATE_N == optimal_n

    def test_step1_normalization_returns_dataframe(self, research_pipeline_factory):
        """Process: execute_step1_normalization returns non-empty DataFrame."""
        pipeline = research_pipeline_factory()
        result = pipeline.execute_step1_normalization("israel", "egypt")
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_step1_affinity_s_unr_column_present(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        result = pipeline.execute_step1_normalization("israel", "egypt")
        assert "affinity_s_unr" in result.columns

    def test_step1_affinity_s_del_column_present(self, research_pipeline_factory):
        pipeline = research_pipeline_factory()
        result = pipeline.execute_step1_normalization("israel", "egypt")
        assert "affinity_s_del" in result.columns

    def test_step1_calls_visualizer(self, research_pipeline_factory):
        """Export step: visualizer must be called after processing."""
        pipeline = research_pipeline_factory()
        pipeline.execute_step1_normalization("israel", "morocco")
        pipeline.visualizer.plot_affinity_trends.assert_called_once()

    def test_reporter_creates_metadata_file(
        self, research_pipeline_factory, reporter_in_tmp, tmp_path, monkeypatch
    ):
        """Export: Reporter.save_run_metadata must write run_metadata.json."""
        import config as _config
        monkeypatch.setattr(_config, "OUTPUTS_DIR", tmp_path)

        pipeline = research_pipeline_factory(reporter=reporter_in_tmp)
        reporter_in_tmp.save_run_metadata(
            pipeline.analyst.get_basic_metrics()
        )
        assert (tmp_path / "run_metadata.json").exists()

    def test_metadata_json_is_valid(
        self, research_pipeline_factory, reporter_in_tmp, tmp_path, monkeypatch
    ):
        """Metadata file must be valid JSON with required keys."""
        import json
        import config as _config
        monkeypatch.setattr(_config, "OUTPUTS_DIR", tmp_path)

        pipeline = research_pipeline_factory(reporter=reporter_in_tmp)
        reporter_in_tmp.save_run_metadata()
        data = json.loads((tmp_path / "run_metadata.json").read_text())
        for key in ["timestamp", "python_version", "pandas_version"]:
            assert key in data


class TestResearchPipelineH1H4Smoke:
    """
    Smoke tests: evaluate_h1_mirage and evaluate_h4_thematic_bias must
    complete without raising on the synthetic dataset.
    """

    def test_h1_runs_without_error(self, research_pipeline_factory, monkeypatch):
        """Provide controlled affinity data so H1 (Mann-Whitney) always converges."""
        from unittest.mock import MagicMock

        pipeline = research_pipeline_factory()
        rows = [
            {"year": y, "c_i": "iran", "c_j": "israel",
             "s_unr": 0.01, "s_del": 0.004, "delta_c": 0.6}
            for y in range(2000, 2026)
        ] + [
            {"year": y, "c_i": "egypt", "c_j": "jordan",
             "s_unr": 0.01, "s_del": 0.009, "delta_c": 0.1}
            for y in range(2000, 2026)
        ]
        pipeline.analyst.fetch_regional_affinity_data = MagicMock(
            return_value=pd.DataFrame(rows)
        )
        pipeline.evaluate_h1_mirage()

    def test_h4_runs_without_error(self, research_pipeline_factory):
        """Provide a valid 2×2 contingency table so Fisher's test always runs."""
        pipeline = research_pipeline_factory()
        table = pd.DataFrame(
            {"neutral": [120.0, 300.0], "sensitive": [80.0, 100.0]},
            index=["israel_arab", "control"],
        )
        pipeline.analyst.get_thematic_contingency_table = MagicMock(
            return_value=table
        )
        pipeline.evaluate_h4_thematic_bias()
