"""
engine/sensitivity_analyzer.py
--------------------------------
Full-range sensitivity analysis for the MENA collaboration weighting scheme.

Grid search
-----------
Two axes iterate over [0.1 … 1.0] in steps of 0.1:
    SCALE_CONSORTIA_WEIGHT   — mega-science tier weight (nₚ > DELIBERATE_N)
    SCOPE_INTERNATIONAL_WEIGHT — cross-country scope multiplier

Thematic comparison
-------------------
Each grid point is evaluated under two thematic methods:
    'fixed_0.5'        — mixed paper always splits 50/50 neutral / sensitive
    'proportional_linear' — split ∝ actual field counts  (n_k / Σn_k)

Test cases
----------
    A : 100% IL authors      (n_countries = 1)
    B : 3 authors / 2 countries   → small deliberate group (nₚ ≤ DELIBERATE_N)
    C : 50 authors / 15 countries → mega-science consortia (nₚ > DELIBERATE_N)
    D : 4 neutral / 1 sensitive subject  → thematic bias probe

Output
------
    outputs/tables/weight_sensitivity_results.csv   (200 rows)
    Console: Stability Zone summary

DRY note
--------
config.WEIGHTS provides the baseline fixed values (small_group, domestic); the
grid varies only the two parameters under test (consortia_w, international_w).
config.WEIGHTS is NEVER mutated — each grid row uses local scalar copies of the
weights so that the module is safe to import alongside the live research engine.
"""

from __future__ import annotations

import csv
import sys
from itertools import product
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DELIBERATE_NP_THRESHOLD as DELIBERATE_N, WEIGHTS

# ── Grid parameters ───────────────────────────────────────────────────────────

_AXIS = [round(v / 10, 1) for v in range(1, 11)]  # [0.1, 0.2, …, 1.0]

GRID_CONSORTIA_WEIGHT = _AXIS
GRID_INTERNATIONAL_WEIGHT = _AXIS
THEMATIC_METHODS = ["fixed_0.5", "proportional_linear"]

# ── Test case definitions ─────────────────────────────────────────────────────

CASES: dict[str, dict[str, Any]] = {
    "A": {
        "n_countries": 1,
        "n_authors": 10,
        "n_neutral": 3,
        "n_sensitive": 1,
        "description": "100% IL authors — no cross-border dyad",
    },
    "B": {
        "n_countries": 2,
        "n_authors": 3,
        "n_neutral": 3,
        "n_sensitive": 1,
        "description": "3 authors / 2 countries — small deliberate group",
    },
    "C": {
        "n_countries": 15,
        "n_authors": 50,
        "n_neutral": 3,
        "n_sensitive": 1,
        "description": "50 authors / 15 countries — mega-science consortia",
    },
    "D": {
        "n_countries": 2,
        "n_authors": 5,
        "n_neutral": 4,
        "n_sensitive": 1,
        "description": "4 neutral / 1 sensitive subject — thematic bias probe",
    },
}

# ── Core computation helpers ──────────────────────────────────────────────────


def _scale_weight(n_countries: int, consortia_w: float) -> float:
    """Return the SCALE weight for this paper tier. Baseline small_group is fixed."""
    small_group_w: float = WEIGHTS["SCALE"]["small"]  # type: ignore[assignment]
    return small_group_w if n_countries <= DELIBERATE_N else consortia_w


def _scope_weight(n_countries: int, international_w: float) -> float:
    """Return the SCOPE weight for this paper tier. Baseline domestic is fixed."""
    domestic_w: float = WEIGHTS["SCOPE"]["domestic"]  # type: ignore[assignment]
    return domestic_w if n_countries <= 1 else international_w


def compute_cstar_total(
    n_countries: int, consortia_w: float, international_w: float
) -> float:
    """
    Total C* contribution summed across all dyads in a single paper.

    Formula (methodology.md):
        C*_paper = Σ_{(i,j)} 2 / (nₚ · (nₚ − 1))   × scale_w × scope_w

    For nₚ countries the number of dyads is nₚ(nₚ−1)/2, and each contributes
    2/(nₚ(nₚ−1)), so the sum telescopes to:
        C*_paper = scale_w × scope_w

    Parameters
    ----------
    n_countries      : number of distinct author countries in the paper
    consortia_w      : SCALE_CONSORTIA_WEIGHT being tested
    international_w  : SCOPE_INTERNATIONAL_WEIGHT being tested
    """
    if n_countries < 2:
        return 0.0

    # Sum over all dyads: n_dyads * c_per_dyad = [nₚ(nₚ-1)/2] * [2/(nₚ(nₚ-1))] = 1
    # → total telescopes to exactly 1 regardless of nₚ, before weighting.
    scale_w = _scale_weight(n_countries, consortia_w)
    scope_w = _scope_weight(n_countries, international_w)
    return scale_w * scope_w


def compute_thematic(
    n_neutral: int, n_sensitive: int, method: str
) -> tuple[float, float, float]:
    """
    Compute (neutral_weight, sensitive_weight, bias_vs_proportional).

    Proportional is the LaTeX-defined default:
        w_k = n_k / (n_neutral + n_sensitive)

    Bias is the absolute deviation of sensitive_weight from its
    proportional target — zero means the method is unbiased.

    Returns
    -------
    (neutral_w, sensitive_w, bias)
    """
    total = n_neutral + n_sensitive
    prop_sensitive = n_sensitive / total
    prop_neutral = n_neutral / total

    if method == "fixed_0.5":
        if n_neutral > 0 and n_sensitive > 0:
            s_w, n_w = 0.5, 0.5
        elif n_sensitive == 0:
            s_w, n_w = 0.0, 1.0
        else:
            s_w, n_w = 1.0, 0.0
    else:  # proportional_linear
        s_w = prop_sensitive
        n_w = prop_neutral

    bias = abs(s_w - prop_sensitive)
    return n_w, s_w, bias


def compute_row(
    consortia_w: float,
    international_w: float,
    method: str,
) -> dict[str, Any]:
    """Compute all metrics for a single grid point."""
    # C* totals for all cases
    cstar = {
        k: compute_cstar_total(v["n_countries"], consortia_w, international_w)
        for k, v in CASES.items()
    }

    # Per-dyad C* for Cases B and C (for diagnostic reference)
    cstar_per_dyad_B = (
        2.0
        / (CASES["B"]["n_countries"] * (CASES["B"]["n_countries"] - 1))
        * _scale_weight(CASES["B"]["n_countries"], consortia_w)
        * _scope_weight(CASES["B"]["n_countries"], international_w)
    )
    cstar_per_dyad_C = (
        2.0
        / (CASES["C"]["n_countries"] * (CASES["C"]["n_countries"] - 1))
        * _scale_weight(CASES["C"]["n_countries"], consortia_w)
        * _scope_weight(CASES["C"]["n_countries"], international_w)
    )

    # Penalisation: does Case C contribute LESS total C* per paper than Case B?
    ratio_C_to_B = (cstar["C"] / cstar["B"]) if cstar["B"] > 1e-12 else float("inf")
    case_c_penalized = ratio_C_to_B < 1.0

    # Thematic metrics for Case D
    n_w_D, s_w_D, bias_D = compute_thematic(
        CASES["D"]["n_neutral"],
        CASES["D"]["n_sensitive"],
        method,
    )
    zero_bias = abs(bias_D) < 1e-9
    in_stability = zero_bias and case_c_penalized

    return {
        "consortia_weight": consortia_w,
        "international_weight": international_w,
        "thematic_method": method,
        # Total C* per paper for each case
        "cstar_total_A": round(cstar["A"], 6),
        "cstar_total_B": round(cstar["B"], 6),
        "cstar_total_C": round(cstar["C"], 6),
        "cstar_total_D": round(cstar["D"], 6),
        # Per-dyad C* (diagnostic)
        "cstar_per_dyad_B": round(cstar_per_dyad_B, 6),
        "cstar_per_dyad_C": round(cstar_per_dyad_C, 8),
        # Penalisation metric: < 1.0 means consortia paper contributes less per paper
        "ratio_C_to_B": round(ratio_C_to_B, 6),
        "case_C_penalized": case_c_penalized,
        # Thematic weights for Case D (4 neutral / 1 sensitive)
        "thematic_neutral_w_D": round(n_w_D, 4),
        "thematic_sensitive_w_D": round(s_w_D, 4),
        # Bias: |sensitive_w − proportional_sensitive| = |s_w − 0.2|
        "thematic_bias_D": round(bias_D, 4),
        # Stability flags
        "zero_bias": zero_bias,
        "in_stability_zone": in_stability,
    }


# ── Grid search ───────────────────────────────────────────────────────────────


def run_grid() -> list[dict[str, Any]]:
    """Enumerate all (consortia_w × international_w × method) combinations."""
    combos = list(
        product(GRID_CONSORTIA_WEIGHT, GRID_INTERNATIONAL_WEIGHT, THEMATIC_METHODS)
    )
    return [compute_row(cw, iw, method) for cw, iw, method in combos]


# ── CSV export ────────────────────────────────────────────────────────────────


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[CSV]  Wrote {len(rows)} rows → {path.relative_to(ROOT)}")


# ── Stability zone analysis ───────────────────────────────────────────────────


def _fmt_range(values: list[float]) -> str:
    """Format a sorted list of floats as a compact range string."""
    if not values:
        return "∅"
    lo, hi = min(values), max(values)
    return f"[{lo:.1f} – {hi:.1f}]" if lo != hi else f"{lo:.1f}"


def print_stability_summary(rows: list[dict[str, Any]]) -> None:
    """
    Analyse and print the Stability Zone — the parameter sub-space where:
      1. Case D thematic bias = 0.0   (no over-weighting of sensitive fields)
      2. Case C total C* < Case B     (consortia papers penalised vs small groups)
    """
    sep = "=" * 68
    sep2 = "-" * 68

    stable = [r for r in rows if r["in_stability_zone"]]
    zero_bias = [r for r in rows if r["zero_bias"]]
    penalised = [r for r in rows if r["case_C_penalized"]]

    # Unique parameter values in stability zone
    stab_cw = sorted({r["consortia_weight"] for r in stable})
    stab_iw = sorted({r["international_weight"] for r in stable})
    stab_mth = sorted({r["thematic_method"] for r in stable})

    # Boundary analysis: what breaks stability?
    # Criterion 2 fails when consortia_w ≥ small_group_w (= 0.8)
    small_group_w: float = WEIGHTS["SCALE"]["small"]  # type: ignore[assignment]
    critical_cw = small_group_w

    # Penalisation ratios at boundary
    # ratio_C_to_B = consortia_w / small_group_w (scope cancels)
    ratio_at_boundary = 1.0 * 1.0 / small_group_w  # consortia_w = critical_cw

    print()
    print(sep)
    print("  SENSITIVITY ANALYSIS — STABILITY ZONE SUMMARY")
    print(sep)
    print()

    # ── Grid overview ─────────────────────────────────────────────────────────

    print(f"  Grid dimensions")
    print(
        f"  {'SCALE_CONSORTIA_WEIGHT':32s} : {_fmt_range(GRID_CONSORTIA_WEIGHT)}  ({len(GRID_CONSORTIA_WEIGHT)} levels)"
    )
    print(
        f"  {'SCOPE_INTERNATIONAL_WEIGHT':32s} : {_fmt_range(GRID_INTERNATIONAL_WEIGHT)}  ({len(GRID_INTERNATIONAL_WEIGHT)} levels)"
    )
    print(f"  {'Thematic methods':32s} : {', '.join(THEMATIC_METHODS)}")
    print(f"  {'Total combinations':32s} : {len(rows)}")
    print()

    # ── Test case C* at baseline ──────────────────────────────────────────────

    baseline_cw = WEIGHTS["SCALE"]["cons"]  # type: ignore[assignment]
    baseline_iw = WEIGHTS["SCOPE"]["intl"]  # type: ignore[assignment]

    print("  Baseline C* per paper  (consortia_w=0.2, international_w=0.7)")
    print(
        f"  {'Case A (1 country)':32s} : {compute_cstar_total(1, baseline_cw, baseline_iw):.4f}  (no dyad → 0)"
    )
    print(
        f"  {'Case B (2 countries)':32s} : {compute_cstar_total(2, baseline_cw, baseline_iw):.4f}  (small group)"
    )
    print(
        f"  {'Case C (15 countries)':32s} : {compute_cstar_total(15, baseline_cw, baseline_iw):.4f}  (consortia)"
    )
    print(
        f"  {'Ratio C/B':32s} : {compute_cstar_total(15, baseline_cw, baseline_iw) / compute_cstar_total(2, baseline_cw, baseline_iw):.4f}"
    )
    print()

    # ── Thematic at baseline (Case D) ─────────────────────────────────────────

    _, s_w_prop, bias_prop = compute_thematic(4, 1, "proportional_linear")
    _, s_w_fix, bias_fix = compute_thematic(4, 1, "fixed_0.5")
    prop_target = 1 / 5

    print("  Case D thematic weights  (4 neutral / 1 sensitive)")
    print(
        f"  {'Proportional target':32s} : sensitive = {prop_target:.4f}  neutral = {1 - prop_target:.4f}"
    )
    print(f"  {'fixed_0.5':32s} : sensitive = {s_w_fix:.4f}  bias = {bias_fix:.4f}")
    print(
        f"  {'proportional_linear':32s} : sensitive = {s_w_prop:.4f}  bias = {bias_prop:.4f}  ✓ zero bias"
    )
    print()

    # ── Stability criteria ────────────────────────────────────────────────────

    print(sep2)
    print("  Stability Criteria")
    print(sep2)
    print()
    print(f"  #1  Case D thematic bias = 0.0")
    print(f"      Satisfied by  : proportional_linear  only")
    print(
        f"      Satisfied for : {len(zero_bias)} / {len(rows)} grid rows  ({len(zero_bias) / len(rows) * 100:.0f}%)"
    )
    print()
    print(f"  #2  Case C effectively penalised vs Case B  (ratio_C_to_B < 1.0)")
    print(
        f"      Mathematical condition : consortia_weight < small_group_weight = {small_group_w:.1f}"
    )
    print(
        f"      (scope weight cancels in the ratio since both cases are international)"
    )
    print(
        f"      At boundary (consortia_w = {critical_cw:.1f}) : ratio = 1.000  (parity, not penalty)"
    )
    print(
        f"      Satisfied for : {len(penalised)} / {len(rows)} grid rows  ({len(penalised) / len(rows) * 100:.0f}%)"
    )
    print()

    # ── Stability zone ────────────────────────────────────────────────────────

    print(sep2)
    print("  STABILITY ZONE  (#1 ∩ #2)")
    print(sep2)
    print()
    print(
        f"  Stable rows             : {len(stable)} / {len(rows)}  ({len(stable) / len(rows) * 100:.0f}%)"
    )
    print(f"  Thematic method         : {', '.join(stab_mth)}")
    print(f"  SCALE_CONSORTIA_WEIGHT  : {_fmt_range(stab_cw)}  ({len(stab_cw)} levels)")
    print(
        f"  SCOPE_INTERNATIONAL_WEIGHT: {_fmt_range(stab_iw)}  (all — scope does not affect criterion #2)"
    )
    print()

    # Ratios across the stable range
    print(f"  ratio_C_to_B across stable zone")
    print(
        f"  {'consortia_w':>14s}  {'ratio (any intl_w)':>20s}  {'ΔC deficit vs B':>18s}"
    )
    for cw in stab_cw:
        ratio = cw / small_group_w
        deficit = 1.0 - ratio
        print(f"  {cw:>14.1f}  {ratio:>20.4f}  {deficit:>18.4f}")

    print()
    print(f"  Instability boundary    : consortia_weight ≥ {critical_cw:.1f}")
    print(
        f"  At boundary             : ratio_C_to_B = {ratio_at_boundary:.4f}  (Case C = Case B → no penalty)"
    )
    print(f"  Above boundary          : Case C *exceeds* Case B in total C*")
    print(
        f"                            (consortia papers rewarded more than deliberate ones)"
    )
    print()

    # ── Recommendations ───────────────────────────────────────────────────────

    print(sep2)
    print("  Recommendations")
    print(sep2)
    print()
    print(f"  Baseline (config.py)   : consortia_w = 0.2  →  safe, ratio = 0.25")
    print(f"  Conservative upper bound: consortia_w ≤ 0.4  →  ratio ≤ 0.50")
    print(
        f"  Hard ceiling           : consortia_w < {critical_cw:.1f}  (required for stability)"
    )
    print(f"  Thematic               : always use 'proportional_linear'")
    print(
        f"                           (fixed_0.5 inflates sensitive share by +0.30 in Case D)"
    )
    print(
        f"  SCOPE_INTERNATIONAL    : adjust freely — does not affect scale-based criteria"
    )
    print()
    print(sep)
    print()


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    out_path = ROOT / "outputs" / "tables" / "weight_sensitivity_results.csv"

    print(
        f"\n[RUN]  Grid: {len(GRID_CONSORTIA_WEIGHT)} × {len(GRID_INTERNATIONAL_WEIGHT)} × "
        f"{len(THEMATIC_METHODS)} = "
        f"{len(GRID_CONSORTIA_WEIGHT) * len(GRID_INTERNATIONAL_WEIGHT) * len(THEMATIC_METHODS)} combinations"
    )

    rows = run_grid()
    # config.WEIGHTS is never mutated; the grid uses local scalar copies of the weights.
    write_csv(rows, out_path)
    print_stability_summary(rows)


if __name__ == "__main__":
    main()
