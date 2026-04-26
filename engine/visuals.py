from __future__ import annotations

from typing import Dict, List

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from networkx.algorithms import community
from pyvis.network import Network

import config


class ScientificVisualizer:
    """
    Handles publication-quality visualization for the research pipeline.
    All figures are saved to config.FIGURES_DIR.
    """

    PALETTE = {
        "israel": "#e74c3c",
        "control": "#3498db",
        "destabilized": "#e67e22",
        "norm": "#27ae60",
        "nonnorm": "#8e44ad",
        "pre": "#2980b9",
        "post": "#c0392b",
    }

    def __init__(self):
        self.figures_dir = config.FIGURES_DIR
        plt.style.use("seaborn-v0_8-paper")
        plt.rcParams.update(
            {
                "font.family": "serif",
                "font.size": 12,
                "figure.autolayout": True,
                "axes.titlesize": 14,
                "savefig.dpi": 300,
            }
        )

    def _save(self, filename: str):
        """Save the current figure to the configured figures directory."""
        path = str(self.figures_dir / filename)
        plt.savefig(path, bbox_inches="tight")
        plt.close()
        return path

    def plot_threshold_sensitivity(self, res_df: pd.DataFrame, optimal_n: int) -> None:
        """
        Elbow-curve chart for the deliberate collaboration threshold calibration.

        Left axis  — raw C* curves for Israel-Involved and Non-Israel dyads.
        Right axis — marginal growth rate of the Israel-Involved curve.
        Vertical dashed line marks the detected elbow (optimal N).
        """
        fig, ax1 = plt.subplots(figsize=(11, 6))

        # Primary curves
        ax1.plot(
            res_df["n_threshold"],
            res_df["israel_involved_c_star"],
            "o-",
            color=self.PALETTE["israel"],
            linewidth=2,
            label="Israel-Involved (C*)",
        )
        ax1.plot(
            res_df["n_threshold"],
            res_df["non_israel_c_star"],
            "s-",
            color=self.PALETTE["control"],
            linewidth=2,
            label="Non-Israel (C*)",
        )
        ax1.set_xlabel("Country-Count Threshold (N)")
        ax1.set_ylabel("Collaboration Strength (Sum of C*)")

        # Growth rate on secondary axis
        ax2 = ax1.twinx()
        ax2.plot(
            res_df["n_threshold"],
            res_df["growth_isr"] * 100,
            "D--",
            color="gray",
            alpha=0.55,
            linewidth=1.5,
            label="Marginal Growth Rate (%)",
        )
        ax2.set_ylabel("Marginal Growth Rate of Israel-Involved C* (%)", color="gray")
        ax2.tick_params(axis="y", labelcolor="gray")
        ax2.axhline(0, color="gray", linewidth=0.5, linestyle=":")

        # Elbow marker
        ax1.axvline(optimal_n, color="black", linestyle="--", alpha=0.8, linewidth=1.5)
        ax1.text(
            optimal_n + 0.3,
            ax1.get_ylim()[1] * 0.92,
            f"Selected N = {optimal_n}",
            fontsize=11,
            fontweight="bold",
            color="black",
        )

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True)

        ax1.set_title(
            "Threshold Sensitivity Analysis: Identifying Deliberate Collaboration Filter\n"
            r"Elbow = point where adding higher-$N$ papers yields diminishing signal",
            fontsize=13,
        )
        ax1.grid(True, alpha=0.2)
        self._save("threshold_sensitivity_elbow.png")

    def plot_affinity_trends(self, df: pd.DataFrame, target: str, compare: str) -> None:
        arab_spring = config.GEOPOLITICAL_MARKERS["ARAB_SPRING"]
        abraham_accords = config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(
            df["year"],
            df["affinity_s_unr"],
            "o-",
            label=r"$S_{unrestricted}$",
            color="gray",
            alpha=0.4,
        )
        ax.plot(
            df["year"],
            df["affinity_s_del"],
            "s-",
            label=r"$S_{deliberate}$",
            color="blue",
            linewidth=2,
        )

        ymax = df[["affinity_s_unr", "affinity_s_del"]].max().max()
        ax.axvline(arab_spring, color="darkred", linestyle="--", alpha=0.7)
        ax.text(arab_spring + 0.2, ymax * 0.9, "Arab Spring", color="darkred")
        ax.axvline(abraham_accords, color="darkgreen", linestyle="--", alpha=0.7)
        ax.text(abraham_accords + 0.2, ymax * 0.9, "Abraham Accords", color="darkgreen")

        ax.set_title(f"Scientific Affinity Trend: {target.upper()} - {compare.upper()}")
        ax.set_xlabel("Year")
        ax.set_ylabel(r"Salton's Index ($S_{ij}$)")
        ax.legend()
        ax.grid(False)
        self._save(f"affinity_{target}_{compare}.png")

    def plot_h1_mirage(self, fractured_median: float, control_median: float) -> None:
        fig, ax = plt.subplots(figsize=(6, 5))
        bars = ax.bar(
            ["Israel-Regional", "Control"],
            [fractured_median, control_median],
            color=[self.PALETTE["israel"], self.PALETTE["control"]],
        )
        for bar, val in zip(bars, [fractured_median, control_median]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.001,
                f"{val:.4f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )
        ax.set_title(r"H1: Median Reliance on Mega-Science ($\Delta C$)")
        ax.set_ylabel("Index Value")
        ax.grid(False)
        self._save("h1_mirage_comparison.png")

    def plot_h1_mirage_2(self, df: pd.DataFrame) -> None:
        plot_df = df.copy()
        plot_df["group"] = plot_df.apply(
            lambda r: (
                "Israel-Regional"
                if "israel" in {r["c_i"], r["c_j"]}
                else "Intra-Regional"
            ),
            axis=1,
        )
        plot_data = plot_df[plot_df["delta_c"] > 0.01]
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.boxplot(
            x="group",
            y="delta_c",
            hue="group",
            data=plot_data,
            palette={
                "Israel-Regional": self.PALETTE["israel"],
                "Intra-Regional": self.PALETTE["control"],
            },
            order=["Israel-Regional", "Intra-Regional"],
            legend=False,
            ax=ax,
        )
        ax.set_yscale("log")
        ax.set_ylim(1e-3, 1.1)
        ax.set_title(r"H1: Distribution of Mega-Science Reliance ($\Delta C$)")
        ax.set_xlabel("Region Group")
        ax.set_ylabel("Index Value (Log Scale)")
        self._save("h1_mirage_distribution.png")

    def plot_h3_centrality_comparison(
        self,
        years: List[int],
        ec_scores: List[float],
        bc_scores: List[float],
        country: str,
    ) -> None:
        """
        Dual-axis chart: Eigenvector Centrality (left) vs Betweenness Centrality (right)
        over the full study period, with key political event markers.
        """
        fig, ax1 = plt.subplots(figsize=(12, 6))
        color_ec, color_bc = "#8e44ad", "#27ae60"

        ax1.plot(
            years,
            ec_scores,
            "D-",
            color=color_ec,
            linewidth=2,
            label="Eigenvector Centrality (EC)",
        )
        ax1.fill_between(years, ec_scores, color=color_ec, alpha=0.08)
        ax1.set_xlabel("Year")
        ax1.set_ylabel("Eigenvector Centrality", color=color_ec)
        ax1.tick_params(axis="y", labelcolor=color_ec)

        ax2 = ax1.twinx()
        ax2.plot(
            years,
            bc_scores,
            "s--",
            color=color_bc,
            linewidth=2,
            label="Betweenness Centrality (BC)",
        )
        ax2.fill_between(years, bc_scores, color=color_bc, alpha=0.08)
        ax2.set_ylabel("Betweenness Centrality", color=color_bc)
        ax2.tick_params(axis="y", labelcolor=color_bc)

        _markers = [
            (config.GEOPOLITICAL_MARKERS["ARAB_SPRING"], "Arab Spring", "darkred"),
            (config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"], "Abraham Accords", "navy"),
        ]
        for event_year, label_text, color in _markers:
            ax1.axvline(event_year, color=color, linestyle="--", alpha=0.5)
            ax1.text(
                event_year + 0.3,
                ax1.get_ylim()[1] * 0.95,
                label_text,
                color=color,
                fontsize=9,
                va="top",
            )

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", frameon=True)

        ax1.set_title(
            f"H3: Structural Position of {country.upper()} Over Time\n"
            r"Eigenvector Centrality vs. Betweenness Centrality",
            fontsize=14,
        )
        ax1.grid(True, alpha=0.2)
        self._save(f"h3_centrality_comparison_{country}.png")

    def plot_h4_thematic(self, counts_df: pd.DataFrame) -> None:
        df_perc = counts_df.div(counts_df.sum(axis=1), axis=0) * 100
        ax = df_perc.plot(
            kind="bar",
            stacked=False,
            color=[self.PALETTE["control"], self.PALETTE["israel"]],
            figsize=(8, 6),
        )
        ax.set_title("H4: Thematic Distribution (Neutral vs Sensitive)")
        ax.set_ylabel("Percentage of Total (%)")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
        ax.legend(["Neutral (STEM)", "Sensitive (Social)"])
        ax.grid(False)
        self._save("h4_thematic_bias.png")

    def plot_did_comparison(
        self,
        df: pd.DataFrame,
        group_col: str,
        event_year: int,
        title: str,
        filename: str,
    ) -> None:
        fig, ax = plt.subplots(figsize=(10, 6))
        raw_means = df.groupby(["year", group_col])["s_del"].mean().reset_index()
        sns.scatterplot(
            data=raw_means, x="year", y="s_del", hue=group_col, alpha=0.4, s=60, ax=ax
        )

        df = df.copy()
        df["is_post"] = (df["year"] >= event_year).astype(int)
        levels = df.groupby([group_col, "is_post"])["s_del"].mean().reset_index()
        colors = sns.color_palette("tab10", n_colors=df[group_col].nunique())

        for i, group in enumerate(df[group_col].unique()):
            pre = levels[(levels[group_col] == group) & (levels["is_post"] == 0)][
                "s_del"
            ]
            post = levels[(levels[group_col] == group) & (levels["is_post"] == 1)][
                "s_del"
            ]
            if not pre.empty:
                ax.hlines(
                    pre.values[0],
                    df["year"].min(),
                    event_year - 1,
                    colors=colors[i],
                    linestyles="-",
                    lw=3,
                )
            if not post.empty:
                ax.hlines(
                    post.values[0],
                    event_year,
                    df["year"].max(),
                    colors=colors[i],
                    linestyles="-",
                    lw=3,
                )

        ax.axvline(event_year, color="red", linestyle="--", alpha=0.6)
        ax.set_title(title, fontsize=14)
        ax.set_ylabel("Salton's Index ($S_{ij}$)")
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        self._save(filename)

    def plot_structural_break_search(
        self, history_df: pd.DataFrame, best_year: int, label: str
    ) -> None:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(
            history_df["year"],
            history_df["r2"],
            marker="o",
            color="#2c3e50",
            label="R-squared",
        )
        ax.axvline(
            best_year,
            color=self.PALETTE["post"],
            linestyle="--",
            label=f"Best Year: {best_year}",
        )
        ax.set_title(f"Structural Break Discovery: {label}")
        ax.set_xlabel("Candidate Year")
        ax.set_ylabel("Explanatory Power (Within R2)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        self._save(f"h2c_break_{label.lower().replace(' ', '_')}.png")

    def plot_segmented_break_fit(
        self, df: pd.DataFrame, group_label: str, best_year: int, filename: str
    ) -> None:
        """
        Segmented regression chart for H2c structural break detection.

        Fits two OLS trend lines (pre / post ``best_year``) to the annual
        mean Salton index using ``sns.regplot``.
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        plot_data = df.groupby("year")["s_del"].mean().reset_index()
        ax.scatter(
            plot_data["year"],
            plot_data["s_del"],
            color="#34495e",
            alpha=0.4,
            s=50,
            label="Annual Mean Affinity",
        )

        pre_break = plot_data[plot_data["year"] < best_year]
        post_break = plot_data[plot_data["year"] >= best_year]
        if not pre_break.empty:
            sns.regplot(
                data=pre_break,
                x="year",
                y="s_del",
                scatter=False,
                color=self.PALETTE["pre"],
                label=f"Pre-Break Trend ({config.START_YEAR}–{best_year - 1})",
                line_kws={"lw": 3, "alpha": 0.8},
                ax=ax,
            )
        if not post_break.empty:
            sns.regplot(
                data=post_break,
                x="year",
                y="s_del",
                scatter=False,
                color=self.PALETTE["post"],
                label=f"Post-Break Trend ({best_year}–{config.END_YEAR})",
                line_kws={"lw": 3, "alpha": 0.8},
                ax=ax,
            )

        ax.axvline(best_year, color="black", linestyle="--", alpha=0.5)
        ax.set_title(
            f"Segmented Regression Fit: {group_label}\nStructural Break at {best_year}",
            fontsize=14,
        )
        ax.set_ylabel(r"Salton's Index ($S_{ij}$)")
        ax.set_xlabel("Year")
        ax.legend(frameon=True)
        ax.grid(True, alpha=0.2)
        self._save(filename)

    def plot_network_topology(
        self,
        G: nx.Graph,
        year: int,
        centrality_dict: Dict[str, float],
        title_prefix: str = "",
    ) -> None:
        if not G.nodes():
            return
        fig, ax = plt.subplots(figsize=(14, 10))
        pos = nx.spring_layout(G, k=0.4, iterations=100, seed=42)

        communities_list = list(
            community.greedy_modularity_communities(G, weight="weight")
        )
        node_community = {
            node: i for i, comm in enumerate(communities_list) for node in comm
        }
        cmap = plt.get_cmap("tab10", len(communities_list))
        node_colors = [cmap(node_community[node]) for node in G.nodes()]
        node_sizes = [centrality_dict.get(node, 0.001) * 1000 for node in G.nodes()]
        weights = [d["weight"] * 200 for (_, _, d) in G.edges(data=True)]

        nx.draw_networkx_edges(
            G, pos, width=weights, edge_color="gray", alpha=0.2, ax=ax
        )
        for node in G.nodes():
            idx = list(G.nodes()).index(node)
            shape = "s" if node == "israel" else "o"
            nx.draw_networkx_nodes(
                G,
                pos,
                nodelist=[node],
                node_size=node_sizes[idx],
                node_color=[node_colors[idx]],
                node_shape=shape,
                alpha=0.9,
                edgecolors="black",
                linewidths=0.5,
                ax=ax,
            )
        nx.draw_networkx_labels(
            G, pos, font_size=10, font_family="serif", font_weight="bold", ax=ax
        )
        ax.set_title(
            f"{title_prefix} Regional Scientific Communities ({year})",
            fontsize=16,
            pad=20,
        )
        ax.axis("off")
        ax.annotate(
            f"Detected Communities: {len(communities_list)}\nSquare = Israel, Circle = Others",
            xy=(0.02, 0.02),
            xycoords="axes fraction",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.5),
        )
        self._save(f"h3_clusters_{year}.png")

    def create_interactive_network(self, G: nx.Graph, year: int) -> None:
        net = Network(
            height="750px", width="100%", bgcolor="#ffffff", font_color="black"
        )
        net.from_nx(G)
        net.show_buttons(filter_=["physics"])
        net.save_graph(str(self.figures_dir / f"interactive_network_{year}.html"))
