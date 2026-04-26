"""
engine/analyzer.py
------------------
Backward-compatibility shim.

``ScientificAnalyzer`` has been superseded by ``NetworkAnalyst`` in
``engine.processor``.  This module re-exports the new class under the old
name so that existing test-suite imports continue to work without
modification.

Prefer importing from ``engine.processor`` directly in new code.
"""

from engine.processor import NetworkAnalyst  # noqa: F401

ScientificAnalyzer = NetworkAnalyst

__all__ = ["ScientificAnalyzer"]
