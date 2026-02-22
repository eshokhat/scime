# DATABASE CREATION

import pandas as pd

baseline = pd.read_csv('raw/baseline.csv') # Total country output in Scopus for a period 2000-2025
master = pd.read_csv('raw/master.csv') # Full database for countries in the list with subject areas added from scopus_sources

# --- ALL COUNTRIES ---

countries_df = master[['eid', 'all_countries']].copy()

# Turn the string "Country1; Country2" into a list ["Country1", "Country2"]
countries_df['country'] = countries_df['all_countries'].str.split('; ')

# Use explode - this will "expand" the list into separate lines
countries_df = countries_df.explode('country')
countries_df['country'] = countries_df['country'].str.strip()
countries_df['country'] = countries_df['country'].replace('Türkiye', 'Turkey')
countries_df = countries_df.drop(columns=['all_countries']).dropna(subset=['country'])


# --- SUBJECT AREAS ---
# The logic is the same, but the separator is usually "|"

subjects_df = master[['eid', 'subject_areas']].copy()
subjects_df['subject'] = subjects_df['subject_areas'].str.split('|')
subjects_df = subjects_df.explode('subject')
subjects_df['subject'] = subjects_df['subject'].str.strip()
subjects_df = subjects_df.drop(columns=['subject_areas']).dropna(subset=['subject'])

# Lower-casing 
countries_df['country'] = countries_df['country'].str.strip().str.lower()
subjects_df['subject'] = subjects_df['subject'].str.strip().str.lower()
baseline['country'] = baseline['country'].str.strip().str.lower()

# --- SAVING THE RESULTS ---

countries_df.to_csv('master_countries.csv', index=False)
subjects_df.to_csv('master_subjects.csv', index=False)
master_clean = master.drop(columns=['all_countries', 'subject_areas'])
master_clean.to_csv('master_main.csv', index=False)

print(f"Done! Countries lines: {len(countries_df)}")
print(f"Done! Subject lines: {len(subjects_df)}")

# CREATING THE DUCKDB DATABASE

import duckdb

con = duckdb.connect('database.db')
print("Initializing the database...")

# List of tables and corresponding files
tables = {
    "articles": "master_main.csv",
    "countries": "master_countries.csv",
    "subjects": "master_subjects.csv",
    "baseline": "raw/baseline.csv"
}

for table_name, file_path in tables.items():
    con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM read_csv_auto('{file_path}') LIMIT 0")

    count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    if count == 0:
        print(f"Loading data into {table_name}...")
        con.execute(f"INSERT INTO {table_name} SELECT * FROM read_csv_auto('{file_path}')")
    else:
        print(f"Table {table_name} already exists and contains data. Skipping import.")

print("Database ready!")

con.close()