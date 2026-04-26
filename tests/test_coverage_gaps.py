"""
test_coverage_gaps.py
---------------------
Tests targeting uncovered lines identified by coverage analysis.

Gaps addressed
--------------
pipeline/database.py  : 96-125  load_to_db (tables created, populated, skip-if-present)
                        129-131  build end-to-end
engine/processor.py   : 57-59   NetworkAnalyst.__init__ error path
                        70-71   NetworkAnalyst.close() exception swallowed
                        463-465 compute_network_centrality query failure
                        505     _eigenvector_centrality numpy fallback
                        511-512 _eigenvector_centrality NetworkXPointlessConcept
                        600-602 ThematicAnalyst.__init__ error path
                        605-614 ThematicAnalyst lifecycle (__enter__/__exit__/close)
                        671-673 get_contingency_table query failure
                        689     get_contingency_table total==0 row skipped
                        696-697 get_contingency_table fixed_0.5 fallback
engine/visuals.py     : 482-487 create_interactive_network HTML output
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import networkx as nx
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from engine.processor import NetworkAnalyst, ThematicAnalyst


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_analyst(monkeypatch) -> NetworkAnalyst:
    """Return a NetworkAnalyst backed by a fresh in-memory connection."""
    fresh = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
    return NetworkAnalyst()


def _fresh_thematic(monkeypatch) -> ThematicAnalyst:
    """Return a ThematicAnalyst backed by a fresh in-memory connection."""
    fresh = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
    return ThematicAnalyst()


# ---------------------------------------------------------------------------
# Fixture: DatabaseBuilder wired to tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def db_builder(tmp_path, monkeypatch):
    """
    DatabaseBuilder with all file paths and the DB path redirected to tmp_path.
    Synthetic CSVs are written so normalise() / load_to_db() / build() can run.
    """
    import config as _config

    monkeypatch.setattr(_config, "MASTER_RAW_FILE", tmp_path / "master.csv")
    monkeypatch.setattr(_config, "BASELINE_FILE", tmp_path / "baseline.csv")
    monkeypatch.setattr(_config, "MASTER_MAIN_FILE", tmp_path / "master_main.csv")
    monkeypatch.setattr(
        _config, "MASTER_COUNTRIES_FILE", tmp_path / "master_countries.csv"
    )
    monkeypatch.setattr(
        _config, "MASTER_SUBJECTS_FILE", tmp_path / "master_subjects.csv"
    )
    monkeypatch.setattr(_config, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(_config, "DB_PATH", str(tmp_path / "test.db"))

    pd.DataFrame(
        [
            {
                "eid": "e1",
                "title": "Paper One",
                "doi": "10.1/a",
                "year": 2015,
                "journal": "Journal A",
                "all_countries": "Israel; Egypt",
                "subject_areas": "Engineering|Medicine",
            },
            {
                "eid": "e2",
                "title": "Paper Two",
                "doi": "10.1/b",
                "year": 2020,
                "journal": "Journal B",
                "all_countries": "Turkey; Iran",
                "subject_areas": "Physics and Astronomy",
            },
        ]
    ).to_csv(tmp_path / "master.csv", index=False)

    pd.DataFrame(
        [
            {"country": "israel", "year": 2015, "total_output": 5000},
            {"country": "egypt", "year": 2015, "total_output": 1000},
        ]
    ).to_csv(tmp_path / "baseline.csv", index=False)

    from pipeline.database import DatabaseBuilder

    return DatabaseBuilder()


# ---------------------------------------------------------------------------
# 1. DatabaseBuilder.load_to_db
# ---------------------------------------------------------------------------


class TestDatabaseBuilderLoad:
    """load_to_db creates all four tables from normalised CSVs."""

    def test_load_creates_all_four_tables(self, db_builder, tmp_path):
        db_builder.normalise()
        db_builder.load_to_db()

        con = duckdb.connect(str(tmp_path / "test.db"))
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        con.close()
        assert {"articles", "countries", "subjects", "baseline"}.issubset(tables)

    def test_load_populates_articles_table(self, db_builder, tmp_path):
        db_builder.normalise()
        db_builder.load_to_db()

        con = duckdb.connect(str(tmp_path / "test.db"))
        count = con.execute("SELECT count(*) FROM articles").fetchone()[0]
        con.close()
        assert count == 2

    def test_load_populates_countries_table(self, db_builder, tmp_path):
        """e1 → 2 countries, e2 → 2 countries: 4 rows total."""
        db_builder.normalise()
        db_builder.load_to_db()

        con = duckdb.connect(str(tmp_path / "test.db"))
        count = con.execute("SELECT count(*) FROM countries").fetchone()[0]
        con.close()
        assert count == 4

    def test_second_load_does_not_duplicate_rows(self, db_builder, tmp_path):
        """load_to_db called twice must leave article count unchanged (skip branch)."""
        db_builder.normalise()
        db_builder.load_to_db()
        db_builder.load_to_db()  # triggers "already populated" log path

        con = duckdb.connect(str(tmp_path / "test.db"))
        count = con.execute("SELECT count(*) FROM articles").fetchone()[0]
        con.close()
        assert count == 2

    def test_load_baseline_table_populated(self, db_builder, tmp_path):
        db_builder.normalise()
        db_builder.load_to_db()

        con = duckdb.connect(str(tmp_path / "test.db"))
        count = con.execute("SELECT count(*) FROM baseline").fetchone()[0]
        con.close()
        assert count == 2


# ---------------------------------------------------------------------------
# 2. DatabaseBuilder.build
# ---------------------------------------------------------------------------


class TestDatabaseBuilderBuild:
    """build() = normalise() + load_to_db(); returns the stats dict."""

    def test_build_returns_stats_dict(self, db_builder):
        stats = db_builder.build()
        assert isinstance(stats, dict)
        assert set(stats.keys()) == {"articles", "countries", "subjects", "baseline"}

    def test_build_creates_db_file(self, db_builder, tmp_path):
        db_builder.build()
        assert (tmp_path / "test.db").exists()

    def test_build_stats_article_count(self, db_builder):
        stats = db_builder.build()
        assert stats["articles"] == 2

    def test_build_stats_countries_count(self, db_builder):
        stats = db_builder.build()
        assert stats["countries"] == 4


# ---------------------------------------------------------------------------
# 3. NetworkAnalyst.__init__ error path
# ---------------------------------------------------------------------------


class TestNetworkAnalystInitError:
    """__init__ must log and re-raise when duckdb.connect raises."""

    def test_init_reraises_connection_error(self, monkeypatch):
        monkeypatch.setattr(
            duckdb, "connect", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db"))
        )
        with pytest.raises(RuntimeError, match="no db"):
            NetworkAnalyst()


# ---------------------------------------------------------------------------
# 4. NetworkAnalyst.close() exception swallowed
# ---------------------------------------------------------------------------


class TestNetworkAnalystCloseException:
    """close() must silently swallow exceptions raised by conn.close()."""

    def test_close_swallows_runtime_error(self, monkeypatch):
        analyst = _fresh_analyst(monkeypatch)
        analyst.conn = MagicMock()
        analyst.conn.close.side_effect = RuntimeError("already closed")
        analyst.close()  # must not raise


# ---------------------------------------------------------------------------
# 5. compute_network_centrality — query failure and NetworkXPointlessConcept
# ---------------------------------------------------------------------------


class TestNetworkCentralityEdgeCases:
    """Branches in compute_network_centrality not covered by existing tests."""

    def test_query_failure_returns_empty_dict(self, monkeypatch):
        """When conn.sql raises, the method must return {} without propagating."""
        analyst = _fresh_analyst(monkeypatch)
        analyst.conn = MagicMock()
        analyst.conn.sql.side_effect = RuntimeError("simulated query error")
        assert analyst.compute_network_centrality(2015) == {}

    def test_networkx_pointless_concept_returns_empty_dict(self, monkeypatch):
        """NetworkXPointlessConcept (graph with no edges) must be caught."""
        analyst = _fresh_analyst(monkeypatch)
        # Replace conn with a MagicMock (DuckDB conn.sql is read-only)
        mock_conn = MagicMock()
        mock_conn.sql.return_value.df.return_value = pd.DataFrame(
            {"c_i": ["israel"], "c_j": ["egypt"], "s_ij": [0.5]}
        )
        analyst.conn = mock_conn
        with patch(
            "networkx.eigenvector_centrality",
            side_effect=nx.exception.NetworkXPointlessConcept("no edges"),
        ):
            assert analyst.compute_network_centrality(2015) == {}


# ---------------------------------------------------------------------------
# 6. _eigenvector_centrality — numpy fallback and NetworkXPointlessConcept
# ---------------------------------------------------------------------------


class TestEigenvectorCentralityPrivate:
    """Direct tests of the private _eigenvector_centrality helper."""

    def test_empty_graph_returns_empty_dict(self, monkeypatch):
        analyst = _fresh_analyst(monkeypatch)
        assert analyst._eigenvector_centrality(nx.Graph()) == {}

    def test_numpy_fallback_on_convergence_failure(self, monkeypatch):
        """PowerIterationFailedConvergence triggers the numpy eigensolver path."""
        analyst = _fresh_analyst(monkeypatch)
        G = nx.cycle_graph(5)  # small dense graph the numpy solver handles fine
        with patch(
            "networkx.eigenvector_centrality",
            side_effect=nx.PowerIterationFailedConvergence(1000),
        ):
            result = analyst._eigenvector_centrality(G)
        assert isinstance(result, dict)
        assert len(result) == 5
        assert all(isinstance(v, float) for v in result.values())

    def test_pointless_concept_returns_empty_dict(self, monkeypatch):
        """NetworkXPointlessConcept (isolated node) is caught and {} returned."""
        analyst = _fresh_analyst(monkeypatch)
        G = nx.Graph()
        G.add_node("isolated")
        with patch(
            "networkx.eigenvector_centrality",
            side_effect=nx.exception.NetworkXPointlessConcept("no edges"),
        ):
            assert analyst._eigenvector_centrality(G) == {}


# ---------------------------------------------------------------------------
# 7. calculate_dyad_affinity — error handler (lines 273-277)
# ---------------------------------------------------------------------------


class TestCalculateDyadAffinityEdgeCases:
    """Error-propagation branch in calculate_dyad_affinity."""

    def test_query_failure_reraises(self, monkeypatch):
        """When conn.sql raises, the method must log and re-raise the exception."""
        analyst = _fresh_analyst(monkeypatch)
        analyst.conn = MagicMock()
        analyst.conn.sql.side_effect = RuntimeError("simulated query error")
        with pytest.raises(RuntimeError, match="simulated query error"):
            analyst.calculate_dyad_affinity("israel", "egypt")

    def test_unknown_country_pair_returns_empty_dataframe(self, monkeypatch, test_db):
        """A pair with no baseline entries returns an empty DataFrame (not an error)."""
        import duckdb as _ddb
        monkeypatch.setattr(_ddb, "connect", lambda *a, **kw: test_db)
        analyst = NetworkAnalyst()
        df = analyst.calculate_dyad_affinity("atlantis", "utopia")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


# ---------------------------------------------------------------------------
# 8. ThematicAnalyst.__init__ error path
# ---------------------------------------------------------------------------


class TestThematicAnalystInitError:
    """ThematicAnalyst.__init__ must log and re-raise when duckdb.connect raises."""

    def test_init_reraises_connection_error(self, monkeypatch):
        monkeypatch.setattr(
            duckdb, "connect", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db"))
        )
        with pytest.raises(RuntimeError, match="no db"):
            ThematicAnalyst()


# ---------------------------------------------------------------------------
# 8. ThematicAnalyst lifecycle (__enter__ / __exit__ / close)
# ---------------------------------------------------------------------------


class TestThematicAnalystLifecycle:
    """ThematicAnalyst must implement the context-manager protocol correctly."""

    def test_context_manager_returns_self(self, monkeypatch):
        with _fresh_thematic(monkeypatch).__class__.__new__(
            ThematicAnalyst
        ) as _:
            pass  # ensure class is importable; real test below
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        with ThematicAnalyst() as ta:
            assert isinstance(ta, ThematicAnalyst)

    def test_context_manager_exit_does_not_raise(self, monkeypatch):
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        with ThematicAnalyst():
            pass

    def test_close_is_idempotent(self, monkeypatch):
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        ta = ThematicAnalyst()
        ta.close()
        ta.close()  # second call must not raise

    def test_close_swallows_connection_error(self, monkeypatch):
        """close() exception handler (lines 605-608) must swallow errors."""
        fresh = duckdb.connect(":memory:")
        monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: fresh)
        ta = ThematicAnalyst()
        ta.conn = MagicMock()
        ta.conn.close.side_effect = RuntimeError("already closed")
        ta.close()  # must not raise


# ---------------------------------------------------------------------------
# 9. ThematicAnalyst.get_contingency_table — query failure
# ---------------------------------------------------------------------------


class TestThematicContingencyQueryFailure:
    """get_contingency_table must propagate DB errors after logging."""

    @pytest.fixture
    def thematic_analyst(self, test_db, monkeypatch):
        import duckdb as _ddb
        monkeypatch.setattr(_ddb, "connect", lambda *a, **kw: test_db)
        return ThematicAnalyst()

    def test_query_failure_reraises(self, thematic_analyst):
        thematic_analyst.conn = MagicMock()
        thematic_analyst.conn.sql.side_effect = RuntimeError("db error")
        with pytest.raises(RuntimeError, match="db error"):
            thematic_analyst.get_contingency_table()


# ---------------------------------------------------------------------------
# 10. ThematicAnalyst.get_contingency_table — branch coverage
# ---------------------------------------------------------------------------


class TestThematicContingencyBranches:
    """
    Cover the two uncovered branches inside the row-iteration loop:
      line 689  — total == 0  → continue
      lines 696-697 — fixed_0.5 fallback (THEMATIC_METHOD != 'proportional')
    """

    @pytest.fixture
    def thematic_analyst(self, test_db, monkeypatch):
        import duckdb as _ddb
        monkeypatch.setattr(_ddb, "connect", lambda *a, **kw: test_db)
        return ThematicAnalyst()

    def _inject_data(self, ta: ThematicAnalyst, df: pd.DataFrame) -> pd.DataFrame:
        """Replace ta.conn with a MagicMock so get_contingency_table processes df."""
        mock_conn = MagicMock()
        mock_conn.sql.return_value.df.return_value = df
        ta.conn = mock_conn
        return ta.get_contingency_table()

    def test_zero_total_row_is_skipped(self, thematic_analyst):
        """A row with n_count=0 and s_count=0 must be silently skipped."""
        fake = pd.DataFrame(
            {"countries": [["israel", "egypt"]], "n_count": [0], "s_count": [0]}
        )
        result = self._inject_data(thematic_analyst, fake)
        assert result.loc["israel_arab", "neutral"] == 0.0
        assert result.loc["israel_arab", "sensitive"] == 0.0

    def test_fixed_05_fallback_splits_mixed_paper(self, thematic_analyst, monkeypatch):
        """With THEMATIC_METHOD != 'proportional', mixed papers get 0.5 / 0.5."""
        monkeypatch.setattr(config, "THEMATIC_METHOD", "fixed_0.5")
        fake = pd.DataFrame(
            {"countries": [["israel", "egypt"]], "n_count": [3], "s_count": [1]}
        )
        result = self._inject_data(thematic_analyst, fake)
        assert result.loc["israel_arab", "neutral"] == pytest.approx(0.5)
        assert result.loc["israel_arab", "sensitive"] == pytest.approx(0.5)

    def test_fixed_05_fallback_applies_to_control_group(self, thematic_analyst, monkeypatch):
        """fixed_0.5 also covers a non-israel-arab dyad."""
        monkeypatch.setattr(config, "THEMATIC_METHOD", "fixed_0.5")
        fake = pd.DataFrame(
            {"countries": [["egypt", "jordan"]], "n_count": [2], "s_count": [2]}
        )
        result = self._inject_data(thematic_analyst, fake)
        assert result.loc["control", "neutral"] == pytest.approx(0.5)
        assert result.loc["control", "sensitive"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 11. ScientificVisualizer.create_interactive_network
# ---------------------------------------------------------------------------


class TestCreateInteractiveNetwork:
    """create_interactive_network must produce a non-empty HTML file."""

    def test_creates_html_file(self, visualizer_in_tmp):
        G = nx.Graph()
        G.add_edge("israel", "egypt", weight=0.5)
        G.add_edge("egypt", "jordan", weight=0.3)
        G.add_edge("israel", "morocco", weight=0.4)
        visualizer_in_tmp.create_interactive_network(G, 2015)

        html_path = visualizer_in_tmp.figures_dir / "interactive_network_2015.html"
        assert html_path.exists(), "HTML file was not created"
        assert html_path.stat().st_size > 0, "HTML file is empty"

    def test_html_contains_network_content(self, visualizer_in_tmp):
        """The generated HTML must reference at least one node name."""
        G = nx.Graph()
        G.add_edge("israel", "egypt", weight=0.5)
        visualizer_in_tmp.create_interactive_network(G, 2020)

        html_path = visualizer_in_tmp.figures_dir / "interactive_network_2020.html"
        content = html_path.read_text(encoding="utf-8")
        assert "israel" in content or "egypt" in content

    def test_empty_graph_creates_html_file(self, visualizer_in_tmp):
        """An empty graph must still produce an HTML file without raising."""
        visualizer_in_tmp.create_interactive_network(nx.Graph(), 1990)
        html_path = visualizer_in_tmp.figures_dir / "interactive_network_1990.html"
        assert html_path.exists()
