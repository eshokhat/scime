"""
api.py
------
FastAPI web server exposing the MENA scientometrics pipeline as a REST API
for the interactive visualization frontend.

Run:
    uvicorn api:app --reload --port 10000

Endpoints:
    GET /api/config
    GET /api/metrics?target=<country>&compare=<country>[&np_threshold=N&w_small=F&w_cons=F]
"""

from __future__ import annotations

import logging
import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import duckdb
import networkx as nx
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader

import config

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_API_KEY = os.getenv("API_KEY", "")
if _API_KEY:
    logger.info("API Key loaded successfully.")
else:
    logger.warning("API Key missing — server is running WITHOUT authentication.")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_key(key: Optional[str] = Security(_api_key_header)) -> None:
    if _API_KEY and key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


app = FastAPI(title="MENA Scientometrics API", version="1.0.0")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_cors_origins = (
    [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]
)
logger.info("CORS allowed origins: %s", _cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend is running"}


_NEUTRAL_PATTERN = "|".join(config.NEUTRAL_FIELDS)
_VALID_COUNTRIES = set(config.COUNTRIES_LIST)
_ACCORDS_YEAR = config.GEOPOLITICAL_MARKERS["ABRAHAM_ACCORDS"]


# ---------------------------------------------------------------------------
# DB context manager
# ---------------------------------------------------------------------------


@contextmanager
def _db() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = duckdb.connect(config.DB_PATH, read_only=True)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SQL builders
# ---------------------------------------------------------------------------


def _h1_sql(target: str, threshold: int) -> str:
    """Annual total and regional (≤threshold countries) paper counts for target."""
    return f"""
        WITH paper_nps AS (
            SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
            FROM {config.TABLES["countries"]}
            GROUP BY eid
        ),
        target_papers AS (
            SELECT a.eid, a.year
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c ON a.eid = c.eid
            WHERE LOWER(TRIM(c.country)) = '{target}'
        )
        SELECT
            tp.year,
            COUNT(DISTINCT tp.eid)                                              AS h1_total,
            COUNT(DISTINCT CASE WHEN pn.np <= {threshold} THEN tp.eid END)      AS h1_reg
        FROM target_papers tp
        JOIN paper_nps pn ON tp.eid = pn.eid
        GROUP BY tp.year
        ORDER BY tp.year
    """


def _h2_joint_sql(target: str, compare: str) -> str:
    """Annual joint paper count for target–compare dyad."""
    return f"""
        SELECT a.year, COUNT(DISTINCT a.eid) AS h2_joint
        FROM {config.TABLES["articles"]} a
        JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
        JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
        WHERE LOWER(TRIM(c1.country)) = '{target}'
          AND LOWER(TRIM(c2.country)) = '{compare}'
        GROUP BY a.year
        ORDER BY a.year
    """


def _h2_brokers_sql(target: str, compare: str) -> str:
    """Top-3 third-party countries (by paper count) per year for the dyad."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid, a.year
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        ),
        broker_counts AS (
            SELECT
                jp.year,
                LOWER(TRIM(c.country)) AS name,
                COUNT(DISTINCT jp.eid)  AS papers
            FROM joint_papers jp
            JOIN {config.TABLES["countries"]} c ON jp.eid = c.eid
            WHERE LOWER(TRIM(c.country)) NOT IN ('{target}', '{compare}')
            GROUP BY jp.year, LOWER(TRIM(c.country))
        ),
        ranked AS (
            SELECT year, name, papers,
                ROW_NUMBER() OVER (PARTITION BY year ORDER BY papers DESC) AS rn
            FROM broker_counts
        )
        SELECT year, name, papers
        FROM ranked
        WHERE rn <= 3
        ORDER BY year, rn
    """


def _h3_all_years_sql(threshold: int, w_small: float, w_cons: float) -> str:
    """
    Salton-normalised weighted edge list for all MENA dyads across all years.
    All multi-country papers are included; deliberate (np ≤ threshold) papers
    receive weight w_small per fractional unit, mega-consortia receive w_cons.
    """
    return f"""
        WITH paper_stats AS (
            SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) AS np
            FROM {config.TABLES["countries"]}
            GROUP BY eid
            HAVING np > 1
        ),
        dyad_weights AS (
            SELECT
                a.year,
                LOWER(TRIM(c1.country)) AS c_i,
                LOWER(TRIM(c2.country)) AS c_j,
                SUM(
                    2.0 / (ps.np * (ps.np - 1)) *
                    CASE WHEN ps.np <= {threshold}
                        THEN {w_small:.6f}
                        ELSE {w_cons:.6f}
                    END
                ) AS c_star
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            JOIN paper_stats ps ON a.eid = ps.eid
            WHERE c_i < c_j
            GROUP BY 1, 2, 3
        )
        SELECT
            dw.year,
            dw.c_i,
            dw.c_j,
            (dw.c_star / SQRT(b1.total_output * b2.total_output)) AS s_ij
        FROM dyad_weights dw
        JOIN {config.TABLES["baseline"]} b1
            ON dw.c_i = LOWER(TRIM(b1.country)) AND b1.year = dw.year
        JOIN {config.TABLES["baseline"]} b2
            ON dw.c_j = LOWER(TRIM(b2.country)) AND b2.year = dw.year
        WHERE b1.total_output > 0 AND b2.total_output > 0
    """


def _h4_yearly_sql(target: str, compare: str) -> str:
    """Annual neutral vs. other paper counts for target–compare dyad."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid, a.year
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        ),
        paper_themes AS (
            SELECT
                jp.eid,
                jp.year,
                MAX(CASE
                    WHEN LOWER(s.subject) SIMILAR TO '.*({_NEUTRAL_PATTERN}).*'
                    THEN 1 ELSE 0
                END) AS is_neutral
            FROM joint_papers jp
            LEFT JOIN {config.TABLES["subjects"]} s ON jp.eid = s.eid
            GROUP BY jp.eid, jp.year
        )
        SELECT
            year,
            CAST(SUM(is_neutral)       AS INTEGER) AS h4_neutral,
            CAST(SUM(1 - is_neutral)   AS INTEGER) AS h4_other
        FROM paper_themes
        GROUP BY year
        ORDER BY year
    """


def _global_brokers_sql(target: str, compare: str) -> str:
    """All-time broker country totals with percentage share."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        ),
        broker_totals AS (
            SELECT LOWER(TRIM(c.country)) AS name, COUNT(DISTINCT jp.eid) AS papers
            FROM joint_papers jp
            JOIN {config.TABLES["countries"]} c ON jp.eid = c.eid
            WHERE LOWER(TRIM(c.country)) NOT IN ('{target}', '{compare}')
            GROUP BY LOWER(TRIM(c.country))
        )
        SELECT
            name,
            papers,
            ROUND(100.0 * papers / SUM(papers) OVER (), 1) AS percent
        FROM broker_totals
        ORDER BY papers DESC
        LIMIT 15
    """


def _summary_sql(target: str, compare: str) -> str:
    """Pre/post Abraham Accords paper counts for the dyad."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid, a.year
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        )
        SELECT
            CAST(SUM(CASE WHEN year < {_ACCORDS_YEAR} THEN 1 ELSE 0 END) AS INTEGER) AS pre,
            CAST(SUM(CASE WHEN year >= {_ACCORDS_YEAR} THEN 1 ELSE 0 END) AS INTEGER) AS post
        FROM joint_papers
    """


def _h4_subjects_sql(target: str, compare: str) -> str:
    """Top-5 subject areas for target–compare joint papers."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        )
        SELECT s.subject, COUNT(DISTINCT jp.eid) AS papers
        FROM joint_papers jp
        JOIN {config.TABLES["subjects"]} s ON jp.eid = s.eid
        GROUP BY s.subject
        ORDER BY papers DESC
        LIMIT 5
    """


def _h4_neutral_ratio_sql(target: str, compare: str) -> str:
    """Percentage of joint papers classified as neutral STEM fields."""
    return f"""
        WITH joint_papers AS (
            SELECT a.eid
            FROM {config.TABLES["articles"]} a
            JOIN {config.TABLES["countries"]} c1 ON a.eid = c1.eid
            JOIN {config.TABLES["countries"]} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) = '{target}'
              AND LOWER(TRIM(c2.country)) = '{compare}'
        ),
        paper_themes AS (
            SELECT
                jp.eid,
                MAX(CASE
                    WHEN LOWER(s.subject) SIMILAR TO '.*({_NEUTRAL_PATTERN}).*'
                    THEN 1 ELSE 0
                END) AS is_neutral
            FROM joint_papers jp
            LEFT JOIN {config.TABLES["subjects"]} s ON jp.eid = s.eid
            GROUP BY jp.eid
        )
        SELECT ROUND(100.0 * SUM(is_neutral) / NULLIF(COUNT(*), 0), 1) AS neutral_ratio
        FROM paper_themes
    """


# ---------------------------------------------------------------------------
# H3 centrality computation
# ---------------------------------------------------------------------------


def _compute_h3(
    all_edges: pd.DataFrame,
    years: range,
    target: str,
) -> Dict[int, Dict[str, Any]]:
    """
    Compute per-year eigenvector (target) and betweenness (top broker)
    centrality from a pre-fetched full-range edge list.
    """
    result: Dict[int, Dict[str, Any]] = {}

    for year in years:
        edges = all_edges[all_edges["year"] == year]
        if edges.empty:
            continue

        G = nx.Graph()
        for _, row in edges.iterrows():
            G.add_edge(row["c_i"], row["c_j"], weight=float(row["s_ij"]))

        if not G.nodes():
            continue

        try:
            ec = nx.eigenvector_centrality(G, weight="weight", max_iter=1000)
        except (
            nx.PowerIterationFailedConvergence,
            nx.exception.NetworkXPointlessConcept,
        ):
            try:
                ec = nx.eigenvector_centrality_numpy(G, weight="weight")
            except Exception:
                ec = {}

        try:
            bc = nx.betweenness_centrality(G, weight="weight", normalized=True)
        except Exception:
            bc = {}

        top_broker = max(bc, key=bc.get) if bc else ""
        top_bc = bc.get(top_broker, 0.0) if top_broker else 0.0

        result[year] = {
            "h3_broker_name": top_broker,
            "h3_broker_score": round(top_bc, 4),
            "h3_target": round(ec.get(target, 0.0), 4),
        }

    return result


# ---------------------------------------------------------------------------
# Dataset assembler
# ---------------------------------------------------------------------------


def _build_dataset(
    conn: duckdb.DuckDBPyConnection,
    target: str,
    compare: str,
    threshold: int,
    w_small: float,
    w_cons: float,
) -> List[Dict[str, Any]]:
    years = range(config.START_YEAR, config.END_YEAR + 1)

    data: Dict[int, Dict[str, Any]] = {
        y: {
            "year": y,
            "h1_total": 0,
            "h1_reg": 0,
            "h2_joint": 0,
            "h2_yearly_brokers": [],
            "h3_broker_name": "",
            "h3_broker_score": 0.0,
            "h3_target": 0.0,
            "h4_neutral": 0,
            "h4_other": 0,
        }
        for y in years
    }

    # H1
    for _, row in conn.execute(_h1_sql(target, threshold)).df().iterrows():
        y = int(row["year"])
        if y in data:
            data[y]["h1_total"] = int(row["h1_total"])
            data[y]["h1_reg"] = int(row["h1_reg"])

    # H2 joint
    for _, row in conn.execute(_h2_joint_sql(target, compare)).df().iterrows():
        y = int(row["year"])
        if y in data:
            data[y]["h2_joint"] = int(row["h2_joint"])

    # H2 yearly brokers
    brokers_df = conn.execute(_h2_brokers_sql(target, compare)).df()
    for _, row in brokers_df.iterrows():
        y = int(row["year"])
        if y in data:
            data[y]["h2_yearly_brokers"].append(
                {"name": row["name"], "papers": int(row["papers"])}
            )

    # H3 — single bulk query, iterate in Python
    all_edges = conn.execute(_h3_all_years_sql(threshold, w_small, w_cons)).df()
    h3 = _compute_h3(all_edges, years, target)
    for y, vals in h3.items():
        if y in data:
            data[y].update(vals)

    # H4 yearly
    for _, row in conn.execute(_h4_yearly_sql(target, compare)).df().iterrows():
        y = int(row["year"])
        if y in data:
            data[y]["h4_neutral"] = int(row["h4_neutral"])
            data[y]["h4_other"] = int(row["h4_other"])

    return list(data.values())


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def get_config(_: None = Security(_verify_key)) -> Dict[str, Any]:
    return {
        "np_threshold": config.DELIBERATE_N,
        "w_small": config.WEIGHTS["SCALE"]["small"],
        "w_cons": config.WEIGHTS["SCALE"]["cons"],
        "w_intl": config.WEIGHTS["SCOPE"]["intl"],
        "start_year": config.START_YEAR,
        "end_year": config.END_YEAR,
        "geopolitical_markers": {
            k.lower(): v for k, v in config.GEOPOLITICAL_MARKERS.items()
        },
    }


@app.get("/api/metrics")
def get_metrics(
    _: None = Security(_verify_key),
    target: str = Query(..., description="Target country (lowercase, e.g. 'israel')"),
    compare: str = Query(..., description="Comparison country (lowercase)"),
    np_threshold: Optional[int] = Query(
        default=None, ge=2, le=8, description="Deliberate-network threshold (nₚ ≤ N)"
    ),
    w_small: Optional[float] = Query(
        default=None,
        ge=0.05,
        le=1.0,
        description="Weight for deliberate (small) papers",
    ),
    w_cons: Optional[float] = Query(
        default=None, ge=0.0, le=1.0, description="Weight for mega-consortium papers"
    ),
) -> Dict[str, Any]:
    target = target.lower().strip()
    compare = compare.lower().strip()

    if target not in _VALID_COUNTRIES or compare not in _VALID_COUNTRIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid country. Valid options: {sorted(_VALID_COUNTRIES)}",
        )
    if target == compare:
        raise HTTPException(status_code=400, detail="target and compare must differ")

    # Resolve overrides — never mutate config module
    threshold = np_threshold if np_threshold is not None else config.DELIBERATE_N
    weight_small = w_small if w_small is not None else config.WEIGHTS["SCALE"]["small"]
    weight_cons = w_cons if w_cons is not None else config.WEIGHTS["SCALE"]["cons"]

    logger.info(
        "Metrics request: target=%s, compare=%s, threshold=%d, w_small=%.3f, w_cons=%.3f",
        target,
        compare,
        threshold,
        weight_small,
        weight_cons,
    )

    try:
        with _db() as conn:
            dataset = _build_dataset(
                conn, target, compare, threshold, weight_small, weight_cons
            )

            brokers_df = conn.execute(_global_brokers_sql(target, compare)).df()
            global_brokers = [
                {
                    "name": row["name"],
                    "papers": int(row["papers"]),
                    "percent": float(row["percent"]),
                }
                for _, row in brokers_df.iterrows()
            ]

            summary_row = conn.execute(_summary_sql(target, compare)).fetchone()
            pre = int(summary_row[0] or 0)
            post = int(summary_row[1] or 0)
            growth = round((post - pre) / pre * 100, 1) if pre > 0 else 0.0
            summary = {"pre": pre, "post": post, "growth": growth}

            subjects_df = conn.execute(_h4_subjects_sql(target, compare)).df()
            h4_subjects = [
                {
                    "subject": row["subject"].title()
                    if row["subject"]
                    else row["subject"],
                    "papers": int(row["papers"]),
                }
                for _, row in subjects_df.iterrows()
                if row["subject"] and row["subject"].lower() != "unknown"
            ]

            ratio_row = conn.execute(_h4_neutral_ratio_sql(target, compare)).fetchone()
            neutral_ratio_raw = ratio_row[0] if ratio_row else 0
            h4_neutral_ratio = (
                0
                if neutral_ratio_raw is None or math.isnan(float(neutral_ratio_raw))
                else round(float(neutral_ratio_raw), 1)
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error computing metrics for %s / %s", target, compare)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "dataset": dataset,
        "globalBrokers": global_brokers,
        "summary": summary,
        "h4_subjects": h4_subjects,
        "h4_neutral_ratio": h4_neutral_ratio,
        "params": {
            "np_threshold": threshold,
            "w_small": weight_small,
            "w_cons": weight_cons,
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
