import duckdb
import networkx as nx
import pandas as pd
from community import community_louvain
import config

class ScientometricAnalyzer:
    def __init__(self):
        # Initialize DuckDB connection
        self.conn = duckdb.connect(config.DB_PATH, read_only=True)
        self.mena_countries = tuple(config.COUNTRIES_LIST)

    def get_basic_metrics(self) -> dict:
        # Fetch high-level dataset metrics
        query = f"SELECT COUNT(*) FROM {config.TABLES['articles']}"
        total_papers = self.conn.execute(query).fetchone()[0]
        return {"total_papers": total_papers}

    def get_country_timeseries(self, country: str, exclude_mega_projects: bool = False) -> pd.DataFrame:
        # Hypothesis 1: Filter out mega-projects if flag is True
        having_clause = "HAVING COUNT(c2.country) <= 5" if exclude_mega_projects else ""
        
        query = f"""
            WITH ValidPapers AS (
                SELECT a.eid
                FROM {config.TABLES['articles']} a
                JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
                GROUP BY a.eid
                {having_clause}
            )
            SELECT a.year, COUNT(DISTINCT a.eid) as papers
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c ON a.eid = c.eid
            JOIN ValidPapers vp ON a.eid = vp.eid
            WHERE LOWER(TRIM(c.country)) = '{country}'
            GROUP BY a.year ORDER BY a.year
        """
        return self.conn.sql(query).df()

    def get_group_collaboration(self, countries: list) -> pd.DataFrame:
        # Hypothesis 2: Extract timeline of collaboration between N specific countries
        formatted_countries = ", ".join([f"'{c.strip().lower()}'" for c in countries])
        num_countries = len(countries)
        
        query = f"""
            SELECT a.year, COUNT(DISTINCT a.eid) as joint_papers
            FROM {config.TABLES['articles']} a
            JOIN (
                SELECT eid 
                FROM {config.TABLES['countries']}
                WHERE LOWER(TRIM(country)) IN ({formatted_countries})
                GROUP BY eid
                HAVING COUNT(DISTINCT LOWER(TRIM(country))) = {num_countries}
            ) c_match ON a.eid = c_match.eid
            GROUP BY a.year 
            ORDER BY a.year
        """
        return self.conn.sql(query).df()

    def build_annual_network(self, year: int) -> nx.Graph:
        # Build adjacency matrix and graph for a specific year
        query = f"""
            SELECT LOWER(TRIM(c1.country)) as source, 
                   LOWER(TRIM(c2.country)) as target, 
                   COUNT(DISTINCT a.eid) as weight
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            WHERE a.year = {year} 
              AND LOWER(TRIM(c1.country)) < LOWER(TRIM(c2.country))
              AND LOWER(TRIM(c1.country)) IN {self.mena_countries}
              AND LOWER(TRIM(c2.country)) IN {self.mena_countries}
            GROUP BY 1, 2
        """
        edges = self.conn.sql(query).df()
        
        G = nx.Graph()
        for _, row in edges.iterrows():
            G.add_edge(row['source'], row['target'], weight=row['weight'], distance=1.0/row['weight'])
        return G

    def get_network_brokers(self, year: int) -> dict:
        # Hypothesis 3: Calculate Betweenness Centrality to identify brokers
        G = self.build_annual_network(year)
        if G.number_of_edges() == 0:
            return {}
        return nx.betweenness_centrality(G, weight='distance')
    
    def get_global_brokers_for_dyad(self, country_a: str, country_b: str) -> pd.DataFrame:
        # Retrieves top 5 non-MENA countries co-authoring with the specified dyad
        query = f"""
            WITH joint_papers AS (
                SELECT a.eid
                FROM {config.TABLES['articles']} a
                JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
                JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
                WHERE LOWER(TRIM(c1.country)) = '{country_a}'
                  AND LOWER(TRIM(c2.country)) = '{country_b}'
            )
            SELECT LOWER(TRIM(c.country)) as global_broker, COUNT(DISTINCT c.eid) as papers
            FROM {config.TABLES['countries']} c
            JOIN joint_papers jp ON c.eid = jp.eid
            WHERE LOWER(TRIM(c.country)) NOT IN {self.mena_countries}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 5
        """
        return self.conn.sql(query).df()
    
    def get_network_metrics(self, year: int) -> dict:
        # Hypothesis 3: Calculate Betweenness and Eigenvector Centrality
        G = self.build_annual_network(year)
        if G.number_of_edges() == 0:
            return {}
            
        # Betweenness for broker role (shortest paths)
        betweenness = nx.betweenness_centrality(G, weight='distance')
        
        # Eigenvector for network integration (influence)
        try:
            eigenvector = nx.eigenvector_centrality(G, weight='weight', max_iter=1000)
        except nx.PowerIterationFailedConvergence:
            eigenvector = nx.degree_centrality(G) # Fallback if matrix does not converge
            
        metrics = {}
        for node in G.nodes():
            metrics[node] = {
                'betweenness': betweenness.get(node, 0.0),
                'eigenvector': eigenvector.get(node, 0.0)
            }
        return metrics