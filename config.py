# CONFIG FILE

import os

# --- DIRECTORIES ---
DB_PATH = "database.db"

# --- DATABASE SCHEMA (Mapping for new structure) ---

TABLES = {
    "articles": "articles",   # eid, title, doi, year, journal
    "subjects": "subjects",   # eid, subject
    "countries": "countries", # eid, country
    "baseline": "baseline"    # country, year, total_output
}

# --- GEOGRAPHY (Normalized list) ---
# Middle East North Africa countries list
COUNTRIES_LIST = [
    "israel", "algeria", "bahrain", "egypt", "iran", "iraq", "jordan", 
    "kuwait", "lebanon", "libya", "morocco", "oman", "palestine", "qatar", 
    "saudi arabia", "syria", "tunisia", "turkey", "united arab emirates", "yemen"
]

# --- CHRONOLOGY (Eras for analysis) ---

START_YEAR = 2000
END_YEAR = 2025

# --- RESEARCH SETTINGS ---
# Minimal Salton 
MIN_SALTON_THRESHOLD = 0.0001

# If we want to check if there's any collaboration in neutral fields that are less impacted by politics
NEUTRAL_FIELDS = [
    'medicine', 'physics and astronomy', 'biochemistry, genetics and molecular biology',
    'engineering', 'environmental science', 'agricultural and biological sciences',
    'materials science', 'chemistry', 'mathematics', 'computer science'
]