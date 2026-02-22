import networkx as nx
from community import community_louvain
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import polars as pl
from engine import AnalysisEngine
import config

class ScienceML:
    def __init__(self, engine: AnalysisEngine):
        self.engine = engine
        self._scaler = StandardScaler()

    def _build_graph(self, year: int):
        edges = self.engine.get_full_network(year)
        G = nx.Graph()
        if not edges.is_empty():
            for row in edges.iter_rows(named=True):
                G.add_edge(row['source'], row['target'], weight=row['weight'], distance=1.0/row['weight'])
        return G

    def get_centrality_metrics(self, year: int):
        G = self._build_graph(year)
        if G.number_of_edges() == 0:
            return {"degree": {}, "betweenness": {}, "density": 0.0}
        
        return {
            "degree": nx.degree_centrality(G),
            "betweenness": nx.betweenness_centrality(G, weight='distance'),
            "density": nx.density(G)
        }

    def find_best_k_clusters(self, year: int, target_country: str):
        self.engine.calc_country_stats(target_country, year)
        df = self.engine.conn.sql("SELECT * FROM era_stats").pl()
        
        if df.is_empty():
            return df.with_columns(pl.lit(None).cast(pl.Int32).alias("cluster")), 0.0, 1
        if len(df) < 3:
            return df.with_columns(pl.lit(0).alias("cluster")), 0.0, 1
        
        feat = df.select(['co_auth', 'salton']).to_numpy()
        scaled = self._scaler.fit_transform(feat)
        
        best_k, max_s, labels = 2, -1, None
        limit = min(len(df), 7)
        
        for k in range(2, limit):
            model = KMeans(n_clusters=k, random_state=42, n_init=10)
            l = model.fit_predict(scaled)
            s = silhouette_score(scaled, l)
            if s > max_s:
                max_s, best_k, labels = s, k, l
                
        if labels is None:
            return df.with_columns(pl.lit(0).alias("cluster")), 0.0, 1
        return df.with_columns(pl.Series("cluster", labels)), max_s, best_k

    def find_hierarchical_clusters(self, year: int, target_country: str):
        self.engine.calc_country_stats(target_country, year)
        df = self.engine.conn.sql("SELECT * FROM era_stats").pl()
        
        if df.is_empty():
            return df.with_columns(pl.lit(None).cast(pl.Int32).alias("h_cluster")), 0.0, 1
        if len(df) < 3:
            return df.with_columns(pl.lit(0).alias("h_cluster")), 0.0, 1
        
        feat = df.select(['co_auth', 'salton']).to_numpy()
        scaled = self._scaler.fit_transform(feat)
        
        best_k, max_s, labels = 2, -1, None
        limit = min(len(df), 7)
        
        for k in range(2, limit):
            model = AgglomerativeClustering(n_clusters=k, linkage='ward')
            l = model.fit_predict(scaled)
            s = silhouette_score(scaled, l)
            if s > max_s:
                max_s, best_k, labels = s, k, l
                
        if labels is None:
            return df.with_columns(pl.lit(0).alias("h_cluster")), 0.0, 1
        return df.with_columns(pl.Series("h_cluster", labels)), max_s, best_k

    def get_communities(self, year: int):
        G = self._build_graph(year)
        if G.number_of_edges() == 0:
            return {}, 0.0
        partition = community_louvain.best_partition(G, weight='weight')
        modularity = community_louvain.modularity(partition, G, weight='weight')
        comm = {}
        for node, c_id in partition.items():
            comm.setdefault(c_id, []).append(node)
        return comm, modularity
    
    def assign_global_tiers(self, year: int):
        """Divides all countries in the region into 3 global leagues (Tiers)."""
        import pandas as pd
        from sklearn.cluster import KMeans
        
        #1. Obtain graph metrics (how wide are the connections and who is the intermediary)
        centrality = self.get_centrality_metrics(year)
        if centrality['density'] == 0.0:
            return {c: "Tier 3 (Peripheral)" for c in config.COUNTRIES_LIST}
            
        deg_dict = centrality['degree']
        bet_dict = centrality['betweenness']
        
        # 2. Obtaining volumes of regional articles from the database
        stats_df = self.engine.get_global_integration_stats(year).to_pandas()
        
        #3. We are compiling a single matrix of features for all 20 countries
        data = []
        for c in config.COUNTRIES_LIST:
            c = c.lower()
            deg = deg_dict.get(c, 0.0)
            bet = bet_dict.get(c, 0.0)
            row = stats_df[stats_df['country'] == c]
            papers = row['total_regional_papers'].values[0] if not row.empty else 0
            
            data.append({'country': c, 'degree': deg, 'betweenness': bet, 'papers': papers})
            
        df = pd.DataFrame(data)
        
        if df['papers'].sum() == 0:
             return {c: "Tier 3 (Peripheral)" for c in config.COUNTRIES_LIST}
             
        # Scaling features
        features = df[['degree', 'betweenness', 'papers']].values
        scaled = self._scaler.fit_transform(features)
        
        #4. Strict clustering into 3 leagues
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(scaled)
        
        # 5. Automatic ranking: Who is the elite and who is the periphery?
        # Calculating the average cluster weight across all metrics
        cluster_centers = pd.DataFrame(kmeans.cluster_centers_, columns=['degree', 'betweenness', 'papers'])
        cluster_centers['score'] = cluster_centers.mean(axis=1) 

        ranked = cluster_centers.sort_values('score', ascending=False).index.tolist()
        
        tier_mapping = {
            ranked[0]: "Tier 1 (Regional Hubs)",
            ranked[1]: "Tier 2 (Active Players)",
            ranked[2]: "Tier 3 (Peripheral)"
        }
        
        df['tier'] = df['cluster'].map(tier_mapping)
        return dict(zip(df['country'], df['tier']))