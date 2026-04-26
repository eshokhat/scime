"""
conftest.py
-----------
Shared pytest fixtures for the entire test suite.

Synthetic dataset — ground-truth values used in assertions
----------------------------------------------------------
All C* values are derived from: C*(pair) = 2 / (np * (np - 1))

eid1 : Israel–Egypt,                 year=2015, np=2  → C* per pair = 1.000000
eid2 : Israel–Morocco,               year=2020, np=2  → C* per pair = 1.000000
eid3 : Egypt–Jordan,                 year=2015, np=2  → C* per pair = 1.000000
eid4 : Israel–Egypt–Morocco,         year=2021, np=3  → C* per pair = 0.333333
eid5 : 8-country mega-project,       year=2015, np=8  → C* per pair = 0.035714

Baseline output: israel = 5000, all others = 1000 (all years 1990–2025).

Salton denominator for Israel–any_other:
    sqrt(5000 * 1000) = sqrt(5_000_000) ≈ 2236.068

fetch_sensitivity_stats(n=2) expected:
    Israel-Involved C* = 2.000  (eid1 + eid2)
    Non-Israel C*      = 1.000  (eid3)

fetch_sensitivity_stats(n=3) expected:
    Adds eid4 — 3 dyads each with C* = 1/3:
        egypt–israel   → Israel-Involved  +0.333
        egypt–morocco  → Non-Israel       +0.333
        israel–morocco → Israel-Involved  +0.333
    Israel-Involved C* = 2.000 + 0.667 = 2.667
    Non-Israel C*      = 1.000 + 0.333 = 1.333

fetch_sensitivity_stats(n=8) further adds eid5 — 28 dyads each with C* = 1/28:
    Israel pairs (7):   Israel-Involved += 7/28  = 0.250
    Non-Israel pairs (21): Non-Israel   += 21/28 = 0.750
    Israel-Involved C* = 2.667 + 0.250 = 2.917
    Non-Israel C*      = 1.333 + 0.750 = 2.083
"""

import sys
from pathlib import Path

# Non-interactive matplotlib backend — must be set before any pyplot import
import matplotlib

matplotlib.use("Agg")

# Make the project root importable regardless of where pytest is invoked
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# In-memory database construction
# ---------------------------------------------------------------------------


def _build_test_db() -> duckdb.DuckDBPyConnection:
    """Return a populated in-memory DuckDB connection."""
    con = duckdb.connect(":memory:")

    con.execute("""
        CREATE TABLE articles (
            eid VARCHAR, title VARCHAR, doi VARCHAR,
            year INTEGER, journal VARCHAR
        )
    """)
    con.execute("CREATE TABLE countries (eid VARCHAR, country VARCHAR)")
    con.execute("CREATE TABLE subjects  (eid VARCHAR, subject  VARCHAR)")
    con.execute("""
        CREATE TABLE baseline (
            country VARCHAR, year INTEGER, total_output INTEGER
        )
    """)

    con.executemany(
        "INSERT INTO articles VALUES (?,?,?,?,?)",
        [
            ("eid1", "Bilateral Israel-Egypt", "doi1", 2015, "Journal A"),
            ("eid2", "Bilateral Israel-Morocco", "doi2", 2020, "Journal B"),
            ("eid3", "Bilateral Egypt-Jordan", "doi3", 2015, "Journal C"),
            ("eid4", "Trilateral Israel-Egypt-Morocco", "doi4", 2021, "Journal D"),
            ("eid5", "Mega-Project (8 countries)", "doi5", 2015, "Journal E"),
        ],
    )

    con.executemany(
        "INSERT INTO countries VALUES (?,?)",
        [
            ("eid1", "israel"),
            ("eid1", "egypt"),
            ("eid2", "israel"),
            ("eid2", "morocco"),
            ("eid3", "egypt"),
            ("eid3", "jordan"),
            ("eid4", "israel"),
            ("eid4", "egypt"),
            ("eid4", "morocco"),
            ("eid5", "israel"),
            ("eid5", "egypt"),
            ("eid5", "jordan"),
            ("eid5", "morocco"),
            ("eid5", "turkey"),
            ("eid5", "iran"),
            ("eid5", "iraq"),
            ("eid5", "algeria"),
        ],
    )

    con.executemany(
        "INSERT INTO subjects VALUES (?,?)",
        [
            ("eid1", "engineering"),
            ("eid2", "medicine"),
            ("eid3", "social sciences"),
            ("eid4", "physics and astronomy"),
            ("eid5", "physics and astronomy"),
        ],
    )

    all_countries = [
        "israel",
        "algeria",
        "bahrain",
        "egypt",
        "iran",
        "iraq",
        "jordan",
        "kuwait",
        "lebanon",
        "libya",
        "morocco",
        "oman",
        "palestine",
        "qatar",
        "saudi arabia",
        "syria",
        "tunisia",
        "turkey",
        "united arab emirates",
        "yemen",
    ]
    baseline_rows = [
        (c, yr, 5000 if c == "israel" else 1000)
        for c in all_countries
        for yr in range(1990, 2026)
    ]
    con.executemany("INSERT INTO baseline VALUES (?,?,?)", baseline_rows)

    return con


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_db():
    """
    Module-scoped in-memory DuckDB.
    A single connection shared across all tests in one module.
    Test code must NOT modify database state.
    """
    con = _build_test_db()
    yield con
    con.close()


@pytest.fixture
def mock_analyzer(test_db, monkeypatch):
    """
    ScientificAnalyzer wired to the in-memory test DB instead of the
    real database file.  duckdb.connect() is patched at the module level
    that analyzer.py uses, so no file I/O occurs.
    """
    import duckdb as _duckdb

    monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
    from engine.analyzer import ScientificAnalyzer

    return ScientificAnalyzer()


@pytest.fixture
def reporter_in_tmp(tmp_path, monkeypatch):
    """
    Reporter whose output directories are redirected to tmp_path,
    so tests never write into the real outputs/ tree.
    """
    import config as _config

    monkeypatch.setattr(_config, "TABLES_DIR", tmp_path / "tables")
    monkeypatch.setattr(_config, "OUTPUTS_DIR", tmp_path)
    (tmp_path / "tables").mkdir()
    from engine.reporter import Reporter

    return Reporter()


@pytest.fixture
def visualizer_in_tmp(tmp_path, monkeypatch):
    """
    ScientificVisualizer whose figures directory is tmp_path/figures.
    """
    import config as _config

    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    monkeypatch.setattr(_config, "FIGURES_DIR", figures_dir)
    from engine.visuals import ScientificVisualizer

    return ScientificVisualizer()


@pytest.fixture(autouse=True)
def reset_deliberate_n():
    """
    Restore DELIBERATE_NP_THRESHOLD (and alias DELIBERATE_N) after every test
    that might mutate them, preventing state leakage between tests.
    """
    import config as _config

    original = _config.DELIBERATE_NP_THRESHOLD
    yield
    _config.DELIBERATE_NP_THRESHOLD = original
    _config.DELIBERATE_N = original


@pytest.fixture
def mock_network_analyst(test_db, monkeypatch):
    """
    NetworkAnalyst wired to the in-memory test DB — canonical new-architecture
    fixture.  Imports from engine.processor directly (no backward-compat shim).
    """
    import duckdb as _duckdb

    monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
    from engine.processor import NetworkAnalyst

    return NetworkAnalyst()


@pytest.fixture
def research_pipeline_factory(test_db, tmp_path, monkeypatch):
    """
    Factory for ResearchPipeline instances backed by the in-memory test DB.

    Usage::

        def test_something(research_pipeline_factory):
            pipeline = research_pipeline_factory()
            ...

        def test_with_reporter(research_pipeline_factory, reporter_in_tmp):
            pipeline = research_pipeline_factory(reporter=reporter_in_tmp)
            ...
    """
    import duckdb as _duckdb
    from unittest.mock import MagicMock

    import config as _config

    monkeypatch.setattr(_duckdb, "connect", lambda *a, **kw: test_db)
    figures = tmp_path / "figures"
    figures.mkdir(exist_ok=True)
    monkeypatch.setattr(_config, "FIGURES_DIR", figures)

    def _make(reporter=None):
        from engine.orchestrator import ResearchPipeline

        pipeline = ResearchPipeline.__new__(ResearchPipeline)
        from engine.processor import NetworkAnalyst

        pipeline.analyst = NetworkAnalyst()
        pipeline.visualizer = MagicMock()
        pipeline.reporter = reporter
        pipeline.normalized_states = {
            "united arab emirates",
            "bahrain",
            "morocco",
            "egypt",
            "jordan",
        }
        return pipeline

    return _make
