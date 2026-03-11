# Scientometric Analysis of Middle Eastern Scientific Cooperation (2000–2025)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![DuckDB](https://img.shields.io/badge/Database-DuckDB-yellow)
![NetworkX](https://img.shields.io/badge/Graph-NetworkX-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## Project Overview
This project provides a rigorous, data-driven framework to analyze the evolution of scientific collaboration networks in the Middle East and North Africa (MENA) from 2000 to 2025. Utilizing bibliometric data (Scopus), SQL-based data normalization, and graph theory, the software investigates the intersection of regional geopolitics and scientific cooperation.

The analytical engine is specifically designed to test three core hypotheses:
1. **The Mega-Project Effect (H1):** Assessing whether a country's (e.g., Israel's) regional scientific footprint is localized or merely a byproduct of massive international consorita (e.g., CERN).
2. **Polyadic Political Dynamics (H2):** Measuring the quantitative impact of major geopolitical events—specifically the **Arab Spring (2011)** and the **Abraham Accords (2020)**—on dyadic and multilateral scientific output, testing the theory that "science precedes diplomacy."
3. **Network Topology & Brokerage (H3):** Tracking the shift in regional scientific intermediaries over 25 years using **Betweenness Centrality** (to identify network brokers like Saudi Arabia) and **Eigenvector Centrality** (to measure true structural integration).

---

## System Architecture & Data Pipeline

The project follows a strict ETL (Extract, Transform, Load) and Analysis pipeline to ensure academic reproducibility and data integrity.



1. **Enrichment (`enrich.py`):** Maps raw bibliometric extracts against official Scopus All Science Journal Classification (ASJC) codes to assign accurate subject areas.
2. **Normalization (`database.py`):** Converts flat CSV files into First Normal Form (1NF) and compiles them into a highly optimized, read-only `DuckDB` relational database.
3. **Analytical Engine (`analyzer.py`):** The mathematical core. Executes vectorized SQL queries and calculates temporal graph metrics.
4. **Interface & Visualization (`main.py`):** The user-facing CLI that orchestrates the analysis and generates academic-grade `matplotlib` plots.

---

## Installation & Prerequisites

Ensure you have Python 3.9+ installed. It is recommended to use a virtual environment.

**1. Clone the repository:**
```bash
git clone [https://github.com/eshokhat/scime.git](https://github.com/eshokhat/scime.git)
cd scime
```


## PROJECT STRUCTURE

```
├── raw/                            # Raw Scopus datasets and baseline metrics
│   ├── baseline.csv                # Total global output per country/year
│   ├── full_database_FINAL.csv     # Unprocessed bibliometric export
│   └── scopus_sources.xlsx         # Official Scopus ASJC classification table
├── enrich.py                       # ASJC classification mapping script
├── config.py                       # Global variables, DB schema, and timeframes
├── database.py                     # DuckDB initialization and CSV normalization
├── analyzer.py                     # Mathematical and SQL backend engine
├── main.py                         # CLI interface and plotting module
└── README.md                       # Project documentation
```

**Execution guide**

**Step 1: Data Enrichment (Optional)**
If you already have master.csv, you can skip this step.
Parses raw/full_database_FINAL.csv and cross-references it with raw/scopus_sources.xlsx to map ASJC codes.

**Step 2: Database Initialization**
Reads the enriched data and compiles the database.db DuckDB file. This step normalizes authors, countries, and subject areas.

**Step 3: Run the Analysis**
Executes the main analytical suite. The CLI will prompt you for a target country and comparison countries.



When running main.py, the interactive CLI will guide you:

-Target Country: Enter the primary node you wish to analyze (e.g., israel, egypt).
-Comparison Group: Enter a comma-separated list of countries to test dyadic/polyadic cooperation (e.g., united arab emirates, morocco). Press Enter to skip.

**Expected Outputs**:

1.**Console**: Prints structured data tables showing total vs. strictly regional papers, joint publication timelines, growth rate analytics (Pre/Post 2020), Global Brokers mapping, and historical Centrality scores.

2.**Visualizations**: 
Generates a 3-panel matplotlib figure containing:

-Integration context (Total vs. Regional <= 5 countries)
-Joint output dynamics with historical markers (Arab Spring, Abraham Accords).
-Network centrality evolution.



**Methodology Notes**
Global Brokers Analysis: To prevent "regional blindness," when analyzing a dyad (exactly two countries), the system automatically searches for non-MENA countries (e.g., USA, France) that frequently co-author in that specific intersection, revealing Western funding/umbrella effects.

Algorithm Fallback: If the network adjacency matrix fails to converge for Eigenvector Centrality in highly sparse historical years, the engine automatically falls back to Degree Centrality to prevent runtime crashes.
