Scientometric Analysis of Middle Eastern Scientific Cooperation (2000–2025)

**Project Overview**

This project provides a rigorous, data-driven framework to analyze the evolution of scientific collaboration networks in the Middle East and North Africa (MENA) from 2000 to 2025. Utilizing bibliometric data (Scopus), SQL-based data normalization, and graph theory, the software investigates the intersection of regional geopolitics and scientific cooperation.

The analytical engine tests four core hypotheses:

**The Mega-Project Effect (H1)**: Assessing whether a country's regional scientific footprint is localized or merely a byproduct of massive international consortia (e.g., CERN).

**Polyadic Political Dynamics (H2)**: Measuring the quantitative impact of major geopolitical events (Arab Spring, Abraham Accords) on dyadic scientific output.

**Network Topology & Brokerage (H3)**: Tracking the shift in regional scientific intermediaries over 25 years using Betweenness Centrality and Eigenvector Centrality.

**The Safe Harbor Effect (H4)**: Measuring the "Neutrality Index" to prove that non-normalized cooperation occurs predominantly in politically agnostic STEM fields, bypassing humanities and social sciences.

**System Architecture & Data Pipeline**

The project follows a strict ETL and full-stack architecture to ensure academic reproducibility:

Normalization (database.py): Converts flat CSV files into a highly optimized DuckDB relational database.

Analytical Engine (analyzer.py): The mathematical core. Executes vectorized SQL queries and temporal graph metrics.

Backend API (api.py): A FastAPI server that exposes the analytical engine via REST endpoints.

Interactive Dashboard (frontend/): A React/Vite web application with Recharts for dynamic, real-time data visualization.

Automated Testing (test_api.py): Pytest suite ensuring mathematical sanity and API stability.

**Project Structure**
```
├── raw/                            # Raw Scopus datasets and baseline metrics
├── config.py                       # Global variables, DB schema, and timeframes
├── database.py                     # DuckDB initialization and CSV normalization
├── analyzer.py                     # Mathematical and SQL backend engine
├── api.py                          # FastAPI backend server
├── test_api.py                     # Pytest suite for logical sanity checks
├── README.md                       # Project documentation
└── frontend/                       # Interactive React Dashboard
    ├── src/
    │   ├── App.jsx                 # Main Dashboard component
    │   └── main.jsx                # React entry point
    ├── package.json                # Node.js dependencies
    └── vite.config.js              # Vite configuration
```

Installation & Execution Guide

Ensure you have Python 3.9+ and Node.js installed.

**Step 1: Database Initialization**

Compile the database.db DuckDB file from the raw CSVs.

python database.py

**Step 2: Start the Python Backend (API)**

Start the FastAPI server (runs on http://localhost:8000).

pip install fastapi uvicorn pandas networkx duckdb python-louvain scikit-learn
python api.py


**Step 3: Start the React Frontend (Dashboard)**

Open a new terminal window, navigate to the frontend folder, and start the UI.

cd frontend
npm install
npm run dev

