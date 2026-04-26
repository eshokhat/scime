"""
utils/dyad.py
-------------
Backward-compatibility shim.

Dyad classification functions have been consolidated into ``engine.utils``
(the canonical location).  This module re-exports them so that existing
imports of ``from utils.dyad import ...`` continue to work.

Prefer importing from ``engine.utils`` directly in new code.
"""

from engine.utils import (  # noqa: F401
    is_israel_dyad,
    is_fractured_dyad,
    classify_dyad_h2a,
    classify_dyad_h2b,
)

__all__ = [
    "is_israel_dyad",
    "is_fractured_dyad",
    "classify_dyad_h2a",
    "classify_dyad_h2b",
]
