"""
test_config.py
--------------
Validates that config.py exports the correct types, values, and path
structure required by every other module in the project.
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


class TestPaths:
    def test_project_root_is_directory(self):
        assert config.PROJECT_ROOT.is_dir()

    def test_db_path_is_string(self):
        assert isinstance(config.DB_PATH, str)

    def test_db_path_ends_with_db(self):
        assert config.DB_PATH.endswith(".db")

    def test_db_path_inside_project(self):
        assert (
            config.PROJECT_ROOT in Path(config.DB_PATH).parents
            or Path(config.DB_PATH).parent == config.PROJECT_ROOT
        )

    @pytest.mark.parametrize(
        "attr",
        [
            "RAW_DIR",
            "PROCESSED_DIR",
            "OUTPUTS_DIR",
            "FIGURES_DIR",
            "TABLES_DIR",
            "CHECKPOINT_FILE",
            "PROCESSED_LOG_FILE",
            "MASTER_RAW_FILE",
            "BASELINE_FILE",
            "FINAL_DB_FILE",
            "MASTER_MAIN_FILE",
            "MASTER_COUNTRIES_FILE",
            "MASTER_SUBJECTS_FILE",
        ],
    )
    def test_path_constants_are_path_objects(self, attr):
        assert isinstance(getattr(config, attr), Path), (
            f"config.{attr} must be a pathlib.Path, got {type(getattr(config, attr))}"
        )

    def test_output_dirs_exist_after_import(self):
        """config.py must create output dirs on import."""
        for d in [
            config.FIGURES_DIR,
            config.TABLES_DIR,
            config.RAW_DIR,
            config.PROCESSED_DIR,
        ]:
            assert d.exists(), f"{d} was not created by config.py"


class TestSchema:
    def test_tables_dict_has_four_keys(self):
        assert set(config.TABLES.keys()) == {
            "articles",
            "subjects",
            "countries",
            "baseline",
        }

    def test_tables_values_are_strings(self):
        for k, v in config.TABLES.items():
            assert isinstance(v, str), f"TABLES['{k}'] must be a string"


class TestGeography:
    def test_countries_list_is_nonempty(self):
        assert len(config.COUNTRIES_LIST) > 0

    def test_israel_in_countries(self):
        assert "israel" in config.COUNTRIES_LIST

    def test_all_countries_lowercase(self):
        for c in config.COUNTRIES_LIST:
            assert c == c.lower(), f"'{c}' must be lowercase in COUNTRIES_LIST"

    def test_no_duplicate_countries(self):
        assert len(config.COUNTRIES_LIST) == len(set(config.COUNTRIES_LIST))


class TestChronology:
    def test_start_before_end(self):
        assert config.START_YEAR < config.END_YEAR

    def test_years_are_integers(self):
        assert isinstance(config.START_YEAR, int)
        assert isinstance(config.END_YEAR, int)

    def test_start_year_plausible(self):
        assert 1980 <= config.START_YEAR <= 2000

    def test_end_year_plausible(self):
        assert 2020 <= config.END_YEAR <= 2030


class TestResearchSettings:
    def test_deliberate_n_is_int(self):
        assert isinstance(config.DELIBERATE_N, int)

    def test_deliberate_n_at_least_two(self):
        # np=1 means single-country paper; deliberate collaboration requires np>=2
        assert config.DELIBERATE_N >= 2

    def test_min_salton_threshold_positive(self):
        assert config.MIN_SALTON_THRESHOLD > 0

    def test_neutral_fields_nonempty_strings(self):
        assert len(config.NEUTRAL_FIELDS) > 0
        for f in config.NEUTRAL_FIELDS:
            assert isinstance(f, str) and len(f) > 0
