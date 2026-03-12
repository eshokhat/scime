import duckdb
import pandas as pd
import config

def run_sensitivity_analysis(target_country: str = 'israel'):
    """ 
    Conducts a sensitivity analysis for hypothesis H1 by varying 
    cut-off threshold for mega-projects (k = 3, 5, 7 countries). 
    """
    print(f"Running Sensitivity Analysis for: {target_country.upper()}")
    print("-" * 50)
    
    conn = duckdb.connect('database.db', read_only=True)
    
    query = f"""
        WITH paper_counts AS (
            SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) as country_count
            FROM {config.TABLES['countries']}
            GROUP BY eid
        ),
        target_papers AS (
            SELECT a.year, a.eid
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c ON a.eid = c.eid
            WHERE LOWER(TRIM(c.country)) = '{target_country.lower()}'
        )
        SELECT 
            t.year,
            COUNT(DISTINCT t.eid) as total_papers,
            COUNT(DISTINCT CASE WHEN pc.country_count <= 3 THEN t.eid END) as k_3,
            COUNT(DISTINCT CASE WHEN pc.country_count <= 5 THEN t.eid END) as k_5_baseline,
            COUNT(DISTINCT CASE WHEN pc.country_count <= 7 THEN t.eid END) as k_7
        FROM target_papers t
        JOIN paper_counts pc ON t.eid = pc.eid
        GROUP BY t.year
        ORDER BY t.year
    """
    
    df = conn.sql(query).df()
    
    if df.empty:
        print("No data found for the target country.")
        return

    # We display the first and last 3 years for clarity
    print(df.head(3).to_string(index=False))
    print("...")
    print(df.tail(3).to_string(index=False))
    print("-" * 50)
    
    # ---------------------------------------------------------
    # EVIDENCE FOR THE ARTICLE (Correlation Analysis)
    # ---------------------------------------------------------
    corr_3_5 = df['k_3'].corr(df['k_5_baseline'])
    corr_7_5 = df['k_7'].corr(df['k_5_baseline'])
    
    avg_share_5 = (df['k_5_baseline'] / df['total_papers']).mean() * 100
    
    print("\n[SCIENTIFIC JUSTIFICATION SUMMARY FOR PAPER]")
    print(f"1. Baseline k=5 captures on average {avg_share_5:.1f}% of total output.")
    print(f"2. Pearson Correlation (k=3 vs k=5): {corr_3_5:.4f}")
    print(f"3. Pearson Correlation (k=7 vs k=5): {corr_7_5:.4f}")
    
    print("\nConclusion for methodology section:")
    if corr_3_5 > 0.95 and corr_7_5 > 0.95:
        print("=> SUCCESS: The structural dynamics of regional integration are highly robust. "
              "Since the correlation across k=3, 5, and 7 exceeds 0.95, the choice of k=5 "
              "does not introduce arbitrary bias into the temporal trend analysis.")
    else:
        print("=> WARNING: The trend significantly changes depending on the threshold.")

if __name__ == "__main__":
    run_sensitivity_analysis('israel')