"""
engine
------
MENA Scientific Collaboration Analysis Engine.

Canonical public API
--------------------
ResearchPipeline     — full pipeline runner (engine.orchestrator)
NetworkAnalyst       — data retrieval and graph analysis (engine.processor)
ThematicAnalyst      — H4 thematic contingency logic (engine.processor)
Reporter             — console / LaTeX / CSV output (engine.reporter)
ScientificVisualizer — publication-quality figures (engine.visuals)

Backward-compat aliases (for existing test-suite imports)
---------------------------------------------------------
ScientificWorkflow = ResearchPipeline
ScientificAnalyzer = NetworkAnalyst
"""

from engine.orchestrator import ResearchPipeline
from engine.processor import NetworkAnalyst, ThematicAnalyst
from engine.reporter import Reporter
from engine.visuals import ScientificVisualizer

# Backward-compat aliases
ScientificWorkflow = ResearchPipeline
ScientificAnalyzer = NetworkAnalyst

__all__ = [
    "ResearchPipeline",
    "NetworkAnalyst",
    "ThematicAnalyst",
    "Reporter",
    "ScientificVisualizer",
    "ScientificWorkflow",
    "ScientificAnalyzer",
]
