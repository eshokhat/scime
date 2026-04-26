"""
engine/utils.py
---------------
Pure mathematical formulas and dyad-classification utilities.

Zero external state — every function is a pure function of its inputs.
Import this module wherever a computation is needed; the research engine
itself imports from here to guarantee zero duplication.
"""

from __future__ import annotations

import math
from typing import List, Set

import numpy as np


# ---------------------------------------------------------------------------
# Fractional counting
# ---------------------------------------------------------------------------


def fractional_weight(n_p: int) -> float:
    """
    Per-dyad C* contribution for a paper with *n_p* distinct country affiliations.

    Formula: ``2 / (nₚ · (nₚ − 1))``

    Returns ``0.0`` for ``n_p < 2`` (no cross-country dyad possible).
    """
    if n_p < 2:
        return 0.0
    return 2.0 / (n_p * (n_p - 1))


# ---------------------------------------------------------------------------
# Salton's cosine similarity
# ---------------------------------------------------------------------------


def salton_index(c_star: float, p_i: float, p_j: float) -> float:
    """
    Salton's cosine normalisation of fractional collaboration strength.

    Formula: ``S_ij = C* / √(P_i · P_j)``

    Guards against division-by-zero: returns ``0.0`` when either baseline
    publication count is zero or negative.

    Parameters
    ----------
    c_star : float
        Fractional collaboration strength between countries *i* and *j*.
    p_i, p_j : float
        Total annual publication output for each country.
    """
    if p_i <= 0.0 or p_j <= 0.0:
        return 0.0
    denom = math.sqrt(p_i * p_j)
    if denom == 0.0:
        return 0.0
    return c_star / denom


# ---------------------------------------------------------------------------
# Mega-science reliance metric
# ---------------------------------------------------------------------------


def delta_c_metric(s_unr: float, s_del: float) -> float:
    """
    Mega-science reliance: fraction of apparent collaboration attributable to
    large consortia.

    Formula: ``ΔC = (S_unr − S_del) / S_unr``

    Returns ``0.0`` when ``S_unr ≤ 0`` to prevent division-by-zero.
    The result is guaranteed in ``[0, 1]`` because ``s_del ≤ s_unr`` by
    construction (SCALE weights ≤ 1).
    """
    if s_unr <= 0.0:
        return 0.0
    return (s_unr - s_del) / s_unr


# ---------------------------------------------------------------------------
# Elbow / knee-point detection
# ---------------------------------------------------------------------------


def elbow_detection(x_vals: List[int], y_vals: List[float]) -> int:
    """
    Identify the elbow of a monotone curve via maximum perpendicular distance.

    Normalises both axes to ``[0, 1]``, draws the chord from the first to the
    last point, and returns the x-value at the point of greatest perpendicular
    distance (Kneedle algorithm, no external dependency).

    Parameters
    ----------
    x_vals : list[int]
        Monotonically increasing x values (e.g. N threshold candidates).
    y_vals : list[float]
        Corresponding curve values.

    Returns
    -------
    int
        The x-value at the detected elbow.
    """
    x = np.array(x_vals, dtype=float)
    y = np.array(y_vals, dtype=float)

    x_norm = (x - x.min()) / (x.max() - x.min() + 1e-9)
    y_norm = (y - y.min()) / (y.max() - y.min() + 1e-9)

    p1 = np.array([x_norm[0], y_norm[0]])
    p2 = np.array([x_norm[-1], y_norm[-1]])
    line_vec = p2 - p1
    line_len = float(np.linalg.norm(line_vec)) + 1e-9

    # 2-D cross product via det: |a×b| = |a0*b1 - a1*b0|
    distances = [
        abs(
            line_vec[0] * (p1[1] - y_norm[i]) - line_vec[1] * (p1[0] - x_norm[i])
        ) / line_len
        for i in range(len(x_norm))
    ]
    return int(x_vals[int(np.argmax(distances))])


# ---------------------------------------------------------------------------
# Dyad classification utilities
# (previously utils/dyad.py — canonical location is now engine/utils.py)
# ---------------------------------------------------------------------------


def is_israel_dyad(c_i: str, c_j: str) -> bool:
    """Return ``True`` if either country in the dyad is Israel."""
    return "israel" in {c_i, c_j}


def is_fractured_dyad(c_i: str, c_j: str, normalized_states: Set[str]) -> bool:
    """
    Return ``True`` if the dyad involves Israel and a *non-normalized* partner.

    "Fractured" dyads are Israel–adversary ties that may rely
    disproportionately on mega-consortia for their observed collaboration
    signal (The Mirage Hypothesis, H1).

    Parameters
    ----------
    c_i, c_j : str
        Lowercase, stripped country names.
    normalized_states : set[str]
        Countries with formal diplomatic relations with Israel.
    """
    if not is_israel_dyad(c_i, c_j):
        return False
    other = c_j if c_i == "israel" else c_i
    return other not in normalized_states


def classify_dyad_h2a(c_i: str, c_j: str, destabilized_states: Set[str]) -> str:
    """
    Classify a dyad for the H2a (Arab Spring) DiD model.

    Priority: *destabilized* > *israel* > *stable_control*.

    Returns
    -------
    str
        ``"destabilized"``, ``"israel"``, or ``"stable_control"``.
    """
    countries = {c_i, c_j}
    if any(c in destabilized_states for c in countries):
        return "destabilized"
    if "israel" in countries:
        return "israel"
    return "stable_control"


def classify_dyad_h2b(c_i: str, c_j: str, normalization_set: Set[str]) -> str:
    """
    Classify a dyad for the H2b (Abraham Accords) DiD model.

    Returns
    -------
    str
        ``"norm"``, ``"nonnorm"``, or ``"reference"``.
    """
    countries = {c_i, c_j}
    if "israel" in countries:
        other = (countries - {"israel"}).pop()
        return "norm" if other in normalization_set else "nonnorm"
    return "reference"
