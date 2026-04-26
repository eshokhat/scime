"""
engine/processor.py
-------------------
Data-retrieval and graph-analysis layer for the research pipeline.

Classes
-------
NetworkAnalyst
    Database queries, fractional counting, Salton normalisation,
    Deliberate Network graph construction, and eigenvector centrality.
    Implements the core SQL logic for every hypothesis stage.

ThematicAnalyst
    Thematic contingency table construction for H4 (Fisher's Exact Test).
    Separated so that subject-classification logic is independently testable.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import duckdb
import networkx as nx
import pandas as pd

import config
from engine.utils import classify_dyad_h2a, classify_dyad_h2b

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NetworkAnalyst
# ---------------------------------------------------------------------------


class NetworkAnalyst:
    """
    Core analytical engine for scientific collaboration research.

    Implements
    ----------
    - Fractional counting:          C* = Σ 2 / (nₚ(nₚ − 1))
    - Salton's cosine normalisation: S_ij = C* / √(P_i · P_j)
    - Deliberate Network filter:     nₚ ≤ DELIBERATE_NP_THRESHOLD
    - Eigenvector / Betweenness Centrality via NetworkX
    - Panel-data preparation for H2a (Arab Spring) and H2b (Abraham Accords)
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = db_path or config.DB_PATH
        try:
            self.conn: duckdb.DuckDBPyConnection = duckdb.connect(
                path, read_only=True
            )
        except Exception as exc:
            logger.error("Failed to open DuckDB at %s: %s", path, exc)
            raise
        self.mena_countries: tuple[str, ...] = tuple(config.COUNTRIES_LIST)
        # Per-run affinity cache: keyed on DELIBERATE_NP_THRESHOLD so the
        # cache is invalidated automatically when the threshold changes.
        self._affinity_cache: Dict[int, pd.DataFrame] = {}
        logger.debug("NetworkAnalyst connected to %s", path)

    def close(self) -> None:
        """Release the database connection."""
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self) -> "NetworkAnalyst":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Basic metrics
    # ------------------------------------------------------------------

    def get_basic_metrics(self) -> Dict[str, int]:
        """Return high-level dataset statistics."""
        try:
            query = f"SELECT COUNT(*) FROM {config.TABLES['articles']}"
            total: int = self.conn.execute(query).fetchone()[0]
            return {"total_papers": total}
        except Exception as exc:
            logger.error("get_basic_metrics failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Threshold calibration
    # ------------------------------------------------------------------

    def fetch_sensitivity_stats(self, n_threshold: int) -> pd.DataFrame:
        """
        Compute total fractional C* split by group type for a given threshold.

        Parameters
        ----------
        n_threshold : int
            Upper bound on distinct country affiliations per paper.

        Returns
        -------
        pd.DataFrame
            Columns: ``group_type`` (``"Israel-Involved"`` | ``"Non-Israel"``),
            ``c_star``.
        """
        query = f"""
            WITH paper_stats AS (
                SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
                FROM {config.TABLES["countries"]}
                GROUP BY eid
                HAVING np <= {n_threshold} AND np > 1
            ),
            dyad_weights AS (
                SELECT
                    CASE
                        WHEN 'israel' IN (LOWER(TRIM(c1.country)), LOWER(TRIM(c2.country)))
                        THEN 'Israel-Involved'
                        ELSE 'Non-Israel'
                    END AS group_type,
                    SUM(2.0 / (ps.np * (ps.np - 1))) AS c_star
                FROM {config.TABLES["articles"]} a
                JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
                JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
                JOIN paper_stats ps ON a.eid = ps.eid
                WHERE LOWER(TRIM(c1.country)) < LOWER(TRIM(c2.country))
                GROUP BY 1
            )
            SELECT group_type, c_star FROM dyad_weights
        """
        try:
            return self.conn.sql(query).df()
        except Exception as exc:
            logger.error("fetch_sensitivity_stats(n=%d) failed: %s", n_threshold, exc)
            raise

    # ------------------------------------------------------------------
    # Country time series
    # ------------------------------------------------------------------

    def fetch_country_timeseries(
        self,
        country: str,
        mode: str = "raw",
        max_countries: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Annual publication counts for a specific country.

        Parameters
        ----------
        country : str
            Country name (case-insensitive).
        mode : {"raw", "fractional"}
            ``"raw"`` → each paper counts as 1.
            ``"fractional"`` → weight by ``1/nₚ``.
        max_countries : int, optional
            Deliberate Network filter (``nₚ ≤ max_countries``).
        """
        country = country.lower().strip()
        limit_clause = (
            f"HAVING COUNT(DISTINCT LOWER(TRIM(country))) <= {max_countries}"
            if max_countries
            else ""
        )
        weight_expr = (
            "1.0" if mode == "raw" else "1.0 / COUNT(DISTINCT LOWER(TRIM(country)))"
        )

        query = f"""
            WITH paper_weights AS (
                SELECT eid, {weight_expr} AS weight
                FROM {config.TABLES["countries"]}
                GROUP BY eid
                {limit_clause}
            )
            SELECT a.year, SUM(pw.weight) AS production
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c ON a.eid = c.eid
            JOIN paper_weights pw ON a.eid = pw.eid
            WHERE LOWER(TRIM(c.country)) = '{country}'
            GROUP BY a.year ORDER BY a.year
        """
        try:
            return self.conn.sql(query).df()
        except Exception as exc:
            logger.error("fetch_country_timeseries(%s) failed: %s", country, exc)
            raise

    # ------------------------------------------------------------------
    # Dyad affinity (C* and Salton's S)
    # ------------------------------------------------------------------

    def calculate_dyad_affinity(
        self,
        country_a: str,
        country_b: str,
        max_countries: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fractional collaboration strength (C*) and Salton's Index (S) for a
        single country pair across all available years.

        Methodology (Step 1)
        --------------------
        C*_ij,t = Σ_{p ∈ P_ij,t}  2 / (nₚ(nₚ − 1))
        S_ij,t  = C*_ij,t / √(P_i,t · P_j,t)

        ``S = 0`` when either baseline is zero (guarded division).

        Parameters
        ----------
        country_a, country_b : str
            Country names (case-insensitive).
        max_countries : int, optional
            Deliberate Network threshold (``nₚ ≤ max_countries``).
        """
        country_a = country_a.lower().strip()
        country_b = country_b.lower().strip()
        limit_clause = (
            f"HAVING np <= {max_countries}" if max_countries else ""
        )

        query = f"""
            WITH paper_stats AS (
                SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
                FROM {config.TABLES["countries"]}
                GROUP BY eid
                {limit_clause}
            ),
            collaboration_weights AS (
                SELECT a.year, 2.0 / (ps.np * (ps.np - 1)) AS edge_weight
                FROM {config.TABLES["articles"]} a
                JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
                JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
                JOIN paper_stats ps ON a.eid = ps.eid
                WHERE LOWER(TRIM(c1.country)) = '{country_a}'
                  AND LOWER(TRIM(c2.country)) = '{country_b}'
                  AND ps.np > 1
            ),
            aggregated_c_star AS (
                SELECT year, SUM(edge_weight) AS c_star
                FROM collaboration_weights GROUP BY year
            ),
            baselines AS (
                SELECT b1.year, b1.total_output AS p_i, b2.total_output AS p_j
                FROM {config.TABLES["baseline"]} b1
                JOIN {config.TABLES["baseline"]} b2 ON b1.year = b2.year
                WHERE LOWER(TRIM(b1.country)) = '{country_a}'
                  AND LOWER(TRIM(b2.country)) = '{country_b}'
            )
            SELECT
                b.year,
                b.p_i,
                b.p_j,
                COALESCE(ac.c_star, 0) AS c_star,
                CASE
                    WHEN b.p_i > 0 AND b.p_j > 0
                    THEN COALESCE(ac.c_star, 0) / SQRT(b.p_i * b.p_j)
                    ELSE 0
                END AS affinity_s
            FROM baselines b
            LEFT JOIN aggregated_c_star ac ON b.year = ac.year
            ORDER BY b.year
        """
        try:
            return self.conn.sql(query).df()
        except Exception as exc:
            logger.error(
                "calculate_dyad_affinity(%s, %s) failed: %s", country_a, country_b, exc
            )
            raise

    # ------------------------------------------------------------------
    # Regional affinity matrix — H1, H2a, H2b foundation
    # ------------------------------------------------------------------

    def fetch_regional_affinity_data(self) -> pd.DataFrame:
        """
        Full regional dyad × year affinity table (S_unr, S_del, ΔC).

        Both Unrestricted (S_unr) and Deliberate-Network (S_del) normalised
        affinities are computed, plus the mega-science reliance metric:

            ΔC_ij,t = (S_unr − S_del) / S_unr   [only where S_unr > 0]

        Results are cached per ``DELIBERATE_NP_THRESHOLD`` to avoid
        redundant DB round-trips when H1, H2a and H2b all call this method.

        Zero-collaboration dyad-years are kept (S = 0, ΔC = 0) for panel
        balance.
        """
        threshold = config.DELIBERATE_N
        if threshold in self._affinity_cache:
            logger.debug("fetch_regional_affinity_data: cache hit (N=%d)", threshold)
            return self._affinity_cache[threshold].copy()

        small_w = config.WEIGHTS["SCALE"]["small"]
        cons_w = config.WEIGHTS["SCALE"]["cons"]

        query = f"""
            WITH paper_stats AS (
                SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
                FROM {config.TABLES["countries"]} GROUP BY eid
            ),
            pair_weights AS (
                SELECT
                    a.year,
                    LOWER(TRIM(c1.country)) AS c_i,
                    LOWER(TRIM(c2.country)) AS c_j,
                    ps.np,
                    2.0 / (ps.np * (ps.np - 1)) AS weight
                FROM {config.TABLES["articles"]} a
                JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
                JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
                JOIN paper_stats ps ON a.eid = ps.eid
                WHERE c_i < c_j AND ps.np > 1
            ),
            dyad_annual AS (
                SELECT year, c_i, c_j,
                    SUM(weight) AS c_unr,
                    SUM(
                        CASE WHEN np <= {threshold}
                            THEN weight * {small_w}
                            ELSE weight * {cons_w}
                        END
                    ) AS c_del
                FROM pair_weights GROUP BY 1, 2, 3
            ),
            all_possible_dyads AS (
                SELECT
                    b1.year,
                    LOWER(TRIM(b1.country)) AS c_i,
                    LOWER(TRIM(b2.country)) AS c_j,
                    b1.total_output AS p_i,
                    b2.total_output AS p_j
                FROM {config.TABLES["baseline"]} b1
                JOIN {config.TABLES["baseline"]} b2 ON b1.year = b2.year
                WHERE c_i < c_j
            )
            SELECT
                ad.year, ad.c_i, ad.c_j,
                COALESCE(d.c_unr, 0) / SQRT(ad.p_i * ad.p_j) AS s_unr,
                COALESCE(d.c_del, 0) / SQRT(ad.p_i * ad.p_j) AS s_del
            FROM all_possible_dyads ad
            LEFT JOIN dyad_annual d
                ON ad.year = d.year AND ad.c_i = d.c_i AND ad.c_j = d.c_j
            WHERE ad.p_i > 0 AND ad.p_j > 0
        """
        try:
            df: pd.DataFrame = self.conn.sql(query).df()
        except Exception as exc:
            logger.error("fetch_regional_affinity_data failed: %s", exc)
            raise

        df["delta_c"] = 0.0
        mask = df["s_unr"] > 0
        df.loc[mask, "delta_c"] = (
            df.loc[mask, "s_unr"] - df.loc[mask, "s_del"]
        ) / df.loc[mask, "s_unr"]

        self._affinity_cache[threshold] = df
        return df.copy()

    def clear_affinity_cache(self) -> None:
        """Invalidate the regional affinity cache (call after threshold update)."""
        self._affinity_cache.clear()
        logger.debug("Affinity cache cleared.")

    # ------------------------------------------------------------------
    # H2a panel data (Arab Spring DiD)
    # ------------------------------------------------------------------

    def format_did_panel_data(self) -> pd.DataFrame:
        """
        Panel dataset for H2a (Arab Spring Difference-in-Differences).

        Added columns: ``h2a_group``, ``post_2011``, ``time_since_2011``,
        ``destab_post``, ``destab_trend_slope``, ``israel_post``, ``dyad_id``.
        """
        df = self.fetch_regional_affinity_data()
        destabilized = {"egypt", "syria", "libya", "yemen", "tunisia"}
        arab_spring = config.GEOPOLITICAL_MARKERS["ARAB_SPRING"]

        df["h2a_group"] = df.apply(
            lambda r: classify_dyad_h2a(r["c_i"], r["c_j"], destabilized),
            axis=1,
        )
        df["post_2011"] = (df["year"] >= arab_spring).astype(int)
        df["time_since_2011"] = (df["year"] - arab_spring).clip(lower=0)
        df["destab_post"] = (
            (df["h2a_group"] == "destabilized").astype(int) * df["post_2011"]
        )
        df["destab_trend_slope"] = (
            (df["h2a_group"] == "destabilized").astype(int) * df["time_since_2011"]
        )
        df["israel_post"] = (
            (df["h2a_group"] == "israel").astype(int) * df["post_2011"]
        )
        df["dyad_id"] = df["c_i"] + "_" + df["c_j"]
        return df

    # ------------------------------------------------------------------
    # H2b panel data (Abraham Accords DiD)
    # ------------------------------------------------------------------

    def prepare_h2b_dataset(self) -> pd.DataFrame:
        """
        Panel dataset for H2b (Abraham Accords Difference-in-Differences).

        Added columns: ``h2b_group``, ``post_2020``, ``time_since_2020``,
        ``norm_post``, ``nonnorm_post``, ``norm_trend_slope``,
        ``nonnorm_trend_slope``, ``dyad_id``.
        """
        df = self.fetch_regional_affinity_data()
        normalization_set = {"united arab emirates", "bahrain", "morocco"}
        accords = config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"]

        df["h2b_group"] = df.apply(
            lambda r: classify_dyad_h2b(r["c_i"], r["c_j"], normalization_set),
            axis=1,
        )
        df["post_2020"] = (df["year"] >= accords).astype(int)
        df["time_since_2020"] = (df["year"] - accords).clip(lower=0)
        df["norm_post"] = (
            (df["h2b_group"] == "norm") & (df["post_2020"] == 1)
        ).astype(int)
        df["nonnorm_post"] = (
            (df["h2b_group"] == "nonnorm") & (df["post_2020"] == 1)
        ).astype(int)
        df["norm_trend_slope"] = (
            (df["h2b_group"] == "norm").astype(int) * df["time_since_2020"]
        )
        df["nonnorm_trend_slope"] = (
            (df["h2b_group"] == "nonnorm").astype(int) * df["time_since_2020"]
        )
        df["dyad_id"] = df["c_i"] + "_" + df["c_j"]
        return df

    # ------------------------------------------------------------------
    # H3 network centrality
    # ------------------------------------------------------------------

    def compute_network_centrality(self, year: int) -> Dict[str, float]:
        """
        Eigenvector Centrality for the Deliberate Network in a given year.

        Returns an empty dict when the graph is empty or if the power-iteration
        solver fails to converge (both handled gracefully).

        Note: unlike ``_eigenvector_centrality``, this public method returns
        ``{}`` on convergence failure rather than falling back to numpy — the
        behaviour expected by external callers and the test suite.
        """
        query = self._get_h3_query(year)
        try:
            edges_df: pd.DataFrame = self.conn.sql(query).df()
        except Exception as exc:
            logger.warning("compute_network_centrality(year=%d) query failed: %s", year, exc)
            return {}

        G = self._build_annual_graph(edges_df)
        if not G.nodes():
            return {}
        try:
            return nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
        except (
            nx.PowerIterationFailedConvergence,
            nx.exception.NetworkXPointlessConcept,
        ):
            return {}

    # ------------------------------------------------------------------
    # Graph utilities (previously in engine/base.py)
    # ------------------------------------------------------------------

    def _build_annual_graph(self, edges_df: pd.DataFrame) -> nx.Graph:
        """
        Build a weighted undirected collaboration network from an edge list.

        Each row → one edge with ``weight = s_ij`` (Salton-normalised C*).
        Returns an empty ``nx.Graph`` when ``edges_df`` is empty.
        """
        G = nx.Graph()
        if edges_df.empty:
            return G
        # Vectorised bulk-add is faster than row iteration for large edge lists.
        for _, row in edges_df.iterrows():
            G.add_edge(row["c_i"], row["c_j"], weight=float(row["s_ij"]))
        return G

    def _eigenvector_centrality(self, G: nx.Graph) -> Dict[str, float]:
        """
        Eigenvector Centrality with fallback to the numpy eigensolver.

        The power-iteration solver (``nx.eigenvector_centrality``) can fail to
        converge on sparse annual networks; the numpy fallback is always exact.
        """
        if not G.nodes():
            return {}
        try:
            return nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
        except nx.PowerIterationFailedConvergence:
            logger.debug("EC power-iteration did not converge; falling back to numpy solver.")
            return nx.eigenvector_centrality_numpy(G, weight="weight")
        except nx.exception.NetworkXPointlessConcept:
            return {}

    # ------------------------------------------------------------------
    # H4 thematic contingency table
    # Provided here so that the orchestrator can access it through the
    # single NetworkAnalyst reference (thematic logic shares the DB conn).
    # ThematicAnalyst is a standalone class for isolated testing / direct use.
    # ------------------------------------------------------------------

    def get_thematic_contingency_table(self) -> pd.DataFrame:
        """
        Construct the 2 × 2 thematic contingency table for H4.

        Delegates to ``ThematicAnalyst`` via a shared connection, avoiding
        a second DB open.  See ``ThematicAnalyst.get_contingency_table`` for
        full documentation.
        """
        ta = ThematicAnalyst.__new__(ThematicAnalyst)
        ta.conn = self.conn
        return ta.get_contingency_table()

    # ------------------------------------------------------------------
    # Private SQL helpers
    # ------------------------------------------------------------------

    def _get_h3_query(self, year: int) -> str:
        """
        SQL for the annual Deliberate Network edge list used in H3.

        Filters papers to ``nₚ ≤ DELIBERATE_NP_THRESHOLD``, computes C* per
        dyad with the SCALE small-group weight, and normalises by Salton's
        cosine using baseline country outputs.
        """
        threshold = config.DELIBERATE_N
        small_w = config.WEIGHTS["SCALE"]["small"]

        return f"""
            WITH paper_stats AS (
                SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
                FROM {config.TABLES["countries"]}
                GROUP BY eid
                HAVING np <= {threshold}
            ),
            dyad_weights AS (
                SELECT
                    LOWER(TRIM(c1.country)) AS c_i,
                    LOWER(TRIM(c2.country)) AS c_j,
                    SUM(2.0 / (ps.np * (ps.np - 1)) * {small_w}) AS c_star
                FROM {config.TABLES["articles"]} a
                JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
                JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
                JOIN paper_stats ps ON a.eid = ps.eid
                WHERE a.year = {year} AND c_i < c_j
                GROUP BY 1, 2
            )
            SELECT
                dw.c_i,
                dw.c_j,
                (dw.c_star / SQRT(b1.total_output * b2.total_output)) AS s_ij
            FROM dyad_weights dw
            JOIN {config.TABLES["baseline"]} b1
                ON dw.c_i = LOWER(TRIM(b1.country)) AND b1.year = {year}
            JOIN {config.TABLES["baseline"]} b2
                ON dw.c_j = LOWER(TRIM(b2.country)) AND b2.year = {year}
            WHERE b1.total_output > 0 AND b2.total_output > 0
        """


# ---------------------------------------------------------------------------
# ThematicAnalyst
# ---------------------------------------------------------------------------


class ThematicAnalyst:
    """
    H4 thematic contingency table builder.

    Applies proportional fractional counting to classify collaboration papers
    as Neutral (exact sciences) or Sensitive (social / political sciences),
    then builds the 2 × 2 table for Fisher's Exact Test.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = db_path or config.DB_PATH
        try:
            self.conn: duckdb.DuckDBPyConnection = duckdb.connect(
                path, read_only=True
            )
        except Exception as exc:
            logger.error("ThematicAnalyst: failed to open DuckDB at %s: %s", path, exc)
            raise

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self) -> "ThematicAnalyst":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def get_contingency_table(self) -> pd.DataFrame:
        """
        Construct the 2 × 2 thematic contingency table for H4.

        Rows   : Israel–Arab dyads vs. all-other regional dyads (control).
        Columns: Neutral (STEM + clinical medicine) vs. Sensitive subjects.

        Fractional counting rule (THEMATIC_METHOD = 'proportional'):
        - Pure neutral paper   → +1.0 Neutral
        - Pure sensitive paper → +1.0 Sensitive
        - Mixed paper          → split ∝ subject-field counts

        Only Deliberate Network papers (``nₚ ≤ DELIBERATE_NP_THRESHOLD``) are
        included.

        Returns
        -------
        pd.DataFrame
            Indexed by ``["israel_arab", "control"]``,
            columns ``["neutral", "sensitive"]``.
        """
        arab_states = {
            c for c in config.COUNTRIES_LIST
            if c not in {"israel", "iran", "turkey"}
        }
        neutral_pattern = "|".join(config.NEUTRAL_FIELDS)
        threshold = config.DELIBERATE_N

        query = f"""
            WITH paper_themes AS (
                SELECT eid,
                    SUM(CASE
                        WHEN LOWER(subject) SIMILAR TO '.*({neutral_pattern}).*'
                        THEN 1 ELSE 0
                    END) AS n_count,
                    SUM(CASE
                        WHEN LOWER(subject) NOT SIMILAR TO '.*({neutral_pattern}).*'
                        THEN 1 ELSE 0
                    END) AS s_count
                FROM {config.TABLES["subjects"]} GROUP BY eid
            ),
            collaborations AS (
                SELECT a.eid, LIST(DISTINCT LOWER(TRIM(c.country))) AS countries
                FROM {config.TABLES["articles"]} a
                JOIN {config.TABLES["countries"]} c ON a.eid = c.eid
                GROUP BY a.eid
                HAVING COUNT(DISTINCT country) > 1
                   AND COUNT(DISTINCT country) <= {threshold}
            )
            SELECT c.countries, pt.n_count, pt.s_count
            FROM collaborations c JOIN paper_themes pt ON c.eid = pt.eid
            WHERE pt.n_count > 0 OR pt.s_count > 0
        """
        try:
            data: pd.DataFrame = self.conn.sql(query).df()
        except Exception as exc:
            logger.error("get_contingency_table query failed: %s", exc)
            raise

        table: dict[str, dict[str, float]] = {
            "israel_arab": {"neutral": 0.0, "sensitive": 0.0},
            "control":     {"neutral": 0.0, "sensitive": 0.0},
        }
        method = config.THEMATIC_METHOD

        for _, row in data.iterrows():
            c_set = set(row["countries"])
            is_isr_arab = "israel" in c_set and any(c in arab_states for c in c_set)
            grp = "israel_arab" if is_isr_arab else "control"

            n, s = float(row["n_count"]), float(row["s_count"])
            total = n + s
            if total == 0.0:
                continue

            if n > 0 and s > 0 and method == "proportional":
                table[grp]["neutral"]   += n / total
                table[grp]["sensitive"] += s / total
            elif n > 0 and s > 0:
                # fixed_0.5 fallback
                table[grp]["neutral"]   += 0.5
                table[grp]["sensitive"] += 0.5
            elif n > 0:
                table[grp]["neutral"] += 1.0
            else:
                table[grp]["sensitive"] += 1.0

        return pd.DataFrame(table).T
