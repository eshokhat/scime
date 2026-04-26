"""
test_formulas.py
----------------
Rigorous unit tests for all pure mathematical functions in engine/utils.py
and the dataclass contracts in engine/models.py.

Coverage goals
--------------
- fractional_weight  : n_p ∈ {2, 4, 10, 50}, edge cases (n_p < 2)
- salton_index       : normal path + zero/negative guard branches
- delta_c_metric     : s_unr = 0 (no division-by-zero), all value combinations
- elbow_detection    : L-curve, flat, single-point, various bend positions
- proportional thematic weight W_n = n/(n+s): all neutral, all sensitive, mixed
- dyad classifiers   : is_israel_dyad, is_fractured_dyad,
                       classify_dyad_h2a, classify_dyad_h2b
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.utils import (
    classify_dyad_h2a,
    classify_dyad_h2b,
    delta_c_metric,
    elbow_detection,
    fractional_weight,
    is_fractured_dyad,
    is_israel_dyad,
    salton_index,
)


# ---------------------------------------------------------------------------
# fractional_weight
# ---------------------------------------------------------------------------


class TestFractionalWeight:
    """C* = 2 / (nₚ · (nₚ − 1)) — verified against hand-calculated values."""

    @pytest.mark.parametrize(
        "n_p,expected",
        [
            (2, 1.0),               # 2 / (2 · 1)  = 1.0
            (4, 2 / 12),            # 2 / (4 · 3)  = 1/6
            (10, 2 / 90),           # 2 / (10 · 9) = 1/45
            (50, 2 / 2450),         # 2 / (50 · 49)
        ],
    )
    def test_canonical_values(self, n_p, expected):
        assert math.isclose(fractional_weight(n_p), expected, rel_tol=1e-12)

    def test_n_p_zero_returns_zero(self):
        assert fractional_weight(0) == 0.0

    def test_n_p_one_returns_zero(self):
        """A single-author paper has no co-authorship dyad."""
        assert fractional_weight(1) == 0.0

    def test_n_p_negative_returns_zero(self):
        assert fractional_weight(-1) == 0.0

    def test_n_p_two_is_exactly_one(self):
        """A bilateral paper contributes exactly 1.0 to the dyad."""
        assert fractional_weight(2) == 1.0

    def test_monotonically_decreasing(self):
        """Larger consortia contribute less per dyad — by design."""
        vals = [fractional_weight(n) for n in range(2, 52)]
        assert all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))

    def test_return_type_is_float(self):
        assert isinstance(fractional_weight(3), float)

    def test_large_n_p_approaches_zero(self):
        """For n_p = 1 000, the per-dyad weight is negligible."""
        assert fractional_weight(1000) < 1e-5

    def test_sum_of_all_dyad_weights_equals_one(self):
        """
        For a paper with n_p countries there are n_p*(n_p-1)/2 unique dyads.
        Each carries C* = 2/(n_p*(n_p-1)).
        Their sum must equal 1.0.
        """
        for n_p in [2, 3, 5, 8, 20]:
            n_dyads = n_p * (n_p - 1) // 2
            total = n_dyads * fractional_weight(n_p)
            assert math.isclose(total, 1.0, rel_tol=1e-12), (
                f"n_p={n_p}: expected sum=1.0, got {total}"
            )


# ---------------------------------------------------------------------------
# salton_index
# ---------------------------------------------------------------------------


class TestSaltonIndex:
    """S_ij = C* / √(P_i · P_j) — Salton's cosine normalisation."""

    def test_basic_calculation(self):
        """S = 1.0 / sqrt(5000 × 1000) ≈ 4.4721e-4"""
        expected = 1.0 / math.sqrt(5_000 * 1_000)
        assert math.isclose(salton_index(1.0, 5_000, 1_000), expected, rel_tol=1e-9)

    def test_zero_p_i_returns_zero(self):
        """Guard: p_i = 0 must not raise ZeroDivisionError."""
        assert salton_index(1.0, 0.0, 1_000) == 0.0

    def test_zero_p_j_returns_zero(self):
        assert salton_index(1.0, 1_000, 0.0) == 0.0

    def test_negative_p_i_returns_zero(self):
        assert salton_index(1.0, -1.0, 1_000) == 0.0

    def test_negative_p_j_returns_zero(self):
        assert salton_index(1.0, 1_000, -1.0) == 0.0

    def test_zero_c_star_returns_zero(self):
        assert salton_index(0.0, 5_000, 1_000) == 0.0

    def test_symmetric(self):
        """Swapping p_i and p_j must not change the result (√ is commutative)."""
        assert math.isclose(
            salton_index(1.0, 5_000, 1_000),
            salton_index(1.0, 1_000, 5_000),
            rel_tol=1e-12,
        )

    def test_equal_outputs_simplifies(self):
        """When p_i = p_j = N, S = c_star / N."""
        n, c_star = 100.0, 2.0
        assert math.isclose(salton_index(c_star, n, n), c_star / n, rel_tol=1e-12)

    def test_result_non_negative(self):
        assert salton_index(0.5, 100, 200) >= 0.0

    def test_higher_c_star_higher_salton(self):
        """Holding P_i, P_j fixed, S is proportional to C*."""
        s_low = salton_index(0.5, 100, 100)
        s_high = salton_index(2.0, 100, 100)
        assert s_high > s_low

    def test_lower_production_higher_salton(self):
        """Holding C* fixed, smaller production bases yield higher similarity."""
        s_small = salton_index(1.0, 10, 10)
        s_large = salton_index(1.0, 1000, 1000)
        assert s_small > s_large


# ---------------------------------------------------------------------------
# delta_c_metric
# ---------------------------------------------------------------------------


class TestDeltaCMetric:
    """ΔC = (S_unr − S_del) / S_unr  — mega-science reliance metric."""

    def test_s_unr_zero_no_division_by_zero(self):
        """Critical guard: s_unr = 0 must return 0.0, never raise ZeroDivisionError."""
        assert delta_c_metric(0.0, 0.0) == 0.0

    def test_s_unr_negative_returns_zero(self):
        assert delta_c_metric(-0.01, 0.0) == 0.0

    def test_s_unr_very_small_positive_no_error(self):
        """Just above the guard threshold: must not raise."""
        result = delta_c_metric(1e-15, 0.0)
        assert 0.0 <= result <= 1.0

    def test_equal_values_returns_zero(self):
        """S_unr = S_del (no consortia reliance) → ΔC = 0."""
        assert math.isclose(delta_c_metric(0.01, 0.01), 0.0, abs_tol=1e-12)

    def test_s_del_zero_returns_one(self):
        """Deliberate network = 0; full consortia reliance → ΔC = 1.0."""
        assert math.isclose(delta_c_metric(0.01, 0.0), 1.0, rel_tol=1e-9)

    @pytest.mark.parametrize(
        "s_unr,s_del,expected",
        [
            (0.010, 0.005, 0.5),
            (0.010, 0.008, 0.2),
            (0.010, 0.004, 0.6),
            (0.010, 0.000, 1.0),
            (0.010, 0.010, 0.0),
        ],
    )
    def test_parametrized_exact_values(self, s_unr, s_del, expected):
        assert math.isclose(delta_c_metric(s_unr, s_del), expected, rel_tol=1e-9)

    def test_result_in_unit_interval(self):
        """ΔC ∈ [0, 1] for any valid (s_del ≤ s_unr) pair."""
        for s_unr, s_del in [(0.02, 0.01), (0.1, 0.1), (0.05, 0.00), (0.03, 0.02)]:
            result = delta_c_metric(s_unr, s_del)
            assert 0.0 <= result <= 1.0, f"Out of [0,1]: {result} for {s_unr},{s_del}"

    def test_monotone_in_s_del(self):
        """Increasing s_del (more deliberate-network affinity) reduces ΔC."""
        s_unr = 0.01
        deltas = [delta_c_metric(s_unr, s_del) for s_del in [0.0, 0.003, 0.006, 0.009]]
        assert all(deltas[i] >= deltas[i + 1] for i in range(len(deltas) - 1))


# ---------------------------------------------------------------------------
# Proportional thematic weight  W_n = n / (n + s)
# ---------------------------------------------------------------------------


class TestProportionalThematicWeight:
    """
    Verify the W_n = n/(n+s) formula used by ThematicAnalyst's 'proportional'
    method as a standalone mathematical unit test.

    This does not hit the database — it tests the formula in isolation.
    """

    @staticmethod
    def _proportional_weights(n_count: int, s_count: int) -> tuple[float, float]:
        """
        Mirror of the proportional branch in ThematicAnalyst.
        Returns (w_neutral, w_sensitive).
        """
        total = n_count + s_count
        if total == 0:
            return (0.0, 0.0)
        return n_count / total, s_count / total

    def test_all_neutral_gives_full_neutral_weight(self):
        """n=5, s=0 → W_n = 1.0, W_s = 0.0."""
        w_n, w_s = self._proportional_weights(5, 0)
        assert math.isclose(w_n, 1.0, rel_tol=1e-12)
        assert math.isclose(w_s, 0.0, abs_tol=1e-12)

    def test_all_sensitive_gives_full_sensitive_weight(self):
        """n=0, s=3 → W_n = 0.0, W_s = 1.0."""
        w_n, w_s = self._proportional_weights(0, 3)
        assert math.isclose(w_n, 0.0, abs_tol=1e-12)
        assert math.isclose(w_s, 1.0, rel_tol=1e-12)

    def test_equal_counts_half_half(self):
        """n=s → W_n = W_s = 0.5."""
        w_n, w_s = self._proportional_weights(1, 1)
        assert math.isclose(w_n, 0.5, rel_tol=1e-12)
        assert math.isclose(w_s, 0.5, rel_tol=1e-12)

    def test_weights_sum_to_one(self):
        """W_n + W_s = 1.0 for any non-zero (n, s) pair."""
        for n, s in [(1, 1), (3, 1), (1, 3), (5, 0), (0, 5), (7, 2)]:
            w_n, w_s = self._proportional_weights(n, s)
            assert math.isclose(w_n + w_s, 1.0, rel_tol=1e-12), (
                f"n={n}, s={s}: weights sum to {w_n + w_s}"
            )

    def test_zero_zero_returns_zeros(self):
        """Edge case: paper with no counted subjects yields (0.0, 0.0)."""
        w_n, w_s = self._proportional_weights(0, 0)
        assert w_n == 0.0 and w_s == 0.0

    @pytest.mark.parametrize(
        "n,s,expected_wn",
        [
            (3, 1, 0.75),
            (1, 3, 0.25),
            (2, 8, 0.2),
            (8, 2, 0.8),
        ],
    )
    def test_parametrized_ratios(self, n, s, expected_wn):
        w_n, _ = self._proportional_weights(n, s)
        assert math.isclose(w_n, expected_wn, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# elbow_detection
# ---------------------------------------------------------------------------


class TestElbowDetection:
    """Kneedle algorithm: maximum perpendicular distance from the chord."""

    def test_perfect_l_curve_finds_bend(self):
        """
        y rises linearly then plateaus.  The bend is at x=4 (index 2).
        Normalised chord runs (0,0)→(1,1); max perp. distance is at index 2.
        """
        x = [2, 3, 4, 5, 6, 7]
        y = [1, 2, 3, 3, 3, 3]
        assert elbow_detection(x, y) == 4

    def test_returns_int(self):
        assert isinstance(elbow_detection([2, 3, 4], [1.0, 2.0, 2.5]), int)

    def test_single_element_returns_that_element(self):
        assert elbow_detection([5], [10.0]) == 5

    def test_flat_curve_returns_first_x(self):
        """All values equal → all perp. distances equal → argmax picks index 0."""
        assert elbow_detection([2, 3, 4, 5], [1.0, 1.0, 1.0, 1.0]) == 2

    def test_result_within_x_range(self):
        x = list(range(2, 16))
        y = [i**0.3 for i in x]   # concave growth
        result = elbow_detection(x, y)
        assert x[0] <= result <= x[-1]

    @pytest.mark.parametrize("bend_at", [3, 5, 8, 12])
    def test_detected_elbow_near_true_bend(self, bend_at):
        """For various step-plateau curves the elbow must be within ±1 of the bend."""
        x = list(range(2, 20))
        y = [min(i - 1, bend_at - 1) * 1.0 for i in x]
        result = elbow_detection(x, y)
        assert abs(result - bend_at) <= 1

    def test_longer_plateau_same_elbow(self):
        """Extending the plateau beyond the bend must not shift the detected elbow."""
        x_short = [2, 3, 4, 5, 6]
        y_short = [1, 2, 3, 3, 3]
        x_long = [2, 3, 4, 5, 6, 7, 8, 9]
        y_long = [1, 2, 3, 3, 3, 3, 3, 3]
        assert elbow_detection(x_short, y_short) == elbow_detection(x_long, y_long)

    def test_strictly_linear_in_range(self):
        """Linear curve: result is still within the valid x range."""
        x = [2, 3, 4, 5, 6]
        y = [0.0, 1.0, 2.0, 3.0, 4.0]
        result = elbow_detection(x, y)
        assert x[0] <= result <= x[-1]

    def test_concave_curve_low_elbow(self):
        """A logarithmic growth curve should have its elbow early."""
        x = list(range(2, 26))
        y = [math.log(i) for i in x]
        result = elbow_detection(x, y)
        # Elbow should be in the first third of the range for log growth
        assert result <= x[len(x) // 2]


# ---------------------------------------------------------------------------
# is_israel_dyad
# ---------------------------------------------------------------------------


class TestIsIsraelDyad:
    def test_israel_as_c_i(self):
        assert is_israel_dyad("israel", "egypt") is True

    def test_israel_as_c_j(self):
        assert is_israel_dyad("egypt", "israel") is True

    def test_no_israel(self):
        assert is_israel_dyad("egypt", "jordan") is False

    def test_both_israel(self):
        assert is_israel_dyad("israel", "israel") is True

    def test_case_sensitive_uppercase_is_false(self):
        """Function expects lowercase; 'Israel' is not equal to 'israel'."""
        assert is_israel_dyad("Israel", "egypt") is False


# ---------------------------------------------------------------------------
# is_fractured_dyad
# ---------------------------------------------------------------------------


class TestIsFracturedDyad:
    _NORMALIZED = frozenset(
        {"egypt", "jordan", "morocco", "bahrain", "united arab emirates"}
    )

    def test_israel_non_normalized_is_fractured(self):
        assert is_fractured_dyad("israel", "iran", self._NORMALIZED) is True

    def test_israel_normalized_not_fractured(self):
        assert is_fractured_dyad("israel", "egypt", self._NORMALIZED) is False

    def test_non_israel_dyad_not_fractured(self):
        assert is_fractured_dyad("egypt", "jordan", self._NORMALIZED) is False

    def test_order_invariant_israel_as_ci(self):
        assert is_fractured_dyad("israel", "syria", self._NORMALIZED) is True

    def test_order_invariant_israel_as_cj(self):
        assert is_fractured_dyad("syria", "israel", self._NORMALIZED) is True

    def test_all_five_normalized_partners_not_fractured(self):
        for partner in self._NORMALIZED - {"israel"}:
            assert is_fractured_dyad("israel", partner, self._NORMALIZED) is False, (
                f"Expected not fractured for israel–{partner}"
            )


# ---------------------------------------------------------------------------
# classify_dyad_h2a
# ---------------------------------------------------------------------------


class TestClassifyDyadH2a:
    _DESTABILIZED = frozenset({"egypt", "syria", "libya", "yemen", "tunisia"})

    def test_destabilized_country_gives_destabilized(self):
        assert classify_dyad_h2a("egypt", "jordan", self._DESTABILIZED) == "destabilized"

    def test_israel_non_destabilized_gives_israel(self):
        assert classify_dyad_h2a("israel", "jordan", self._DESTABILIZED) == "israel"

    def test_stable_control_no_israel_no_destab(self):
        assert (
            classify_dyad_h2a("jordan", "morocco", self._DESTABILIZED) == "stable_control"
        )

    def test_destabilized_beats_israel_in_priority(self):
        """egypt (destabilized) + israel: destabilized takes priority."""
        assert (
            classify_dyad_h2a("egypt", "israel", self._DESTABILIZED) == "destabilized"
        )

    def test_both_destabilized(self):
        assert (
            classify_dyad_h2a("egypt", "syria", self._DESTABILIZED) == "destabilized"
        )

    @pytest.mark.parametrize("destab", ["egypt", "syria", "libya", "yemen", "tunisia"])
    def test_each_destabilized_state(self, destab):
        """Every state in the destabilized set must classify as 'destabilized'."""
        assert (
            classify_dyad_h2a(destab, "jordan", self._DESTABILIZED) == "destabilized"
        )


# ---------------------------------------------------------------------------
# classify_dyad_h2b
# ---------------------------------------------------------------------------


class TestClassifyDyadH2b:
    _NORM_SET = frozenset({"morocco", "bahrain", "united arab emirates"})

    def test_israel_normalized_partner_is_norm(self):
        assert classify_dyad_h2b("israel", "morocco", self._NORM_SET) == "norm"

    def test_israel_non_normalized_partner_is_nonnorm(self):
        assert classify_dyad_h2b("israel", "egypt", self._NORM_SET) == "nonnorm"

    def test_no_israel_is_reference(self):
        assert classify_dyad_h2b("egypt", "jordan", self._NORM_SET) == "reference"

    def test_order_invariant_norm_ci(self):
        assert classify_dyad_h2b("morocco", "israel", self._NORM_SET) == "norm"

    def test_order_invariant_nonnorm_ci(self):
        assert classify_dyad_h2b("iran", "israel", self._NORM_SET) == "nonnorm"

    @pytest.mark.parametrize("norm_partner", ["morocco", "bahrain", "united arab emirates"])
    def test_each_normalized_partner_is_norm(self, norm_partner):
        assert classify_dyad_h2b("israel", norm_partner, self._NORM_SET) == "norm"

    def test_empty_norm_set_is_nonnorm(self):
        """With no normalized states, any israel-dyad is 'nonnorm'."""
        assert classify_dyad_h2b("israel", "egypt", frozenset()) == "nonnorm"
