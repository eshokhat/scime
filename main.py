import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from analyzer import ScientometricAnalyzer
import config

def plot_academic_results(df_h1, group_df, centrality_history, target_country, comparison_group):
    """Generates academic-standard plots for the hypotheses, including historical event markers."""
    plt.style.use('seaborn-v0_8-white')
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    # --- Historical Markers Setup ---
    events = [
        {'year': 2011, 'color': 'orange', 'label': 'Arab Spring (2011)'},
        {'year': 2020, 'color': 'red', 'label': 'Abraham Accords (2020)'}
    ]

    # --- Plot 1: Mega-Projects vs Regional ---
    if df_h1 is not None and not df_h1.empty:
        df_h1_plot = df_h1[df_h1['year'] >= config.START_YEAR]
        axes[0].plot(df_h1_plot['year'], df_h1_plot['papers_total'], label='Total Regional', color='black', marker='o')
        axes[0].plot(df_h1_plot['year'], df_h1_plot['papers_regional'], label='Strictly Regional (<=5)', color='gray', linestyle='--')
        axes[0].set_title(f'H1: {target_country.title()} Integration Context')
        axes[0].set_ylabel('Publications')
        axes[0].legend()
        axes[0].set_xlim(config.START_YEAR, config.END_YEAR)
        axes[0].xaxis.set_major_locator(MaxNLocator(integer=True))

    # --- Plot 2: N-adic Temporal Dynamics ---
    if group_df is not None and not group_df.empty:
        group_df_plot = group_df[group_df['year'] >= config.START_YEAR]
        axes[1].plot(group_df_plot['year'], group_df_plot['joint_papers'], color='blue', marker='s')
        for event in events:
            axes[1].axvline(x=event['year'], color=event['color'], linestyle=':', label=event['label'])
        group_title = " & ".join([c.title() for c in comparison_group])
        axes[1].set_title(f'H2: Joint Output ({group_title})')
        axes[1].set_ylabel('Joint Publications')
        axes[1].legend()
        axes[1].set_xlim(config.START_YEAR, config.END_YEAR)
        axes[1].xaxis.set_major_locator(MaxNLocator(integer=True))
    else:
        axes[1].set_title('H2: No Joint Data Available')

    # --- Plot 3: Network Centrality Shifts ---
    if centrality_history:
        years = sorted(list(centrality_history.keys()))
        target_eigen = [centrality_history[y].get(target_country, {}).get('eigenvector', 0) for y in years]
        
        top_betweenness = []
        for y in years:
            if centrality_history[y]:
                max_b = max([metrics['betweenness'] for metrics in centrality_history[y].values()])
                top_betweenness.append(max_b)
            else:
                top_betweenness.append(0)
        
        axes[2].plot(years, top_betweenness, label='Top Regional Broker (Betweenness)', color='black', linestyle='-.')
        axes[2].plot(years, target_eigen, label=f'{target_country.title()} Integration (Eigenvector)', color='green', marker='^')
        for event in events:
            axes[2].axvline(x=event['year'], color=event['color'], linestyle=':', label=event['label'])
        axes[2].set_title('H3: Network Centrality Evolution')
        axes[2].set_ylabel('Centrality Score')
        axes[2].legend()
        axes[2].set_xlim(config.START_YEAR, config.END_YEAR)
        axes[2].xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()
    plt.show()

def main():
    analyzer = ScientometricAnalyzer()
    
    print("\n" + "="*80)
    print(" MIDDLE EAST SCIENTOMETRIC ANALYSIS ".center(80))
    print("="*80)
    
    metrics = analyzer.get_basic_metrics()
    print(f"Total Database Articles: {metrics['total_papers']}\n")
    
    target_country = input("Enter target country (e.g., israel): ").strip().lower()
    if not target_country:
        print("Termination: No country selected.")
        return

    # --- HYPOTHESIS 1 ---
    print("\n" + "-"*80)
    print(f"HYPOTHESIS 1: Mega-Projects vs Regional Science | {target_country.upper()}")
    print("-" * 80)
    
    df_all = analyzer.get_country_timeseries(target_country, exclude_mega_projects=False)
    df_regional = analyzer.get_country_timeseries(target_country, exclude_mega_projects=True)
    
    df_comp = None
    if df_all.empty:
        print(f"No data found for {target_country.title()}.")
    else:
        df_comp = pd.merge(df_all, df_regional, on='year', how='left', suffixes=('_total', '_regional')).fillna(0)
        df_comp['mega_project_papers'] = df_comp['papers_total'] - df_comp['papers_regional']
        df_comp['regional_share_%'] = (df_comp['papers_regional'] / df_comp['papers_total'] * 100).round(1)
        print(df_comp[df_comp['year'] >= 2000].to_string(index=False))

    # --- HYPOTHESIS 2 & GLOBAL BROKERS ---
    compare_input = input("\nEnter countries to compare (comma-separated, e.g., egypt, jordan) or Enter to skip: ").strip().lower()
    
    group_df = None
    comparison_group = [target_country]
    is_dyad = False
    
    if compare_input:
        additional_countries = [c.strip() for c in compare_input.split(',')]
        comparison_group.extend(additional_countries)
        
        if len(comparison_group) == 2:
            is_dyad = True
            
        print("\n" + "-"*80)
        print(f"HYPOTHESIS 2: Polyadic Dynamics | {', '.join(comparison_group).upper()}")
        print("-" * 80)
        
        group_df = analyzer.get_group_collaboration(comparison_group)
        if group_df.empty:
            print("No joint publications found for this specific group.")
        else:
            print(group_df[group_df['year'] >= 2015].to_string(index=False))

        # Academic summary metrics
        pre_accords = group_df[(group_df['year'] >= 2015) & (group_df['year'] <= 2019)]['joint_papers'].mean()
        post_accords = group_df[(group_df['year'] >= 2021) & (group_df['year'] <= 2025)]['joint_papers'].mean()
            
        print("\n  [Analytical Summary]")
        print(f"  Average papers/year (Pre-2020):  {pre_accords:.1f}")
        print(f"  Average papers/year (Post-2020): {post_accords:.1f}")
        
        if pre_accords > 0:
            growth = ((post_accords - pre_accords) / pre_accords) * 100
            print(f"  Post-Accords Growth Rate:        +{growth:.1f}%")    

        # --- GLOBAL BROKERS (Only executed if exactly two countries are compared) ---
        if is_dyad:
            print("\n" + "-"*80)
            print(f"GLOBAL BROKERS ANALYSIS | {target_country.upper()} & {comparison_group[1].upper()}")
            print("-" * 80)
            brokers_df = analyzer.get_global_brokers_for_dyad(target_country, comparison_group[1])
            if brokers_df.empty:
                print("No global brokers found for this dyad.")
            else:
                print(brokers_df.to_string(index=False))
            
    # --- HYPOTHESIS 3 ---
    print("\n" + "-"*80)
    print("HYPOTHESIS 3: Network Topology (Brokerage & Integration)")
    print("-" * 80)
    
    print(f"{'Year':<6} | {'Top Broker (Betweenness)':<30} | {target_country.title()} Integration (Eigenvector)")
    print("-" * 80)
    
    centrality_history = {}
    
    for year in range(config.START_YEAR, config.END_YEAR + 1):
        network_metrics = analyzer.get_network_metrics(year)
        centrality_history[year] = network_metrics
        
        if not network_metrics:
            print(f"{year:<6} | {'No Network Data':<30} | N/A")
            continue
            
        top_broker = max(network_metrics, key=lambda k: network_metrics[k]['betweenness'])
        top_b_score = network_metrics[top_broker]['betweenness']
        target_eigen = network_metrics.get(target_country, {}).get('eigenvector', 0.0)
        
        print(f"{year:<6} | {top_broker.title()[:20]:<20} ({top_b_score:.3f}) | {target_eigen:.4f}")

    print("\n" + "="*80)
    print("Analysis Complete. Generating Visualizations...".center(80))
    print("="*80)
    
    plot_academic_results(df_comp, group_df, centrality_history, target_country, comparison_group)

if __name__ == "__main__":
    main()