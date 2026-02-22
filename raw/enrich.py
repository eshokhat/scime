import pandas as pd
import os
import re

ASJC_MAP = {
    '10': 'Multidisciplinary',
    '11': 'Agricultural & Biological Sciences',
    '12': 'Arts and Humanities',
    '13': 'Biochemistry, Genetics & Molecular Biology',
    '14': 'Business, Management and Accounting',
    '15': 'Chemical Engineering',
    '16': 'Chemistry',
    '17': 'Computer Science',
    '18': 'Decision Sciences',
    '19': 'Earth and Planetary Sciences',
    '20': 'Economics, Econometrics and Finance',
    '21': 'Energy',
    '22': 'Engineering',
    '23': 'Environmental Science',
    '24': 'Immunology and Microbiology',
    '25': 'Materials Science',
    '26': 'Mathematics',
    '27': 'Medicine',
    '28': 'Neuroscience',
    '29': 'Nursing',
    '30': 'Pharmacology, Toxicology and Pharmaceutics',
    '31': 'Physics and Astronomy',
    '32': 'Psychology',
    '33': 'Social Sciences',
    '34': 'Veterinary',
    '35': 'Dentistry',
    '36': 'Health Professions'
}

def get_category_from_code(code_str):
    """Getting category from ASJC code"""
    if not code_str: return None
    code_str = str(code_str).strip()
    if len(code_str) < 2: return None
    
    # (22xx -> 22)
    prefix = code_str[:2]
    return ASJC_MAP.get(prefix)

def clean_text(text):
    """Clears the journal name for searching (removes case and spaces)."""
    if not isinstance(text, str): return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def run_enrichment():
    files = [f for f in os.listdir('.') if 'scopus_source' in f.lower() and ('xlsx' in f or 'csv' in f)]
    if not files:
        print("Error: Scopus Sources file (xlsx/csv) not found in folder.")
        return
    
    source_file = files[0]
    raw_file = 'full_database_FINAL.csv'
    output_file = 'master.csv'
    
    print(f"1. Reading the Scopus Sources file {source_file}")

    try:
        if source_file.endswith('.csv'):
            df_source = pd.read_csv(source_file, on_bad_lines='skip', encoding='utf-8', sep=None, engine='python')
        else:
            df_source = pd.read_excel(source_file)
        df_source.columns = [str(c).strip() for c in df_source.columns]
        
    except Exception as e:
        print(f" Error reading file: {e}")
        return

# --- 2. SEARCHING FOR THE REQUIRED COLUMNS ---
    
# A) We look for the name of the journal
    title_col = None
    possible_names = ['Source Title', 'Title', 'Sourcetitle', 'PubName']
    for col in df_source.columns:
        if any(name.lower() == col.lower() for name in possible_names):
            title_col = col
            break
            
    if not title_col:
        title_col = df_source.columns[1]
        print(f" Column with title not found explicitly. Using: {title_col}")

    # B) Look for the column with ASJC codes
    # It's usually called "All Science Journal Classification Codes (ASJC)" or simply "ASJC"
    asjc_col = None
    for col in df_source.columns:
        if "asjc" in str(col).lower() and "code" in str(col).lower():
            asjc_col = col
            break
    
    if not asjc_col:
        print("Error: Column with ASJC codes not found in the directory.")
        print("Try downloading the full 'Scopus Source List' (it should have an ASJC column).")
        return
    else:
        print(f" Found code column: {asjc_col}")

    # --- 3. CREATING A MAP (JOURNAL -> TEXT CATEGORIES) ---
    print("2. Translating codes into words...")
    journal_map = {}
    
    for _, row in df_source.iterrows():
        j_name = clean_text(row[title_col])
        if not j_name: continue
        
        codes_raw = str(row[asjc_col])
        if codes_raw in ['nan', 'None', '']: continue

        codes_raw = codes_raw.replace(';', ' ').replace(',', ' ')
        codes = codes_raw.split()
        
        subjects = set()
        for code in codes:
            code = code.split('.')[0]
            category = get_category_from_code(code)
            if category:
                subjects.add(category)
        
        if subjects:
            journal_map[j_name] = "|".join(sorted(subjects))
        else:
            journal_map[j_name] = "Multidisciplinary"

    print(f" Dictionary ready. Journals in the database: {len(journal_map)}")

    # --- 4. APPLYING TO THE FILE ---
    print(f"3. Processing {raw_file}...")
    try:
        df_data = pd.read_csv(raw_file)
    except:
        print("The file full_database_FINAL.csv was not found")
        return

    def get_subject(j_name):
        return journal_map.get(clean_text(j_name), "Unknown")

    df_data['subject_areas'] = df_data['journal'].apply(get_subject)
    
    # Stats
    filled = df_data[df_data['subject_areas'] != "Unknown"]
    print(f" Result: {len(filled)} of {len(df_data)} works recognized ({len(filled)/len(df_data):.1%})")

    df_data.to_csv(output_file, index=False)
    print(f" Done! File saved as: {output_file}")

if __name__ == "__main__":
    run_enrichment()