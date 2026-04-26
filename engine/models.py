"""
engine/models.py
----------------
Typed data structures for the MENA Scientific Collaboration Pipeline.

All classes use ``@dataclass`` with strict type annotations so that every
stage of the pipeline has a clear, inspectable data contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Threshold calibration
# ---------------------------------------------------------------------------


@dataclass
class SensitivityRecord:
    """One row of the threshold-sensitivity sweep (one candidate N value)."""

    n_threshold: int
    israel_involved_c_star: float
    non_israel_c_star: float
    ratio_isr_non: float
    growth_isr: float = 0.0


# ---------------------------------------------------------------------------
# Dyad-level affinity
# ---------------------------------------------------------------------------


@dataclass
class DyadAffinityRecord:
    """Per-year collaboration metrics for a single country pair."""

    year: int
    p_i: float
    p_j: float
    c_star: float
    affinity_s: float


# ---------------------------------------------------------------------------
# Network topology
# ---------------------------------------------------------------------------


@dataclass
class CentralityRecord:
    """Annual centrality snapshot for the target country at key study years."""

    year: int
    density: float
    avg_clustering: float
    modularity_q: float
    ec: float
    ec_rank: int
    bc: float
    bc_rank: int
    peers: str


# ---------------------------------------------------------------------------
# Run reproducibility
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """
    Immutable snapshot of all experiment-tuning parameters for a single run.

    Embed in ``run_metadata.json`` to guarantee full reproducibility: every
    numerical result can be traced back to a specific parameter combination.
    """

    deliberate_np_threshold: int
    scale_small: float
    scale_cons: float
    scope_domestic: float
    scope_intl: float
    thematic_method: str
    start_year: int
    end_year: int

    @classmethod
    def from_config(cls) -> "PipelineConfig":
        """Build a snapshot from the current live ``config`` module values."""
        import config  # local import avoids circular dependency at module load

        return cls(
            deliberate_np_threshold=config.DELIBERATE_NP_THRESHOLD,
            scale_small=config.WEIGHTS["SCALE"]["small"],
            scale_cons=config.WEIGHTS["SCALE"]["cons"],
            scope_domestic=config.WEIGHTS["SCOPE"]["domestic"],
            scope_intl=config.WEIGHTS["SCOPE"]["intl"],
            thematic_method=config.THEMATIC_METHOD,
            start_year=config.START_YEAR,
            end_year=config.END_YEAR,
        )

    def to_dict(self) -> Dict[str, object]:
        """Serialise to a plain dict suitable for JSON export."""
        return {
            "deliberate_np_threshold": self.deliberate_np_threshold,
            "weights": {
                "SCALE": {"small": self.scale_small, "cons": self.scale_cons},
                "SCOPE": {"domestic": self.scope_domestic, "intl": self.scope_intl},
            },
            "thematic_method": self.thematic_method,
            "start_year": self.start_year,
            "end_year": self.end_year,
        }


# ---------------------------------------------------------------------------
# Backward-compatibility re-exports
# ScientificWorkflow was previously defined in this file; it now lives in
# engine.orchestrator as ResearchPipeline.  Old test-suite imports continue
# to work without modification.
# ---------------------------------------------------------------------------


def __getattr__(name: str):
    if name in ("ScientificWorkflow", "ResearchPipeline"):
        from engine.orchestrator import ResearchPipeline  # noqa: PLC0415
        return ResearchPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
