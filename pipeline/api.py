"""
api.py
------
Scopus API data ingestion layer.

Classes
-------
ScopusAPI         - Low-level HTTP wrapper around the Scopus Search API.
DataManager       - Checkpoint / log management for resumable scraping runs.
ScopusScraper     - High-level orchestrator for pairwise country scraping.
BaselineCollector - Fetches total annual output per country for normalisation.
"""

import logging
import os
import sys
import time
from itertools import combinations
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)


class ScopusAPI:
    """Low-level wrapper around the Scopus Search API."""

    BASE_URL = "https://api.elsevier.com/content/search/scopus"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}

    def fetch(self, query: str, start: int = 0, count: int = 25, retries: int = 3):
        """
        Fetch a page of results.
        Returns dict on success, 'STOP' on quota exhaustion, None on error.
        """
        params = {"query": query, "count": count, "start": start, "view": "STANDARD"}

        for attempt in range(retries):
            try:
                response = requests.get(
                    self.BASE_URL, headers=self.headers, params=params, timeout=20
                )
                remaining = response.headers.get("X-RateLimit-Remaining")
                if (
                    remaining is not None and int(remaining) <= 0
                ) or response.status_code == 429:
                    logger.warning("API quota exhausted. Stopping.")
                    return "STOP"
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 400:
                    logger.error("HTTP 400 Bad Request for query: %s", query)
                    return None
                time.sleep(0.5)
            except Exception as exc:
                logger.warning("Attempt %d - connection error: %s", attempt + 1, exc)
                time.sleep(2)
        return None


class DataManager:
    """Manages saving, loading, and logging for resumable scraping runs."""

    def __init__(
        self,
        checkpoint_file: Path = config.CHECKPOINT_FILE,
        log_file: Path = config.PROCESSED_LOG_FILE,
    ):
        self.checkpoint_file = Path(checkpoint_file)
        self.log_file = Path(log_file)
        self.all_papers: dict = {}
        self.processed_tasks: set = set()
        self._load_existing_data()

    def _load_existing_data(self):
        if self.checkpoint_file.exists():
            try:
                df = pd.read_csv(self.checkpoint_file)
                if not df.empty and "eid" in df.columns:
                    self.all_papers = df.set_index("eid").to_dict("index")
                    logger.info(
                        "Loaded %d papers from checkpoint.", len(self.all_papers)
                    )
            except Exception as exc:
                logger.error("Error loading checkpoint: %s", exc)

        if self.log_file.exists():
            with open(self.log_file, "r") as fh:
                self.processed_tasks = {line.strip() for line in fh}
            logger.info(
                "Skipped %d already-completed tasks.", len(self.processed_tasks)
            )

    def add_paper(self, eid: str, paper_data: dict, found_countries: set):
        if eid in self.all_papers:
            existing = set(
                str(self.all_papers[eid].get("all_countries", "")).split("; ")
            )
            found_countries.update(existing)
        paper_data["all_countries"] = "; ".join(sorted(filter(None, found_countries)))
        self.all_papers[eid] = paper_data

    def log_task(self, task_id: str):
        self.processed_tasks.add(task_id)
        with open(self.log_file, "a") as fh:
            fh.write(task_id + "\n")

    def save_checkpoint(self):
        if self.all_papers:
            df = pd.DataFrame.from_dict(self.all_papers, orient="index")
            df.index.name = "eid"
            df.reset_index().to_csv(self.checkpoint_file, index=False)

    def save_final(self, is_complete: bool = True):
        if not self.all_papers:
            return None
        out_path = config.FINAL_DB_FILE if is_complete else config.CHECKPOINT_FILE
        df = pd.DataFrame.from_dict(self.all_papers, orient="index")
        df.index.name = "eid"
        df.reset_index().to_csv(out_path, index=False)
        logger.info("Final dataset saved -> %s", out_path)
        return out_path


class ScopusScraper:
    """Orchestrates pairwise country-year scraping across the MENA region."""

    def __init__(self, api_key: str, countries: list, years: list):
        self.api = ScopusAPI(api_key)
        self.db = DataManager()
        self.countries = countries
        self.years = years
        self.stop_execution = False

    def run(self):
        logger.info("Starting data collection.")
        country_pairs = list(combinations(self.countries, 2))
        try:
            for country_a, country_b in country_pairs:
                if self.stop_execution:
                    break
                for year in self.years:
                    task_id = f"{country_a}|{country_b}|{year}"
                    if task_id in self.db.processed_tasks:
                        continue
                    self._process_year_pair(country_a, country_b, year, task_id)
                    if self.stop_execution:
                        break
                self.db.save_checkpoint()
                logger.info(
                    "Checkpoint saved after %s-%s. Total papers: %d",
                    country_a,
                    country_b,
                    len(self.db.all_papers),
                )
        except KeyboardInterrupt:
            logger.warning("Interrupted by user.")
        finally:
            final_file = self.db.save_final(is_complete=not self.stop_execution)
            status = "Complete" if not self.stop_execution else "Stopped"
            logger.info(
                "%s. Total papers: %d. Output: %s",
                status,
                len(self.db.all_papers),
                final_file,
            )

    def _process_year_pair(self, c1: str, c2: str, year: int, task_id: str):
        query = f"AFFILCOUNTRY({c1}) AND AFFILCOUNTRY({c2}) AND PUBYEAR IS {year}"
        logger.debug("Processing: %s - %s (%d)", c1, c2, year)
        start_index = 0
        while True:
            data = self.api.fetch(query, start=start_index)
            if data == "STOP":
                self.stop_execution = True
                break
            if not data:
                break
            results = data.get("search-results", {})
            entries = results.get("entry", [])
            if not entries:
                break
            for entry in entries:
                eid = entry.get("eid")
                if not eid:
                    continue
                found_countries = {c1, c2}
                aff_list = entry.get("affiliation", [])
                if isinstance(aff_list, list):
                    for aff in aff_list:
                        country_name = aff.get("affiliation-country")
                        if country_name:
                            found_countries.add(country_name)
                paper_info = {
                    "title": entry.get("dc:title"),
                    "doi": entry.get("prism:doi"),
                    "year": year,
                    "journal": entry.get("prism:publicationName"),
                }
                self.db.add_paper(eid, paper_info, found_countries)
            start_index += len(entries)
            total_res = int(results.get("opensearch:totalResults", 0))
            if start_index >= total_res:
                break
            time.sleep(0.2)
        if not self.stop_execution:
            self.db.log_task(task_id)


class BaselineCollector:
    """Fetches total annual publication count per country for Salton normalisation."""

    BASE_URL = "https://api.elsevier.com/content/search/scopus"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}

    def get_total_count(self, country: str, year: int):
        """Return total document count for a country/year, or 'STOP' on quota."""
        query = f'AFFILCOUNTRY("{country}") AND PUBYEAR IS {year}'
        params = {"query": query, "count": 0}
        try:
            response = requests.get(
                self.BASE_URL, headers=self.headers, params=params, timeout=20
            )
            if response.status_code == 200:
                total = (
                    response.json()
                    .get("search-results", {})
                    .get("opensearch:totalResults", 0)
                )
                return int(total)
            if response.status_code == 429:
                logger.warning("API quota exhausted during baseline collection.")
                return "STOP"
            logger.error("HTTP %d for %s %d", response.status_code, country, year)
            return 0
        except Exception as exc:
            logger.error("Connection error: %s", exc)
            return 0


def update_baseline_csv(api_key: str, filepath: Path = config.BASELINE_FILE):
    """Fetch and append missing country-year totals to the baseline CSV."""
    collector = BaselineCollector(api_key)
    df = (
        pd.read_csv(filepath)
        if filepath.exists()
        else pd.DataFrame(columns=["country", "year", "total_output"])
    )
    new_rows = []
    for country in config.COUNTRIES_LIST:
        logger.info("Processing baseline for: %s", country)
        for year in range(config.START_YEAR, config.END_YEAR + 1):
            exists = not df[
                (df["country"] == country.lower()) & (df["year"] == year)
            ].empty
            if exists:
                continue
            count = collector.get_total_count(country, year)
            if count == "STOP":
                break
            new_rows.append(
                {"country": country.lower(), "year": year, "total_output": count}
            )
            logger.debug("  %d: %d documents", year, count)
            time.sleep(0.3)
    if new_rows:
        df_final = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(filepath, index=False)
        logger.info("Baseline file updated -> %s", filepath)
    else:
        logger.info("No new baseline data to add.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    api_key = os.environ.get("SCOPUS_API_KEY")
    if not api_key:
        raise EnvironmentError("SCOPUS_API_KEY not set. Check your .env file.")
    update_baseline_csv(api_key)
