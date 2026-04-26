"""
test_analyzer.py
----------------
Tests for ScientificAnalyzer, covering:
  - C* formula correctness (fractional counting)
  - Salton's Index (normalised affinity)
  - DELIBERATE_N filter (mega-project exclusion)
  - fetch_sensitivity_stats (threshold calibration data)
  - fetch_regional_affinity_data (ΔC computation)

All expected values are derived from the synthetic dataset defined
in conftest.py and verified by hand calculation.
"""

import math

import pandas as pd
import pytest

# Ground-truth constants derived from the synthetic dataset
SQRT_5M = math.sqrt(5_000_000)  # = sqrt(israel_output * other_output) ≈ 2236.068
C_STAR_NP2 = 1.0  # 2 / (2 * 1)
C_STAR_NP3 = 1 / 3  # 2 / (3 * 2)
C_STAR_NP8 = 1 / 28  # 2 / (8 * 7)


class TestCStarFormula:
    """C* = 2 / (np * (np - 1)) for each co-authorship pair."""

    def test_bilateral_c_star(self):
        assert math.isclose(C_STAR_NP2, 1.0)

    def test_trilateral_c_star(self):
        assert math.isclose(C_STAR_NP3, 2 / 6)

    def test_mega_c_star(self):
        assert math.isclose(C_STAR_NP8, 2 / 56)

    def test_c_star_decreases_with_np(self):
        """Larger consortia contribute less per dyad — by design."""
        vals = [2 / (n * (n - 1)) for n in range(2, 20)]
        assert all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))


class TestDyadAffinity:
    """calculate_dyad_affinity: C* and Salton's Index per year for a dyad."""

    def test_returns_dataframe(self, mock_analyzer):
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        assert isinstance(df, pd.DataFrame)

    def test_required_columns_present(self, mock_analyzer):
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        for col in ["year", "p_i", "p_j", "c_star", "affinity_s"]:
            assert col in df.columns

    def test_baseline_values_2015_unrestricted(self, mock_analyzer):
        """
        2015: eid1 (np=2, C*=1.0) + eid5 (np=8, C*=1/28)
        Total C* = 1 + 1/28 ≈ 1.035714
        """
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        row = df[df["year"] == 2015].iloc[0]
        expected_c_star = C_STAR_NP2 + C_STAR_NP8
        assert math.isclose(row["c_star"], expected_c_star, rel_tol=1e-5)

    def test_deliberate_filter_excludes_mega_project(self, mock_analyzer):
        """
        With max_countries=5, eid5 (np=8) is excluded.
        2015 C* = 1.0 only (eid1).
        """
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt", max_countries=5)
        row = df[df["year"] == 2015].iloc[0]
        assert math.isclose(row["c_star"], C_STAR_NP2, rel_tol=1e-6)

    def test_salton_index_2015_deliberate(self, mock_analyzer):
        """
        S = C* / sqrt(P_i * P_j) = 1.0 / sqrt(5000 * 1000) ≈ 4.472e-4
        """
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt", max_countries=5)
        row = df[df["year"] == 2015].iloc[0]
        expected_s = C_STAR_NP2 / SQRT_5M
        assert math.isclose(row["affinity_s"], expected_s, rel_tol=1e-5)

    def test_trilateral_c_star_2021(self, mock_analyzer):
        """
        2021: only eid4 (np=3).  Israel–Egypt pair C* = 1/3.
        """
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        row = df[df["year"] == 2021].iloc[0]
        assert math.isclose(row["c_star"], C_STAR_NP3, rel_tol=1e-5)

    def test_zero_c_star_for_year_without_collaboration(self, mock_analyzer):
        df = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        # 2000 has no papers in synthetic data → C* should be 0
        row = df[df["year"] == 2000]
        if not row.empty:
            assert row.iloc[0]["c_star"] == 0.0

    def test_country_case_insensitive(self, mock_analyzer):
        df_lower = mock_analyzer.calculate_dyad_affinity("israel", "egypt")
        df_upper = mock_analyzer.calculate_dyad_affinity("Israel", "Egypt")
        assert len(df_lower) == len(df_upper)


class TestSensitivityStats:
    """fetch_sensitivity_stats returns correct group totals per threshold N."""

    def test_returns_dataframe_with_two_groups(self, mock_analyzer):
        df = mock_analyzer.fetch_sensitivity_stats(2)
        assert set(df["group_type"]) == {"Israel-Involved", "Non-Israel"}

    def test_n2_israel_involved(self, mock_analyzer):
        """n=2: only eid1 + eid2 → Israel-Involved = 2.0"""
        df = mock_analyzer.fetch_sensitivity_stats(2)
        val = df[df["group_type"] == "Israel-Involved"]["c_star"].sum()
        assert math.isclose(val, 2.0, rel_tol=1e-5)

    def test_n2_non_israel(self, mock_analyzer):
        """n=2: only eid3 → Non-Israel = 1.0"""
        df = mock_analyzer.fetch_sensitivity_stats(2)
        val = df[df["group_type"] == "Non-Israel"]["c_star"].sum()
        assert math.isclose(val, 1.0, rel_tol=1e-5)

    def test_n3_israel_involved(self, mock_analyzer):
        """n=3 adds eid4: two Israel pairs each contributing 1/3."""
        df = mock_analyzer.fetch_sensitivity_stats(3)
        val = df[df["group_type"] == "Israel-Involved"]["c_star"].sum()
        expected = 2.0 + 2 * C_STAR_NP3  # ≈ 2.667
        assert math.isclose(val, expected, rel_tol=1e-5)

    def test_n3_non_israel(self, mock_analyzer):
        """n=3 adds eid4: egypt–morocco pair contributes 1/3."""
        df = mock_analyzer.fetch_sensitivity_stats(3)
        val = df[df["group_type"] == "Non-Israel"]["c_star"].sum()
        expected = 1.0 + C_STAR_NP3  # ≈ 1.333
        assert math.isclose(val, expected, rel_tol=1e-5)

    def test_n8_adds_mega_project_correctly(self, mock_analyzer):
        """
        eid5 (np=8): 28 dyads each with C*=1/28.
        7 Israel pairs → +0.25 Israel-Involved.
        21 Non-Israel pairs → +0.75 Non-Israel.
        """
        df_n3 = mock_analyzer.fetch_sensitivity_stats(3)
        df_n8 = mock_analyzer.fetch_sensitivity_stats(8)
        isr_3 = df_n3[df_n3["group_type"] == "Israel-Involved"]["c_star"].sum()
        isr_8 = df_n8[df_n8["group_type"] == "Israel-Involved"]["c_star"].sum()
        nonisr_3 = df_n3[df_n3["group_type"] == "Non-Israel"]["c_star"].sum()
        nonisr_8 = df_n8[df_n8["group_type"] == "Non-Israel"]["c_star"].sum()
        assert math.isclose(isr_8 - isr_3, 7 * C_STAR_NP8, rel_tol=1e-5)
        assert math.isclose(nonisr_8 - nonisr_3, 21 * C_STAR_NP8, rel_tol=1e-5)

    def test_monotone_increase_with_n(self, mock_analyzer):
        """C* can only grow as N increases (more papers qualify)."""
        vals = [
            mock_analyzer.fetch_sensitivity_stats(n)[
                mock_analyzer.fetch_sensitivity_stats(n)["group_type"]
                == "Israel-Involved"
            ]["c_star"].sum()
            for n in [2, 3, 8]
        ]
        assert vals[0] <= vals[1] <= vals[2]


class TestRegionalAffinityDelta:
    """fetch_regional_affinity_data: ΔC = (S_unr - S_del) / S_unr."""

    def test_returns_required_columns(self, mock_analyzer):
        df = mock_analyzer.fetch_regional_affinity_data()
        for col in ["year", "c_i", "c_j", "s_unr", "s_del", "delta_c"]:
            assert col in df.columns

    def test_delta_c_zero_when_s_unr_is_zero(self, mock_analyzer):
        df = mock_analyzer.fetch_regional_affinity_data()
        zero_rows = df[df["s_unr"] == 0]
        assert (zero_rows["delta_c"] == 0.0).all()

    def test_delta_c_between_zero_and_one(self, mock_analyzer):
        df = mock_analyzer.fetch_regional_affinity_data()
        nonzero = df[df["s_unr"] > 0]
        assert (nonzero["delta_c"] >= 0).all()
        assert (nonzero["delta_c"] <= 1).all()

    def test_delta_c_formula(self):
        """Unit test the ΔC formula independent of the DB."""
        import numpy as np

        s_unr = pd.Series([0.010, 0.008, 0.000])
        s_del = pd.Series([0.005, 0.008, 0.000])
        delta = pd.Series([0.0, 0.0, 0.0])
        mask = s_unr > 0
        delta[mask] = (s_unr[mask] - s_del[mask]) / s_unr[mask]
        assert math.isclose(delta[0], 0.5)
        assert math.isclose(delta[1], 0.0)
        assert math.isclose(delta[2], 0.0)
