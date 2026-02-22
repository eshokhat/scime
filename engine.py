import polars as pl
import duckdb
import config

class AnalysisEngine:
    def __init__(self):
        self.conn = duckdb.connect(config.DB_PATH, read_only=True)
        self._mena_list = ", ".join([f"'{c.lower()}'" for c in config.COUNTRIES_LIST])

    def _query(self, sql: str) -> pl.DataFrame:
        return self.conn.sql(sql).pl()

    def get_db_summary(self):
        papers = self.conn.execute(f"SELECT COUNT(*) FROM {config.TABLES['articles']}").fetchone()[0]
        y_min, y_max = self.conn.execute(f"SELECT MIN(year), MAX(year) FROM {config.TABLES['articles']}").fetchone()
        
        regional_links = self.conn.execute(f"""
            SELECT COUNT(DISTINCT a.eid)
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            WHERE LOWER(TRIM(c1.country)) IN ({self._mena_list}) 
              AND LOWER(TRIM(c2.country)) IN ({self._mena_list})
              AND c1.country < c2.country
        """).fetchone()[0]

        print("="*60)
        print(" DATASET OVERVIEW ")
        print("="*60)
        print(f"  Total Articles in DB: {papers:,}")
        print(f"  Timeframe: {y_min} - {y_max}")
        print(f"  Total MENA-MENA Joint Papers: {regional_links:,}")
        print("="*60 + "\n")

    def calc_country_stats(self, target_country: str, year: int):
        target = target_country.strip().lower()
        query = f"""
            CREATE OR REPLACE TEMPORARY VIEW era_stats AS
            WITH joint_counts AS (
                SELECT LOWER(TRIM(c.country)) as partner, COUNT(DISTINCT c.eid) as co_auth
                FROM {config.TABLES['countries']} c
                JOIN {config.TABLES['articles']} a ON c.eid = a.eid
                WHERE a.year = {year}
                  AND c.eid IN (SELECT eid FROM {config.TABLES['countries']} WHERE LOWER(TRIM(country)) = '{target}')
                  AND LOWER(TRIM(c.country)) IN ({self._mena_list}) 
                  AND LOWER(TRIM(c.country)) != '{target}'
                GROUP BY 1
            ),
            baselines AS (
                SELECT LOWER(TRIM(country)) as country, SUM(total_output) as total
                FROM {config.TABLES['baseline']}
                WHERE year = {year}
                GROUP BY 1
            )
            SELECT j.partner, j.co_auth,
                (j.co_auth / SQRT((SELECT total FROM baselines WHERE country = '{target}') * b.total)) AS salton
            FROM joint_counts j
            JOIN baselines b ON j.partner = b.country
            WHERE salton IS NOT NULL
        """
        self.conn.execute(query)

    def get_external_brokers(self, year: int, limit: int = 5):
        query = f"""
            WITH regional_papers AS (
                SELECT DISTINCT c1.eid
                FROM {config.TABLES['countries']} c1
                JOIN {config.TABLES['countries']} c2 ON c1.eid = c2.eid
                JOIN {config.TABLES['articles']} a ON c1.eid = a.eid
                WHERE a.year = {year}
                  AND LOWER(TRIM(c1.country)) IN ({self._mena_list}) 
                  AND LOWER(TRIM(c2.country)) IN ({self._mena_list}) 
                  AND LOWER(TRIM(c1.country)) < LOWER(TRIM(c2.country))
            )
            SELECT LOWER(TRIM(country)) as broker, COUNT(*) as appearances
            FROM {config.TABLES['countries']}
            WHERE eid IN (SELECT eid FROM regional_papers)
              AND LOWER(TRIM(country)) NOT IN ({self._mena_list})
              AND LOWER(TRIM(country)) NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT {limit}
        """
        return self._query(query)

    def get_full_network(self, year: int):
        query = f"""
            SELECT LOWER(TRIM(c1.country)) as source, LOWER(TRIM(c2.country)) as target, COUNT(DISTINCT c1.eid) as weight
            FROM {config.TABLES['countries']} c1
            JOIN {config.TABLES['countries']} c2 ON c1.eid = c2.eid
            JOIN {config.TABLES['articles']} a ON c1.eid = a.eid
            WHERE a.year = {year}
              AND LOWER(TRIM(c1.country)) IN ({self._mena_list}) 
              AND LOWER(TRIM(c2.country)) IN ({self._mena_list})
              AND LOWER(TRIM(c1.country)) < LOWER(TRIM(c2.country))
            GROUP BY 1, 2
            HAVING COUNT(DISTINCT c1.eid) >= 10
        """
        return self._query(query)

    def get_themes(self, year: int):
        query = f"""
            SELECT LOWER(TRIM(subject)) as subject, COUNT(*) as count 
            FROM {config.TABLES['subjects']} s
            JOIN {config.TABLES['articles']} a ON s.eid = a.eid
            WHERE a.year = {year}
              AND subject NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """
        return self._query(query)
    
    def get_global_integration_stats(self, year: int):
        """Collects general integration statistics for all countries in a given year."""
        query = f"""
            WITH regional_pairs AS (
                SELECT LOWER(TRIM(c1.country)) as c1, LOWER(TRIM(c2.country)) as c2, COUNT(DISTINCT a.eid) as papers
                FROM {config.TABLES['countries']} c1
                JOIN {config.TABLES['countries']} c2 ON c1.eid = c2.eid
                JOIN {config.TABLES['articles']} a ON c1.eid = a.eid
                WHERE a.year = {year}
                  AND LOWER(TRIM(c1.country)) IN ({self._mena_list})
                  AND LOWER(TRIM(c2.country)) IN ({self._mena_list})
                  AND LOWER(TRIM(c1.country)) != LOWER(TRIM(c2.country))
                GROUP BY 1, 2
            )
            SELECT c1 as country, 
                   COUNT(DISTINCT c2) as unique_partners,
                   SUM(papers) as total_regional_papers
            FROM regional_pairs
            GROUP BY 1
        """
        return self._query(query)