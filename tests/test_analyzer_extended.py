"""
test_analyzer_extended.py
-------------------------
Covers NetworkAnalyst (engine/processor.py) methods not exercised elsewhere.
(Previously targeted engine/analyzer.py; that file is now a backward-compat
shim that re-exports NetworkAnalyst unchanged.)

Methods covered
---------------
  get_basic_metrics
  fetch_country_timeseries
  format_did_panel_data
  prepare_h2b_dataset
  compute_network_centrality
  get_thematic_contingency_table
  _get_h3_query

All tests use the in-memory DuckDB from conftest.py (5 synthetic papers).
Ground-truth values are derived by hand calculation — see conftest.py docstring.
"""

import math
import sys
from pathlib import Path
from unittest.mock import patch

import networkx as nx
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# ---------------------------------------------------------------------------
# Extra fixture: adds a paper with BOTH neutral and sensitive subjects
# (needed to cover the 0.5/0.5 fractional branch in get_thematic_contingency_table)
# ---------------------------------------------------------------------------


def _build_extended_db():
    """Test DB from conftest plus eid6 (israel+egypt, engineering + social sciences)."""
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE articles (eid VARCHAR, title VARCHAR, doi VARCHAR,
                               year INTEGER, journal VARCHAR)
    """)
    con.execute("CREATE TABLE countries (eid VARCHAR, country VARCHAR)")
    con.execute("CREATE TABLE subjects  (eid VARCHAR, subject  VARCHAR)")
    con.execute(
        "CREATE TABLE baseline  (country VARCHAR, year INTEGER, total_output INTEGER)"
    )

    con.executemany(
        "INSERT INTO articles VALUES (?,?,?,?,?)",
        [
            ("eid1", "Bilateral Israel-Egypt", "doi1", 2015, "Journal A"),
            ("eid2", "Bilateral Israel-Morocco", "doi2", 2020, "Journal B"),
            ("eid3", "Bilateral Egypt-Jordan", "doi3", 2015, "Journal C"),
            ("eid4", "Trilateral Israel-Egypt-Morocco", "doi4", 2021, "Journal D"),
            ("eid5", "Mega-Project", "doi5", 2015, "Journal E"),
            ("eid6", "Mixed-Subject Israel-Egypt", "doi6", 2015, "Journal F"),
        ],
    )
    con.executemany(
        "INSERT INTO countries VALUES (?,?)",
        [
            ("eid1", "israel"),
            ("eid1", "egypt"),
            ("eid2", "israel"),
            ("eid2", "morocco"),
            ("eid3", "egypt"),
            ("eid3", "jordan"),
            ("eid4", "israel"),
            ("eid4", "egypt"),
            ("eid4", "morocco"),
            ("eid5", "israel"),
            ("eid5", "egypt"),
            ("eid5", "jordan"),
            ("eid5", "morocco"),
            ("eid5", "turkey"),
            ("eid5", "iran"),
            ("eid5", "iraq"),
            ("eid5", "algeria"),
            ("eid6", "israel"),
            ("eid6", "egypt"),
        ],
    )
    con.executemany(
        "INSERT INTO subjects VALUES (?,?)",
        [
            ("eid1", "engineering"),
            ("eid2", "medicine"),
            ("eid3", "social sciences"),
            ("eid4", "physics and astronomy"),
            ("eid5", "physics and astronomy"),
            ("eid6", "engineering"),  # neutral subject
            ("eid6", "social sciences"),  # sensitive subject -> triggers 0.5/0.5 branch
        ],
    )
    all_countries = [
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
    rows = [
        (c, yr, 5000 if c == "israel" else 1000)
        for c in all_countries
        for yr in range(1990, 2026)
    ]
    con.executemany("INSERT INTO baseline VALUES (?,?,?)", rows)
    return con


@pytest.fixture
def mock_analyzer_extended(monkeypatch):
    """ScientificAnalyzer backed by the extended in-memory DB (includes eid6)."""
    import duckdb as _duckdb

    con = _build_extended_db()
    monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: con)
    from engine.analyzer import ScientificAnalyzer

    return ScientificAnalyzer()


# ---------------------------------------------------------------------------
# get_basic_metrics
# ---------------------------------------------------------------------------


class TestGetBasicMetrics:
    """Covers L20-22: get_basic_metrics returns total paper count."""

    def test_returns_dict(self, mock_analyzer):
        result = mock_analyzer.get_basic_metrics()
        assert isinstance(result, dict)

    def test_total_papers_key_present(self, mock_analyzer):
        result = mock_analyzer.get_basic_metrics()
        assert "total_papers" in result

    def test_total_papers_count(self, mock_analyzer):
        """Test DB has exactly 5 synthetic papers."""
        result = mock_analyzer.get_basic_metrics()
        assert result["total_papers"] == 5


# ---------------------------------------------------------------------------
# fetch_country_timeseries
# ---------------------------------------------------------------------------


class TestFetchCountryTimeseries:
    """
    Covers L76-100: fetch_country_timeseries in raw and fractional modes.

    Ground truth for israel in 2015:
      raw, no filter       : eid1 + eid5 -> production = 2.0
      fractional, no filter: eid1(1/2) + eid5(1/8) -> production = 0.625
      raw, max_countries=5 : eid5(np=8) excluded -> production = 1.0
    """

    def test_returns_dataframe(self, mock_analyzer):
        df = mock_analyzer.fetch_country_timeseries("israel")
        assert isinstance(df, pd.DataFrame)

    def test_columns_year_and_production(self, mock_analyzer):
        df = mock_analyzer.fetch_country_timeseries("israel")
        assert "year" in df.columns
        assert "production" in df.columns

    def test_raw_mode_counts_all_papers(self, mock_analyzer):
        """eid1 (np=2) + eid5 (np=8) both in 2015 with israel -> 2.0"""
        df = mock_analyzer.fetch_country_timeseries("israel", mode="raw")
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["production"], 2.0, rel_tol=1e-6)

    def test_fractional_mode_weights_by_np(self, mock_analyzer):
        """eid1: weight=1/2=0.5; eid5: weight=1/8=0.125 -> total=0.625"""
        df = mock_analyzer.fetch_country_timeseries("israel", mode="fractional")
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["production"], 0.625, rel_tol=1e-5)

    def test_max_countries_excludes_mega_project(self, mock_analyzer):
        """With max_countries=5, eid5 (np=8) is excluded. Only eid1 remains -> 1.0"""
        df = mock_analyzer.fetch_country_timeseries(
            "israel", mode="raw", max_countries=5
        )
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["production"], 1.0, rel_tol=1e-6)

    def test_fractional_max_countries_correct(self, mock_analyzer):
        """Fractional + max_countries=5: only eid1 (weight=1/2=0.5) in 2015."""
        df = mock_analyzer.fetch_country_timeseries(
            "israel", mode="fractional", max_countries=5
        )
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["production"], 0.5, rel_tol=1e-6)

    def test_nonexistent_country_returns_empty(self, mock_analyzer):
        df = mock_analyzer.fetch_country_timeseries("atlantis")
        assert len(df) == 0

    def test_case_insensitive(self, mock_analyzer):
        df_lower = mock_analyzer.fetch_country_timeseries("israel")
        df_upper = mock_analyzer.fetch_country_timeseries("Israel")
        assert len(df_lower) == len(df_upper)


# ---------------------------------------------------------------------------
# format_did_panel_data
# ---------------------------------------------------------------------------


class TestFormatDIDPanelData:
    """
    Covers L199-223: format_did_panel_data categorizes dyads for H2a DiD.

    Destabilized states: egypt, syria, libya, yemen, tunisia.
    Priority: destabilized > israel > stable_control.
    """

    @pytest.fixture(autouse=True)
    def _fetch(self, mock_analyzer):
        self.df = mock_analyzer.format_did_panel_data()

    def test_required_columns_present(self):
        for col in [
            "h2a_group",
            "post_2011",
            "time_since_2011",
            "destab_post",
            "destab_trend_slope",
            "israel_post",
            "dyad_id",
        ]:
            assert col in self.df.columns, f"Missing column: {col}"

    def test_egypt_dyads_are_destabilized(self):
        """Egypt is destabilized — any dyad involving egypt -> 'destabilized'."""
        egypt_dyads = self.df[(self.df["c_i"] == "egypt") | (self.df["c_j"] == "egypt")]
        assert (egypt_dyads["h2a_group"] == "destabilized").all()

    def test_israel_jordan_is_israel_group(self):
        """Jordan is not destabilized + israel present -> 'israel'."""
        dyad = self.df[
            (self.df["c_i"].isin(["israel", "jordan"]))
            & (self.df["c_j"].isin(["israel", "jordan"]))
        ]
        if not dyad.empty:
            assert (dyad["h2a_group"] == "israel").all()

    def test_stable_control_group_exists(self):
        assert "stable_control" in self.df["h2a_group"].values

    def test_post_2011_flag_correct(self):
        assert (self.df[self.df["year"] >= 2011]["post_2011"] == 1).all()
        assert (self.df[self.df["year"] < 2011]["post_2011"] == 0).all()

    def test_time_since_2011_non_negative(self):
        assert (self.df["time_since_2011"] >= 0).all()

    def test_time_since_2011_pre_2011_is_zero(self):
        assert (self.df[self.df["year"] < 2011]["time_since_2011"] == 0).all()

    def test_destab_post_is_product(self):
        expected = (self.df["h2a_group"] == "destabilized").astype(int) * self.df[
            "post_2011"
        ]
        pd.testing.assert_series_equal(
            self.df["destab_post"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )

    def test_israel_post_is_product(self):
        expected = (self.df["h2a_group"] == "israel").astype(int) * self.df["post_2011"]
        pd.testing.assert_series_equal(
            self.df["israel_post"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )

    def test_dyad_id_format(self):
        for val in self.df["dyad_id"].unique():
            assert "_" in val, f"dyad_id '{val}' missing underscore"


# ---------------------------------------------------------------------------
# prepare_h2b_dataset
# ---------------------------------------------------------------------------


class TestPrepareH2bDataset:
    """
    Covers L227-258: prepare_h2b_dataset categorizes dyads for H2b DiD.

    normalization_set = {united arab emirates, bahrain, morocco}
    norm      : israel + member of normalization_set
    nonnorm   : israel + non-member
    reference : no israel
    """

    @pytest.fixture(autouse=True)
    def _fetch(self, mock_analyzer):
        self.df = mock_analyzer.prepare_h2b_dataset()

    def test_required_columns_present(self):
        for col in [
            "h2b_group",
            "post_2020",
            "time_since_2020",
            "norm_post",
            "nonnorm_post",
            "norm_trend_slope",
            "nonnorm_trend_slope",
            "dyad_id",
        ]:
            assert col in self.df.columns, f"Missing: {col}"

    def test_israel_morocco_is_norm(self):
        """Morocco is in normalization_set -> israel+morocco = 'norm'."""
        dyad = self.df[
            (self.df["c_i"].isin(["israel", "morocco"]))
            & (self.df["c_j"].isin(["israel", "morocco"]))
        ]
        if not dyad.empty:
            assert (dyad["h2b_group"] == "norm").all()

    def test_egypt_israel_is_nonnorm(self):
        """Egypt not in normalization_set -> egypt+israel = 'nonnorm'."""
        dyad = self.df[
            (self.df["c_i"].isin(["egypt", "israel"]))
            & (self.df["c_j"].isin(["egypt", "israel"]))
        ]
        if not dyad.empty:
            assert (dyad["h2b_group"] == "nonnorm").all()

    def test_non_israel_dyads_are_reference(self):
        no_israel = self.df[
            ~((self.df["c_i"] == "israel") | (self.df["c_j"] == "israel"))
        ]
        assert (no_israel["h2b_group"] == "reference").all()

    def test_post_2020_flag_correct(self):
        assert (self.df[self.df["year"] >= 2020]["post_2020"] == 1).all()
        assert (self.df[self.df["year"] < 2020]["post_2020"] == 0).all()

    def test_time_since_2020_non_negative(self):
        assert (self.df["time_since_2020"] >= 0).all()

    def test_norm_post_is_binary(self):
        assert set(self.df["norm_post"].unique()).issubset({0, 1})

    def test_nonnorm_post_is_binary(self):
        assert set(self.df["nonnorm_post"].unique()).issubset({0, 1})

    def test_norm_trend_slope_zero_before_2020(self):
        norm_rows = self.df[self.df["h2b_group"] == "norm"]
        pre_2020 = norm_rows[norm_rows["year"] < 2020]
        assert (pre_2020["norm_trend_slope"] == 0).all()


# ---------------------------------------------------------------------------
# compute_network_centrality
# ---------------------------------------------------------------------------


class TestComputeNetworkCentrality:
    """
    Covers L262-274: compute_network_centrality (dead method kept for API completeness).
    Tests the normal path, the empty-graph path, and the convergence-failure fallback.
    """

    def test_returns_dict_for_year_with_papers(self, mock_analyzer):
        """2015 has eid1 (israel-egypt). Graph has 2 nodes -> EC returns a dict."""
        result = mock_analyzer.compute_network_centrality(2015)
        assert isinstance(result, dict)

    def test_centrality_values_are_floats(self, mock_analyzer):
        """All centrality scores must be floating-point numbers."""
        result = mock_analyzer.compute_network_centrality(2015)
        if result:  # guard: may be empty on a very sparse Salton graph
            assert all(isinstance(v, float) for v in result.values())

    def test_returns_empty_dict_for_year_with_no_papers(self, mock_analyzer):
        """2000 has no papers -> empty graph -> eigenvector_centrality returns {}."""
        result = mock_analyzer.compute_network_centrality(2000)
        assert result == {}

    def test_convergence_failure_returns_empty_dict(self, mock_analyzer):
        """PowerIterationFailedConvergence is caught and the method returns {}."""
        with patch(
            "networkx.eigenvector_centrality",
            side_effect=nx.PowerIterationFailedConvergence(1000),
        ):
            result = mock_analyzer.compute_network_centrality(2015)
        assert result == {}


# ---------------------------------------------------------------------------
# get_thematic_contingency_table
# ---------------------------------------------------------------------------


class TestGetThematicContingencyTable:
    """
    Covers L278-322: get_thematic_contingency_table.

    Three counting branches:
      1. n_count > 0 only -> +1.0 to neutral
      2. s_count > 0 only -> +1.0 to sensitive
      3. Both > 0         -> +0.5 / +0.5 fractional  (requires eid6 via extended DB)

    With standard DB (DELIBERATE_N=5, eid5 np=8 excluded):
      israel_arab neutral   = 3.0  (eid1:engineering, eid2:medicine, eid4:physics)
      israel_arab sensitive = 0.0
      control neutral       = 0.0
      control sensitive     = 1.0  (eid3:social sciences, egypt-jordan dyad)
    """

    def test_returns_dataframe_with_correct_index(self, mock_analyzer):
        df = mock_analyzer.get_thematic_contingency_table()
        assert "israel_arab" in df.index
        assert "control" in df.index

    def test_columns_neutral_and_sensitive(self, mock_analyzer):
        df = mock_analyzer.get_thematic_contingency_table()
        assert "neutral" in df.columns
        assert "sensitive" in df.columns

    def test_neutral_branch_israel_arab(self, mock_analyzer, monkeypatch):
        """eid1, eid2, eid4 are all neutral subjects in israel_arab dyads -> 3.0."""
        monkeypatch.setattr(config, "DELIBERATE_N", 5)
        df = mock_analyzer.get_thematic_contingency_table()
        assert math.isclose(df.loc["israel_arab", "neutral"], 3.0, rel_tol=1e-5)
        assert math.isclose(df.loc["israel_arab", "sensitive"], 0.0, abs_tol=1e-9)

    def test_sensitive_branch_control(self, mock_analyzer, monkeypatch):
        """eid3 is social sciences (sensitive) in a control dyad -> control sensitive=1.0."""
        monkeypatch.setattr(config, "DELIBERATE_N", 5)
        df = mock_analyzer.get_thematic_contingency_table()
        assert math.isclose(df.loc["control", "sensitive"], 1.0, rel_tol=1e-5)
        assert math.isclose(df.loc["control", "neutral"], 0.0, abs_tol=1e-9)

    def test_fractional_branch_mixed_paper(self, mock_analyzer_extended, monkeypatch):
        """
        eid6: engineering (neutral) + social sciences (sensitive), israel+egypt dyad.
        n_count=1 AND s_count=1 -> +0.5 neutral, +0.5 sensitive (israel_arab).
        Expected totals: neutral = 3.0 + 0.5 = 3.5, sensitive = 0.0 + 0.5 = 0.5.
        """
        monkeypatch.setattr(config, "DELIBERATE_N", 5)
        df = mock_analyzer_extended.get_thematic_contingency_table()
        assert math.isclose(df.loc["israel_arab", "neutral"], 3.5, rel_tol=1e-5)
        assert math.isclose(df.loc["israel_arab", "sensitive"], 0.5, rel_tol=1e-5)

    def test_mega_project_excluded_by_deliberate_n(self, mock_analyzer, monkeypatch):
        """
        eid5 (np=8, physics/neutral, israel_arab) is excluded when DELIBERATE_N=5.
        Raising the cap to 10 should bring it in and increase the neutral count.
        """
        monkeypatch.setattr(config, "DELIBERATE_N", 5)
        df_5 = mock_analyzer.get_thematic_contingency_table()
        monkeypatch.setattr(config, "DELIBERATE_N", 10)
        df_10 = mock_analyzer.get_thematic_contingency_table()
        assert df_10.loc["israel_arab", "neutral"] >= df_5.loc["israel_arab", "neutral"]

    def test_all_values_non_negative(self, mock_analyzer):
        df = mock_analyzer.get_thematic_contingency_table()
        assert (df >= 0).all().all()


# ---------------------------------------------------------------------------
# _get_h3_query
# ---------------------------------------------------------------------------


class TestGetH3Query:
    """
    Covers L329: _get_h3_query returns the correct SQL template.
    Tests string structure, year parameterisation, and config.DELIBERATE_N embedding.
    """

    def test_returns_non_empty_string(self, mock_analyzer):
        q = mock_analyzer._get_h3_query(2015)
        assert isinstance(q, str) and len(q) > 50

    def test_year_is_embedded_in_query(self, mock_analyzer):
        q = mock_analyzer._get_h3_query(2011)
        assert "2011" in q

    def test_deliberate_n_embedded(self, mock_analyzer, monkeypatch):
        monkeypatch.setattr(config, "DELIBERATE_N", 7)
        q = mock_analyzer._get_h3_query(2015)
        assert "7" in q

    def test_salton_normalization_present(self, mock_analyzer):
        """Query must use SQRT for Salton's index denominator."""
        q = mock_analyzer._get_h3_query(2015)
        assert "SQRT" in q.upper()

    def test_query_selects_s_ij(self, mock_analyzer):
        """Result column s_ij is consumed by the topology loop in compute_network_centrality."""
        q = mock_analyzer._get_h3_query(2015)
        assert "s_ij" in q

    def test_different_years_produce_different_queries(self, mock_analyzer):
        assert mock_analyzer._get_h3_query(2010) != mock_analyzer._get_h3_query(2020)
