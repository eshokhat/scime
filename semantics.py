import config
from engine import AnalysisEngine
import polars as pl

def analyze_semantic_evolution():
    engine = AnalysisEngine()
    
    # Returning to macro-epochs to assess thematic shifts
    eras = [
        ("Era 1: Pre-Spring (2000-2010)", 2000, 2010),
        ("Era 2: Instability (2011-2019)", 2011, 2019),
        ("Era 3: Abraham Accords (2020-2025)", 2020, 2025)
    ]
    
    # We set the composition of the "Arabic Core" (Tier 1 according to our previous tests in main.py)
    core_arab = "'saudi arabia', 'egypt', 'united arab emirates'"
    
    print("="*90)
    print(" THEMATIC EVOLUTION: CORE vs PERIPHERY ")
    print("="*90)
    
    for name, start, end in eras:
        print(f"\n>>> {name.upper()} <<<")
        
        # 1. Arabic Core Topics (interaction within the core)
        core_sql = f"""
            SELECT LOWER(TRIM(s.subject)) as subject, COUNT(DISTINCT a.eid) as papers
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            JOIN {config.TABLES['subjects']} s ON a.eid = s.eid
            WHERE a.year BETWEEN {start} AND {end}
              AND LOWER(TRIM(c1.country)) IN ({core_arab})
              AND LOWER(TRIM(c2.country)) IN ({core_arab})
              AND LOWER(TRIM(c1.country)) < LOWER(TRIM(c2.country))
              AND LOWER(TRIM(s.subject)) NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """
        core_themes = engine._query(core_sql)
        
        # 2. Israel topics (with any regional partners)
        israel_sql = f"""
            SELECT LOWER(TRIM(s.subject)) as subject, COUNT(DISTINCT a.eid) as papers
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            JOIN {config.TABLES['subjects']} s ON a.eid = s.eid
            WHERE a.year BETWEEN {start} AND {end}
              AND LOWER(TRIM(c1.country)) = 'israel'
              AND LOWER(TRIM(c2.country)) IN ({engine._mena_list})
              AND LOWER(TRIM(c2.country)) != 'israel'
              AND LOWER(TRIM(s.subject)) NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """
        israel_themes = engine._query(israel_sql)

        # 3. Iran topics (with any regional partners)
        iran_sql = f"""
            SELECT LOWER(TRIM(s.subject)) as subject, COUNT(DISTINCT a.eid) as papers
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            JOIN {config.TABLES['subjects']} s ON a.eid = s.eid
            WHERE a.year BETWEEN {start} AND {end}
              AND LOWER(TRIM(c1.country)) = 'iran'
              AND LOWER(TRIM(c2.country)) IN ({engine._mena_list})
              AND LOWER(TRIM(c2.country)) != 'iran'
              AND LOWER(TRIM(s.subject)) NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """
        iran_themes = engine._query(iran_sql)

        # 4. Turkey topics (with any regional partners)
        turkey_sql = f"""
            SELECT LOWER(TRIM(s.subject)) as subject, COUNT(DISTINCT a.eid) as papers
            FROM {config.TABLES['articles']} a
            JOIN {config.TABLES['countries']} c1 ON a.eid = c1.eid
            JOIN {config.TABLES['countries']} c2 ON a.eid = c2.eid
            JOIN {config.TABLES['subjects']} s ON a.eid = s.eid
            WHERE a.year BETWEEN {start} AND {end}
              AND LOWER(TRIM(c1.country)) = 'turkey'
              AND LOWER(TRIM(c2.country)) IN ({engine._mena_list})
              AND LOWER(TRIM(c2.country)) != 'turkey'
              AND LOWER(TRIM(s.subject)) NOT IN ('unknown', '')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """
        turkey_themes = engine._query(turkey_sql)

        # Formatted output
        print(f"  [Arab Core (KSA, EGY, UAE) Internal Collabs]")
        for row in core_themes.iter_rows():
            print(f"    - {row[0].title()}: {row[1]} papers")
            
        print(f"\n  [Israel Regional Collabs]")
        for row in israel_themes.iter_rows():
            print(f"    - {row[0].title()}: {row[1]} papers")

        print(f"\n  [Iran Regional Collabs]")
        for row in iran_themes.iter_rows():
            print(f"    - {row[0].title()}: {row[1]} papers")

        print(f"\n  [Turkey Regional Collabs]")
        for row in turkey_themes.iter_rows():
            print(f"    - {row[0].title()}: {row[1]} papers")            
        print("-" * 90)

if __name__ == "__main__":
    analyze_semantic_evolution()