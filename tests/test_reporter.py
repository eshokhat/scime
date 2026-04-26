"""
test_reporter.py
----------------
Tests for Reporter: file creation, content correctness, significance stars,
and metadata JSON structure.
"""

import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.reporter import _stars


class TestSignificanceStars:
    """_stars() must return the correct APA-standard significance markers."""

    @pytest.mark.parametrize(
        "p,expected",
        [
            (0.0001, "***"),
            (0.0009, "***"),
            (0.001, "**"),  # boundary: p < 0.01 but NOT < 0.001
            (0.005, "**"),
            (0.01, "*"),  # boundary: p < 0.05 but NOT < 0.01
            (0.049, "*"),
            (0.05, ""),  # boundary: p >= 0.05 → no stars
            (0.10, ""),
            (1.0, ""),
        ],
    )
    def test_star_thresholds(self, p, expected):
        assert _stars(p) == expected


class TestTableExport:
    """Reporter.table() must create both CSV and LaTeX files."""

    def test_csv_file_created(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        reporter_in_tmp.table(df, label="test_table")
        assert (tmp_path / "tables" / "test_table.csv").exists()

    def test_latex_file_created(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        reporter_in_tmp.table(df, label="test_table")
        assert (tmp_path / "tables" / "test_table.tex").exists()

    def test_csv_content_matches_dataframe(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"x": [10, 20], "y": [30, 40]})
        reporter_in_tmp.table(df, label="csv_check", index=False)
        loaded = pd.read_csv(tmp_path / "tables" / "csv_check.csv")
        assert list(loaded["x"]) == [10, 20]
        assert list(loaded["y"]) == [30, 40]

    def test_latex_contains_caption(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"col": [1]})
        reporter_in_tmp.table(df, label="caption_test", caption="My Caption Text")
        tex = (tmp_path / "tables" / "caption_test.tex").read_text()
        assert "My Caption Text" in tex

    def test_latex_contains_label(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"col": [1]})
        reporter_in_tmp.table(df, label="label_test")
        tex = (tmp_path / "tables" / "label_test.tex").read_text()
        assert "tab:label_test" in tex

    def test_empty_caption_uses_label_as_fallback(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"col": [1]})
        reporter_in_tmp.table(df, label="fallback_label", caption="")
        tex = (tmp_path / "tables" / "fallback_label.tex").read_text()
        assert "fallback_label" in tex

    def test_index_false_not_in_csv(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"v": [7]})
        reporter_in_tmp.table(df, label="noindex", index=False)
        content = (tmp_path / "tables" / "noindex.csv").read_text()
        assert content.startswith("v")  # first column header, not a numeric index

    def test_float_format_four_decimal_places(self, reporter_in_tmp, tmp_path):
        df = pd.DataFrame({"val": [3.141592653]})
        reporter_in_tmp.table(df, label="float_fmt", index=False)
        tex = (tmp_path / "tables" / "float_fmt.tex").read_text()
        assert "3.1416" in tex


class TestMetadata:
    """Reporter.save_run_metadata() must create valid JSON with required keys."""

    REQUIRED_KEYS = {
        "timestamp",
        "python_version",
        "platform",
        "pandas_version",
        "duckdb_version",
    }

    def test_metadata_file_created(self, reporter_in_tmp, tmp_path):
        reporter_in_tmp.save_run_metadata()
        assert (tmp_path / "run_metadata.json").exists()

    def test_metadata_is_valid_json(self, reporter_in_tmp, tmp_path):
        reporter_in_tmp.save_run_metadata()
        content = (tmp_path / "run_metadata.json").read_text()
        data = json.loads(content)  # raises if invalid
        assert isinstance(data, dict)

    def test_required_keys_present(self, reporter_in_tmp, tmp_path):
        reporter_in_tmp.save_run_metadata()
        data = json.loads((tmp_path / "run_metadata.json").read_text())
        for key in self.REQUIRED_KEYS:
            assert key in data, f"Missing key: {key}"

    def test_extra_keys_stored(self, reporter_in_tmp, tmp_path):
        reporter_in_tmp.save_run_metadata({"deliberate_n": 4, "total_papers": 99})
        data = json.loads((tmp_path / "run_metadata.json").read_text())
        assert data["deliberate_n"] == 4
        assert data["total_papers"] == 99

    def test_timestamp_format(self, reporter_in_tmp, tmp_path):
        reporter_in_tmp.save_run_metadata()
        data = json.loads((tmp_path / "run_metadata.json").read_text())
        ts = data["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts  # ISO 8601: YYYY-MM-DDTHH:MM:SS...Z


class TestConsoleStat:
    """Reporter.stat_line() must include the p-value and stars in output."""

    def test_stat_line_with_significant_p(self, reporter_in_tmp, capsys):
        reporter_in_tmp.stat_line("Test Stat", 42.0, p_value=0.0001)
        out = capsys.readouterr().out
        assert "42" in out
        assert "***" in out

    def test_stat_line_without_p_value(self, reporter_in_tmp, capsys):
        reporter_in_tmp.stat_line("No P", "some_value")
        out = capsys.readouterr().out
        assert "some_value" in out
        assert "p =" not in out
