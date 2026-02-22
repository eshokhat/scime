import sys
import matplotlib.pyplot as plt
import seaborn as sns
import config
from engine import AnalysisEngine
from ml import ScienceML

def clear_terminal():
    print("\n" * 2)

def plot_country_eda(engine: AnalysisEngine, country: str):
    target = country.strip().lower()
    time_df = engine._query(f"SELECT a.year, COUNT(DISTINCT a.eid) as papers FROM {config.TABLES['articles']} a JOIN {config.TABLES['countries']} c ON a.eid = c.eid WHERE LOWER(TRIM(c.country)) = '{target}' AND a.year BETWEEN {config.START_YEAR} AND {config.END_YEAR} GROUP BY a.year ORDER BY a.year").to_pandas()
    subject_df = engine._query(f"SELECT LOWER(TRIM(s.subject)) as subject, COUNT(DISTINCT s.eid) as papers FROM {config.TABLES['subjects']} s JOIN {config.TABLES['countries']} c ON s.eid = c.eid WHERE LOWER(TRIM(c.country)) = '{target}' AND LOWER(TRIM(s.subject)) NOT IN ('unknown', '') GROUP BY 1 ORDER BY 2 DESC LIMIT 5").to_pandas()

    if time_df.empty or subject_df.empty:
        print(f"No data for country: {country.title()}")
        return

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle(f'Basic analysis: {country.upper()}', fontsize=16)
    sns.lineplot(ax=axes[0], data=time_df, x='year', y='papers', marker='o', color='crimson')
    axes[0].set_title('Volume of publications by year')
    sns.barplot(ax=axes[1], data=subject_df, x='papers', y='subject', palette='viridis')
    axes[1].set_title('Top 5 scientific directions')
    axes[1].set_ylabel('')
    plt.tight_layout()
    plt.show()


def plot_ml_trends(years, centrality_hist, tier_hist, country: str):
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f'Evolution in the regional network: {country.upper()}', fontsize=16)

    axes[0].plot(years, centrality_hist, marker='s', color='darkblue', linewidth=2)
    axes[0].set_title('Betweenness Centrality')
    axes[0].set_ylabel('Centrality Score')
    axes[0].grid(True, linestyle='--', alpha=0.7)

    # Tiers
    tier_map = {"Tier 1 (Regional Hubs)": 2, "Tier 2 (Active Players)": 1, "Tier 3 (Peripheral)": 0}
    y_numeric = [tier_map[tier] for tier in tier_hist]
    
    axes[1].step(years, y_numeric, where='mid', color='darkorange', linewidth=2, marker='o')
    axes[1].set_title('Global Ranking (Level of Regional Integration)')
    axes[1].set_yticks([0, 1, 2])
    axes[1].set_yticklabels(["Tier 3 (Periphery)", "Tier 2 (Mid-Range)", "Tier 1 (Hub)"])
    axes[1].set_xlabel('Year')
    axes[1].grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.show()

def run_interactive_pipeline():
    engine = AnalysisEngine()
    ml = ScienceML(engine)
    
    clear_terminal()
    print("="*60)
    print(" REGIONAL SCIENCE DIPLOMACY ANALYZER ")
    print("="*60)

    engine.get_db_summary()

    ans_eda = input("? Do you want to create baseline plots for the dataset? (y/n): ").strip().lower()
    if ans_eda == 'y':
        target_country = input("Enter a country name: ").strip().lower()
        plot_country_eda(engine, target_country)
    
    ans_ml = input("\n? Do you want to continue with clustering and network analysis? (y/n): ").strip().lower()
    if ans_ml != 'y':
        sys.exit()

    clear_terminal()
    years = list(range(config.START_YEAR, config.END_YEAR + 1))
    
    country_betweenness = []
    country_tier = []
    
    ml_country = input("? For which country should we collect ML trend history? : ").strip().lower()
    
    print("\n" + "-"*90)
    print(f"{'Year':<6} | {'Density':<8} | {'Modularity':<11} | {'Brokers (Top-3)':<35} | {ml_country.title()} Global Tier")
    print("-" * 90)

    for year in years:
        centrality = ml.get_centrality_metrics(year)
        _, mod = ml.get_communities(year)
        brokers_df = engine.get_external_brokers(year, limit=3)
        brokers_str = ", ".join(brokers_df['broker'].to_list()) if not brokers_df.is_empty() else "None"
        
        density = centrality.get('density', 0.0)
        country_betweenness.append(centrality['betweenness'].get(ml_country, 0.0))

        # GLOBAL CLUSTERING
        global_tiers = ml.assign_global_tiers(year)
        current_tier = global_tiers.get(ml_country, "Tier 3 (Peripheral)")
        country_tier.append(current_tier)

        tier_short = current_tier.split(" ")[0] + " " + current_tier.split(" ")[1]
        print(f"{year:<6} | {density:<8.4f} | {mod:<11.4f} | {brokers_str:<35} | {tier_short}")

    print("-" * 90)

    ans_viz = input(f"\n? Want to visualize ML trends for {ml_country.title()}? (y/n): ").strip().lower()
    if ans_viz == 'y':
        plot_ml_trends(years, country_betweenness, country_tier, ml_country)

if __name__ == "__main__":
    run_interactive_pipeline()