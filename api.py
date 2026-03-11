import uvicorn
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from analyzer import ScientometricAnalyzer
import pandas as pd
import math
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    analyzer = ScientometricAnalyzer()
    logger.info("ScientometricAnalyzer successfully initialized.")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise RuntimeError("Database initialization failed. Check config and file paths.")

@app.get("/api/metrics")
def get_metrics(target: str = 'israel', compare: str = 'united arab emirates'):
    target = target.lower().strip()
    compare = compare.lower().strip()
    logger.info(f"Processing request for dyad: {target} & {compare}")
    
    try:
        # --- HYPOTHESIS 1 ---
        df_all = analyzer.get_country_timeseries(target, False)
        df_reg = analyzer.get_country_timeseries(target, True)
        
        if not df_all.empty:
            df_h1 = pd.merge(df_all, df_reg, on='year', how='left', suffixes=('_total', '_regional')).fillna(0)
        else:
            df_h1 = pd.DataFrame(columns=['year', 'papers_total', 'papers_regional'])
            
        # --- HYPOTHESIS 2 ---
        dyad_df = analyzer.get_group_collaboration([target, compare])
        
        pre, post, growth = 0.0, 0.0, 0.0
        if not dyad_df.empty:
            pre_slice = dyad_df[(dyad_df['year'] >= 2015) & (dyad_df['year'] <= 2019)]['joint_papers']
            post_slice = dyad_df[(dyad_df['year'] >= 2021) & (dyad_df['year'] <= 2025)]['joint_papers']
            
            pre = float(pre_slice.mean()) if not pre_slice.empty else 0.0
            post = float(post_slice.mean()) if not post_slice.empty else 0.0
            
            if math.isnan(pre): pre = 0.0
            if math.isnan(post): post = 0.0
            
            if pre > 0:
                growth = ((post - pre) / pre * 100)
        
        # --- GLOBAL BROKERS ---
        brokers_df = analyzer.get_global_brokers_for_dyad(target, compare)
        total_broker_papers = brokers_df['papers'].sum() if not brokers_df.empty and brokers_df['papers'].sum() > 0 else 1
        
        global_brokers = []
        for _, row in brokers_df.iterrows():
            global_brokers.append({
                "name": str(row['global_broker']).title(),
                "papers": int(row['papers']),
                "percent": round((row['papers'] / total_broker_papers) * 100)
            })

        # --- HYPOTHESIS 4 (NEUTRAL TOPICS) ---
        subjects_df = analyzer.get_dyad_subjects(target, compare)
        subjects_yearly_df = analyzer.get_dyad_subjects_yearly(target, compare)

        top_subjects = []
        neutral_papers_count = 0
        total_papers_with_subjects = 0
        
        for _, row in subjects_df.iterrows():
            subj = str(row['subject']).strip()
            cnt = int(row['papers'])
            total_papers_with_subjects += cnt
            
            if subj in config.NEUTRAL_FIELDS:
                neutral_papers_count += cnt
                
            if len(top_subjects) < 5 and subj not in ['unknown', 'multidisciplinary', '']:
                display_name = subj.title()
                if "Biochemistry" in display_name: display_name = "Biochem & Genetics"
                if "Agricultural" in display_name: display_name = "Agriculture"
                
                top_subjects.append({
                    "subject": display_name,
                    "papers": cnt
                })
                
        neutral_ratio = round((neutral_papers_count / total_papers_with_subjects) * 100, 1) if total_papers_with_subjects > 0 else 0

        # --- HYPOTHESIS 3 & DATASET ASSEMBLY ---
        dataset = []
        for year in range(config.START_YEAR, config.END_YEAR + 1):
            h1_row = df_h1[df_h1['year'] == year]
            h1_tot = int(h1_row['papers_total'].values[0]) if not h1_row.empty else 0
            h1_reg = int(h1_row['papers_regional'].values[0]) if not h1_row.empty else 0
            
            h2_row = dyad_df[dyad_df['year'] == year] if not dyad_df.empty else pd.DataFrame()
            h2_joint = int(h2_row['joint_papers'].values[0]) if not h2_row.empty else 0
            
            net_metrics = analyzer.get_network_metrics(year)
            if net_metrics:
                try:
                    top_b = max(net_metrics, key=lambda k: net_metrics[k]['betweenness'])
                    top_b_score = net_metrics[top_b]['betweenness']
                except ValueError:
                    top_b = "No Data"
                    top_b_score = 0.0
                    
                target_eigen = net_metrics.get(target, {}).get('eigenvector', 0.0)
            else:
                top_b = "No Data"
                top_b_score = 0.0
                target_eigen = 0.0

            # --- Data for H4 Timeline ---
            h4_neutral_count = 0
            h4_other_count = 0
            if not subjects_yearly_df.empty:
                year_data = subjects_yearly_df[subjects_yearly_df['year'] == year]
                for _, row in year_data.iterrows():
                    subj = str(row['subject']).strip()
                    cnt = int(row['papers'])
                    if subj in config.NEUTRAL_FIELDS:
                        h4_neutral_count += cnt
                    elif subj not in ['unknown', 'multidisciplinary', '']:
                        h4_other_count += cnt
                
            dataset.append({
                "year": year,
                "h1_total": h1_tot,
                "h1_reg": h1_reg,
                "h2_joint": h2_joint,
                "h3_broker_score": round(top_b_score, 3),
                "h3_broker_name": top_b.title(),
                "h3_target": round(target_eigen, 4),
                "h4_neutral": h4_neutral_count,
                "h4_other": h4_other_count
            })
            
        return {
            "dataset": dataset,
            "globalBrokers": global_brokers,
            "summary": {
                "pre": round(pre, 1), 
                "post": round(post, 1), 
                "growth": round(growth, 1)
            },
            "h4_subjects": top_subjects,         
            "h4_neutral_ratio": neutral_ratio    
        }
        
    except Exception as e:
        logger.error(f"Error calculating metrics for {target} & {compare}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal calculation error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)