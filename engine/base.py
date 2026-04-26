"""
engine/base.py
--------------
Backward-compatibility shim.

``BaseNetworkAnalyzer`` has been absorbed into ``NetworkAnalyst`` in
``engine.processor``.  This module keeps the old import path valid.
"""

from abc import ABC

import networkx as nx
import pandas as pd
from typing import Dict


class BaseNetworkAnalyzer(ABC):
    """Retained for import compatibility only. Use NetworkAnalyst instead."""

    def _build_annual_graph(self, edges_df: pd.DataFrame) -> nx.Graph:
        G = nx.Graph()
        for _, row in edges_df.iterrows():
            G.add_edge(row["c_i"], row["c_j"], weight=row["s_ij"])
        return G

    def _eigenvector_centrality(self, G: nx.Graph) -> Dict[str, float]:
        if not G.nodes():
            return {}
        try:
            return nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
        except nx.PowerIterationFailedConvergence:
            return nx.eigenvector_centrality_numpy(G, weight="weight")
