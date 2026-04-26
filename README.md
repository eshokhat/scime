# Research Engine — MENA Scientific Collaboration Pipeline

> **Mapping Persistent Channels in Israeli Science Bibliometrics, 1990–2025**
>
> A modular, statistically rigorous engine for decomposing fractional collaboration signals
> from Scopus bibliometric data across the Middle East and North Africa (MENA) region.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Scientific Methodology](#2-scientific-methodology)
   - 2.1 [Mathematical Glossary](#21-mathematical-glossary)
   - 2.2 [The 0.8 / 0.2 Weighting Rationale](#22-the-08--02-weighting-rationale)
   - 2.3 [Hypothesis Framework](#23-hypothesis-framework)
3. [Architectural Breakdown](#3-architectural-breakdown)
4. [User Guide](#4-user-guide)
   - 4.1 [Installation](#41-installation)
   - 4.2 [Configuration Reference](#42-configuration-reference)
   - 4.3 [Running the Full Pipeline](#43-running-the-full-pipeline)
   - 4.4 [Selective Execution](#44-selective-execution)
5. [Technical Integrity](#5-technical-integrity)
6. [Output Artefacts](#6-output-artefacts)
7. [Testing](#7-testing)
8. [Interactive Web Dashboard](#8-interactive-web-dashboard)
   - 8.1 [Overview](#81-overview)
   - 8.2 [Stack at a Glance](#82-stack-at-a-glance)
   - 8.3 [Application Architecture](#83-application-architecture)
   - 8.4 [API Reference](#84-api-reference)
   - 8.5 [Logic Flow: Settings Panel → Charts](#85-logic-flow-settings-panel--charts)
   - 8.6 [Metric Definitions for the Dashboard](#86-metric-definitions-for-the-dashboard)
   - 8.7 [Frontend State Management](#87-frontend-state-management)
   - 8.8 [Setup and Launch Guide](#88-setup-and-launch-guide)
   - 8.9 ["Who Calls What" Reference](#89-who-calls-what-reference)

---

## 1. Project Overview

### Core Mission

The Research Engine answers a deceptively simple question: *when two countries appear to collaborate scientifically, how much of that signal is real?*

In bibliometric analysis, co-authorship counts are routinely inflated by **mega-science consortia** — large-scale projects such as CERN experiments, global health initiatives, or climate modelling collaborations — that list hundreds of institutional affiliations across dozens of countries. A paper listing Israel alongside Iran, or Israel alongside Saudi Arabia, may reflect nothing more than joint membership in a 500-author physics consortium, not a persistent, deliberate bilateral relationship.

This engine is designed to separate the **deliberate signal** from the **consortia noise** across 35 years (1990–2025) of MENA regional scientific output, with Israel at the centre of the analysis.

### The Consortia Inflation Problem

Consider a paper with $n_p = 150$ distinct country affiliations. Under naïve whole-counting, every one of the $\binom{150}{2} = 11{,}175$ unique country pairs receives a full integer credit of 1. The Israel–Iran pair receives exactly the same score as the France–Germany pair in an entirely different, genuinely bilateral paper. This creates a systematic overestimation of geopolitically sensitive dyads that would otherwise produce few or no papers independently.

**How this engine solves it:**

1. **Fractional counting** — each paper's collaboration credit is divided across all active dyads, so a 150-author paper contributes $\approx 0.000089$ per dyad rather than 1.
2. **Deliberate Network filter** — a calibrated threshold $N^*$ separates small-group collaborations (deliberate, institutionally driven) from mega-consortia (incidental co-authorship).
3. **Scale weighting** — even within the unrestricted network, papers are graded by a two-tier penalty, applying 0.8 to deliberate papers and 0.2 to consortia papers.
4. **Collapse metric** ($\Delta C$) — a per-dyad, per-year measure of how much apparent affinity *disappears* when consortia are excluded, directly quantifying the inflation effect.

---

## 2. Scientific Methodology

### 2.1 Mathematical Glossary

All formulas below are implemented as pure, stateless functions in `engine/utils.py` and are covered by 100% unit-test coverage in `tests/test_formulas.py`.

---

#### Fractional Collaboration Weight

For a paper with $n_p$ distinct country affiliations, the fractional contribution to each unique country-pair dyad $(i, j)$ is:

$$C^*_{ij,t} = \frac{2}{n_p \cdot (n_p - 1)}$$

**Rationale.** A paper has exactly $\binom{n_p}{2} = \frac{n_p(n_p-1)}{2}$ unique dyads. Each receives an equal share of the paper's total collaboration credit of 1, so each dyad receives $\frac{1}{\binom{n_p}{2}} = \frac{2}{n_p(n_p-1)}$. The sum across all dyads is always exactly 1, regardless of $n_p$.

| $n_p$ | $C^*$ per dyad | Total dyads | Sum |
|------:|---------------:|------------:|----:|
| 2 | 1.000000 | 1 | 1.0 |
| 3 | 0.333333 | 3 | 1.0 |
| 4 | 0.166667 | 6 | 1.0 |
| 8 | 0.035714 | 28 | 1.0 |
| 50 | 0.000816 | 1,225 | 1.0 |

The cumulative fractional $C^*$ for a dyad $(i,j)$ in year $t$ sums over all papers in that year involving both countries:

$$C^*_{ij,t} = \sum_{k \in \mathcal{P}_{ij,t}} \frac{2}{n_p^{(k)} \cdot (n_p^{(k)} - 1)}$$

where $\mathcal{P}_{ij,t}$ is the set of papers in year $t$ that involve both country $i$ and country $j$.

---

#### Salton's Cosine Normalisation

Raw $C^*$ values are not directly comparable across dyads because countries differ vastly in total publication output. The Salton index normalises by the geometric mean of each country's annual baseline production:

$$S_{ij,t} = \frac{C^*_{ij,t}}{\sqrt{P_{i,t} \cdot P_{j,t}}}$$

where $P_{i,t}$ is country $i$'s total publication output in year $t$ (sourced from the `baseline` table). This is equivalent to the cosine similarity of two binary affiliation vectors, providing a size-normalised measure that is robust to the asymmetry between, for example, Israel ($\sim$20,000 papers/year) and Bahrain ($\sim$800 papers/year).

**Guard condition:** $S_{ij,t} = 0$ when $P_{i,t} \leq 0$ or $P_{j,t} \leq 0$.

---

#### Scale Weighting — Deliberate Network Filter

Papers are classified into two tiers based on the calibrated threshold $N^* =$ `DELIBERATE_NP_THRESHOLD`:

$$W_{\text{scale}}(n_p) = \begin{cases} 0.8 & \text{if } n_p \leq N^* \quad \text{(deliberate collaboration)} \\ 0.2 & \text{if } n_p > N^* \quad \text{(mega-science consortia)} \end{cases}$$

Two Salton indices are therefore computed for every dyad-year:

- $S^{\text{unr}}_{ij,t}$ — **Unrestricted Network**: all papers, no size filter.
- $S^{\text{del}}_{ij,t}$ — **Deliberate Network**: only papers with $n_p \leq N^*$.

---

#### Consortia Collapse Metric

The collapse metric $\Delta C$ measures what fraction of a dyad's apparent affinity *vanishes* when mega-consortia are removed:

$$\Delta C_{ij,t} = \frac{S^{\text{unr}}_{ij,t} - S^{\text{del}}_{ij,t}}{S^{\text{unr}}_{ij,t}}$$

**Boundary behaviour:**

| Value | Interpretation |
|:------|:---------------|
| $\Delta C = 0$ | The dyad's affinity is entirely explained by deliberate bilateral collaboration |
| $\Delta C = 1$ | The dyad's apparent affinity is entirely an artefact of mega-consortia; no deliberate signal exists |
| $\Delta C \in (0,1)$ | Mixed signal; consortia account for a $(100 \cdot \Delta C)$% share of apparent affinity |

$\Delta C$ is defined as $0$ when $S^{\text{unr}}_{ij,t} = 0$ (no papers at all), preventing division-by-zero and preserving the interpretability of the metric.

---

#### Thematic Proportional Counting

For Hypothesis 4 (thematic compartmentalisation), each paper's collaboration credit must be allocated across subject categories. Let $n$ be the count of neutral subject fields and $s$ the count of sensitive fields listed for a given paper. Under the `"proportional"` method (the default):

$$W_n = \frac{n}{n + s} \qquad W_s = \frac{s}{n + s}$$

with the guarantee that $W_n + W_s = 1$ for any paper with at least one subject classification. This ensures that the total thematic credit assigned across all category bins equals exactly the paper's fractional collaboration weight.

| Condition | $W_n$ | $W_s$ | Interpretation |
|:----------|------:|------:|:---------------|
| All neutral ($s = 0$) | 1.0 | 0.0 | Fully neutral subject profile |
| All sensitive ($n = 0$) | 0.0 | 1.0 | Fully sensitive subject profile |
| Mixed equal ($n = s$) | 0.5 | 0.5 | Balanced mixed paper |
| $n = 3,\ s = 1$ | 0.75 | 0.25 | Predominantly neutral |
| $n = 1,\ s = 3$ | 0.25 | 0.75 | Predominantly sensitive |

The alternative `"fixed_0.5"` method allocates 0.5 to each category whenever both are present, regardless of field counts. The method is selected via `config.THEMATIC_METHOD`.

---

#### Eigenvector Centrality (H3)

Israel's structural position in the regional network is tracked annually via Eigenvector Centrality, which captures *who you are connected to*, not merely *how many* connections exist:

$$e_i = \frac{1}{\lambda} \sum_{j \in \mathcal{N}(i)} w_{ij} \cdot e_j$$

where $w_{ij} = S^{\text{del}}_{ij,t}$ (the Deliberate Network Salton index serves as the edge weight), $\lambda$ is the dominant eigenvalue of the weighted adjacency matrix, and $\mathcal{N}(i)$ is the set of neighbours of node $i$. Power iteration is used (via NetworkX, `max_iter=1000`), with a numpy eigenvector fallback on convergence failure.

---

### 2.2 The 0.8 / 0.2 Weighting Rationale

The 0.8/0.2 scale split is not arbitrary. It emerges from the **threshold sensitivity analysis** — the first step the pipeline executes on every run.

For each candidate threshold $N \in [2, 25]$, the pipeline computes the total fractional $C^*$ separately for Israel-Involved dyads and for Non-Israel dyads. The resulting curve for Israel-Involved $C^*$ as a function of $N$ has a characteristic elbow: a rapid initial rise followed by a **plateau** of diminishing marginal returns.

The elbow is detected via the Kneedle perpendicular-distance algorithm implemented in `engine/utils.elbow_detection`. It works by:

1. Normalising both the $N$-axis and the $C^*$-axis to $[0, 1]$.
2. Drawing the chord from the first to the last normalised point.
3. Computing the perpendicular distance from every point to that chord.
4. Returning the $N$-value at the point of maximum distance.

The elbow identifies the **stability zone**: the region of $N$ where the ratio $C^*_{\text{Isr}} / C^*_{\text{Non-Isr}}$ becomes approximately constant and no longer sensitive to the threshold choice. This is the scientifically correct operating point because results are reproducible across small variations in the threshold.

The 0.8/0.2 values are calibrated to this stability zone:

- **0.8 (Deliberate tier)** — papers at or below $N^*$ are most likely to reflect institutional relationships rather than incidental consortium membership. They receive the dominant share of the collaboration signal. The high weight ensures that genuinely bilateral papers are not underrepresented relative to their true analytical importance.
- **0.2 (Consortia tier)** — papers above $N^*$ are not discarded entirely; discarding would introduce selection bias by completely removing a category of papers that may include real collaboration in addition to incidental co-authorship. Instead, they are heavily discounted so that three or four global mega-projects cannot dominate the regional network topology.

The exact threshold $N^*$ is updated in-place to `config.DELIBERATE_NP_THRESHOLD` at runtime. The default value of 4 is the prior before calibration; the calibrated value is typically in the range of 3–6 depending on dataset composition.

---

### 2.3 Hypothesis Framework

| Hypothesis | Name | Model | Statistical Test | Dependent Variable |
|:-----------|:-----|:------|:-----------------|:-------------------|
| **H1** | The Mirage | Dyad-level $\Delta C$ distribution | Mann-Whitney U (one-sided) | $\Delta C_{\text{fractured}}$ vs. $\Delta C_{\text{control}}$ |
| **H2a** | Arab Spring Destabilisation | Two-Way Fixed Effects DiD | Wald test on $\hat{\beta}_{\text{destab×post}}$ | $S^{\text{del}}_{ij,t}$ |
| **H2b** | Abraham Accords Normalisation | Multi-Group Fixed Effects DiD | Wald test on $\hat{\beta}_{\text{norm×post}}$ | $S^{\text{del}}_{ij,t}$ |
| **H2c** | Structural Break | Rolling R² scan | Argmax of within-$R^2$ | $S^{\text{del}}_{ij,t}$ |
| **H3** | Topological Peripheralisation | Annual EC time series | Mann-Kendall trend test | Eigenvector Centrality rank |
| **H4** | Thematic Compartmentalisation | 2×2 contingency table | Fisher's Exact Test | Odds ratio (neutral vs. sensitive) |

All panel regressions (H2a, H2b) include entity (dyad) and time (year) fixed effects with standard errors clustered at the dyad level:

$$S^{\text{del}}_{ij,t} = \beta_0 + \sum_k \beta_k \cdot (\text{Group}_k \times \text{Post}_t) + \gamma_{ij} + \tau_t + \varepsilon_{ij,t}$$

---

## 3. Architectural Breakdown

```
research-engine/
│
├── config.py                     ← Single source of truth for all parameters
├── run.py                        ← Pipeline entry point
│
├── engine/                       ← Core analytical modules
│   ├── __init__.py
│   ├── models.py                 ← Typed data structures (dataclasses)
│   ├── utils.py                  ← Mathematical core (pure functions)
│   ├── processor.py              ← Data retrieval and graph analysis
│   ├── orchestrator.py           ← Hypothesis orchestration pipeline
│   ├── reporter.py               ← Output formatting and metadata
│   ├── visuals.py                ← Publication-quality figure generation
│   ├── analyzer.py               ← Backward-compatibility shim
│   └── sensitivity_analyzer.py  ← Weight sensitivity grid search
│
├── pipeline/                     ← Data ingestion layer
│   ├── database.py               ← DatabaseBuilder (normalise CSVs → DuckDB)
│   ├── api.py                    ← Scopus API client
│   └── enrich.py                 ← Metadata enrichment
│
├── data/
│   ├── raw/                      ← Scopus exports and baseline CSVs
│   └── processed/                ← Normalised master tables
│
├── outputs/
│   ├── figures/                  ← All generated plots (PNG)
│   └── tables/                   ← CSV and LaTeX table exports
│
└── tests/                        ← Full pytest test suite (452 tests)
    ├── conftest.py               ← Shared fixtures and in-memory DuckDB
    ├── test_formulas.py          ← 100% coverage of engine/utils.py
    ├── test_analyst.py           ← Logic tests for engine/processor.py
    ├── test_models.py            ← Dataclass type contracts
    ├── test_pipeline.py          ← Integration tests (ResearchPipeline dry run)
    ├── test_analyzer_extended.py
    ├── test_models_hypothesis.py
    ├── test_config.py
    ├── test_reporter.py
    └── test_visuals.py
```

---

### `engine/models.py` — Data Integrity and Type Contracts

This module defines the **typed data contract** for every artefact the pipeline produces. Every major output is represented as a `@dataclass` with strict type annotations, ensuring that downstream consumers can rely on the shape and type of data they receive without defensive runtime checks.

| Dataclass | Purpose | Key Fields |
|:----------|:--------|:-----------|
| `SensitivityRecord` | One row of the threshold calibration sweep | `n_threshold: int`, `israel_involved_c_star: float`, `ratio_isr_non: float`, `growth_isr: float` |
| `DyadAffinityRecord` | Per-year collaboration metrics for a country pair | `year: int`, `p_i: float`, `p_j: float`, `c_star: float`, `affinity_s: float` |
| `CentralityRecord` | Annual network topology snapshot at key study years | `year: int`, `density: float`, `ec: float`, `ec_rank: int`, `bc: float`, `bc_rank: int`, `peers: str` |
| `PipelineConfig` | Immutable experiment parameter snapshot | All tuning parameters from `config.py`; JSON-serialisable |

`PipelineConfig.from_config()` captures a snapshot of the live `config.py` state at instantiation time. `PipelineConfig.to_dict()` returns a JSON-serialisable representation that is embedded in `run_metadata.json`, guaranteeing full reproducibility: any result can be traced back to the exact parameter combination that produced it.

The module also serves as the **backward-compatibility gateway**: `engine.models.ScientificWorkflow` is re-exported from `engine.orchestrator.ResearchPipeline` via `__getattr__`, so existing code referencing the old class name continues to work without modification.

---

### `engine/utils.py` — The Mathematical Core

This module is the **sole location** for all quantitative formulas. Every function is a pure, stateless mapping from inputs to outputs — no database access, no side effects, no global state. This architectural choice serves two purposes:

1. **Testability** — mathematical accuracy is verifiable with deterministic unit tests that run in under two milliseconds with no infrastructure dependencies.
2. **Reusability** — the same `fractional_weight` function is invoked identically from DuckDB SQL (via inline constant expansion), from NumPy-level operations in the orchestrator, and from standalone sensitivity scripts.

| Function | Formula | Guard |
|:---------|:--------|:------|
| `fractional_weight(n_p)` | $\frac{2}{n_p(n_p-1)}$ | Returns `0.0` for $n_p < 2$ |
| `salton_index(c_star, p_i, p_j)` | $\frac{C^*}{\sqrt{P_i P_j}}$ | Returns `0.0` if $P_i \leq 0$ or $P_j \leq 0$ |
| `delta_c_metric(s_unr, s_del)` | $\frac{S_\text{unr} - S_\text{del}}{S_\text{unr}}$ | Returns `0.0` if $S_\text{unr} \leq 0$ |
| `elbow_detection(x_vals, y_vals)` | Kneedle perpendicular-distance | Handles flat curves, single-point inputs |
| `is_israel_dyad(c_i, c_j)` | Membership test | — |
| `is_fractured_dyad(c_i, c_j, normalized_states)` | H1 dyad classification | — |
| `classify_dyad_h2a(c_i, c_j, destabilized_states)` | H2a DiD group assignment | Priority: destabilized > israel > stable_control |
| `classify_dyad_h2b(c_i, c_j, normalization_set)` | H2b DiD group assignment | Returns: norm / nonnorm / reference |

---

### `engine/processor.py` — The Analytical Engine

This module translates the mathematical framework into database queries and graph-theoretic computations through two classes.

#### `NetworkAnalyst`

The primary interface between the DuckDB database and the analytical pipeline. It manages a read-only connection, a 20-country MENA list, and a **per-threshold affinity cache** that prevents redundant recomputation when the same threshold is queried multiple times within a single run.

Key design decisions:

- **Read-only connection** — the analyst never writes to the database, preventing accidental modification of the source data.
- **Cache invalidation on threshold change** — `_affinity_cache` is keyed on the integer value of `DELIBERATE_NP_THRESHOLD`. When calibration updates the threshold, `clear_affinity_cache()` is called automatically so all subsequent queries use the calibrated value.
- **Context manager support** — `with NetworkAnalyst() as analyst:` guarantees connection release even if an exception occurs mid-analysis.

| Method | Returns | Description |
|:-------|:--------|:------------|
| `get_basic_metrics()` | `Dict[str, int]` | Total paper count from the articles table |
| `fetch_sensitivity_stats(n)` | `DataFrame` | $C^*$ totals per group for threshold calibration |
| `fetch_country_timeseries(country, mode)` | `DataFrame` | Annual production (`raw` count or `fractional` $1/n_p$ weight) |
| `calculate_dyad_affinity(a, b, max_countries)` | `DataFrame` | $C^*$ and $S$ for a specific dyad across all years |
| `fetch_regional_affinity_data()` | `DataFrame` | Full MENA dyad×year table with $S^{\text{unr}}$, $S^{\text{del}}$, $\Delta C$ |
| `format_did_panel_data()` | `DataFrame` | Panel dataset for H2a with H2a group labels, DiD interaction terms |
| `prepare_h2b_dataset()` | `DataFrame` | Panel dataset for H2b with H2b group labels, DiD interaction terms |
| `compute_network_centrality(year)` | `Dict[str, float]` | Eigenvector Centrality for the Deliberate Network in a given year |
| `get_thematic_contingency_table()` | `DataFrame` | 2×2 contingency table for H4 (Fisher's Exact Test) |

#### `ThematicAnalyst`

A focused sub-engine responsible solely for constructing the H4 contingency table. Deliberately separated from `NetworkAnalyst` so that subject-classification logic is independently testable and modifiable without touching network analysis code.

---

### `engine/orchestrator.py` — The Research Pipeline

`ResearchPipeline` is the top-level coordinator. It owns one `NetworkAnalyst` instance, one `ScientificVisualizer` instance, and an optional `Reporter`. Its role is to invoke analytical methods in the correct sequence, pass results to the visualiser and reporter, and print structured progress output to the console.

```
ResearchPipeline
│
├── run_threshold_sensitivity_test()    → Calibrate N*; update config in-place
├── execute_step1_normalization()       → Compute S_unr and S_del per dyad
│
├── evaluate_h1_mirage()                → Mann-Whitney U test
├── evaluate_h2a_destabilization()      → Two-Way FE DiD (Arab Spring)
├── evaluate_h2b_normalization()        → Multi-Group FE DiD (Abraham Accords)
├── evaluate_h2c_break_detection()      → Rolling R² structural break scan
├── evaluate_h3_topology()              → Eigenvector Centrality + Mann-Kendall
└── evaluate_h4_thematic_bias()         → Fisher's Exact Test with odds ratio
```

The `analyzer` property is a backward-compatibility alias: `pipeline.analyzer` and `pipeline.analyst` refer to the same `NetworkAnalyst` instance.

---

### `engine/reporter.py` — Metadata and Scientific Reproducibility

The `Reporter` class is the pipeline's **scientific audit trail**. Every numerical result printed to the console is simultaneously archived in a structured, citation-ready format.

| Method | Output |
|:-------|:-------|
| `section(title)` | Console section header with `=` separator bars |
| `subsection(title)` | Console subsection header with `-` separator |
| `stat_line(label, value, p_value)` | Console statistic with p-value and APA significance stars |
| `table(df, label, caption)` | CSV + LaTeX saved to `outputs/tables/` |
| `contingency_table(df, OR, p, ci_low, ci_high)` | Formatted 2×2 table with odds ratio and 95% confidence interval |
| `save_run_metadata(extra)` | `outputs/run_metadata.json` with full reproducibility record |

Significance stars follow the APA convention:

| Stars | Threshold |
|:------|:----------|
| `***` | $p < 0.001$ |
| `**` | $p < 0.01$ |
| `*` | $p < 0.05$ |
| _(none)_ | $p \geq 0.05$ |

The `run_metadata.json` file is the **primary reproducibility artefact**, containing:

- UTC timestamp of the run
- Python version and platform
- Library versions (`pandas`, `duckdb`, `networkx`, `scipy`, etc.)
- All experiment parameters from `PipelineConfig.to_dict()` (threshold, weights, year range, thematic method)
- Any additional key-value pairs passed via the `extra` argument (e.g. total paper count, calibrated $N^*$, number of active dyads)

---

## 4. User Guide

### 4.1 Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone <repository-url>
cd research-engine

# Install all dependencies including test dependencies
uv sync

# Alternatively, with pip
pip install -e ".[dev]"
```

**Core runtime dependencies:**

| Package | Version | Purpose |
|:--------|:--------|:--------|
| `duckdb` | ≥ 1.5.2 | Analytical SQL engine for bibliometric queries |
| `pandas` | ≥ 3.0.2 | DataFrame operations and panel data construction |
| `networkx` | ≥ 3.6.1 | Graph construction, centrality, community detection |
| `linearmodels` | ≥ 7.0 | Panel OLS with two-way fixed effects (H2a, H2b) |
| `scipy` | ≥ 1.17.1 | Fisher's exact test, Mann-Whitney U (H1, H4) |
| `pymannkendall` | ≥ 1.4.3 | Mann-Kendall trend test (H3) |
| `statsmodels` | ≥ 0.14.4 | `add_constant`, supplementary regression utilities |
| `matplotlib` / `seaborn` | latest | Publication-quality figure generation |
| `pyvis` | ≥ 0.3.2 | Interactive network visualisation |

---

### 4.2 Configuration Reference

All experiment parameters are centralised in `config.py`. **No other source file needs to be edited** to change analytical parameters; every downstream module reads from `config` at call time, so changes propagate automatically.

#### Core Threshold

```python
# config.py

DELIBERATE_NP_THRESHOLD: int = 4   # prior value; updated at runtime by calibration
DELIBERATE_N: int = DELIBERATE_NP_THRESHOLD  # backward-compat alias; kept in sync
```

This is the prior value used before calibration. The pipeline's first step replaces it with an empirically determined value via elbow detection. To run at a fixed threshold without calibration, set this to your desired value and call hypothesis methods directly.

#### Date Range

```python
START_YEAR: int = 1990
END_YEAR:   int = 2025
```

All queries respect these bounds. To narrow the analysis window (e.g., a post-Oslo focus), set `START_YEAR = 2000`.

#### Collaboration Weights

```python
WEIGHTS = {
    "SCALE": {
        "small": 0.8,   # n_p ≤ DELIBERATE_NP_THRESHOLD  (deliberate tier)
        "cons":  0.2,   # n_p >  DELIBERATE_NP_THRESHOLD  (consortia tier)
    },
    "SCOPE": {
        "domestic": 1.0,   # single-country papers (identity multiplier)
        "intl":     0.7,   # multi-country papers (consortium discount)
    },
    "THEMATIC": {
        "method": "proportional",   # or "fixed_0.5" for H4
    }
}
```

| Parameter | Default | Effect | Recommended Range |
|:----------|:-------:|:-------|:------------------|
| `WEIGHTS["SCALE"]["small"]` | 0.8 | Up-weight on deliberate-tier papers | 0.7 – 0.9 |
| `WEIGHTS["SCALE"]["cons"]` | 0.2 | Down-weight on consortia papers | 0.1 – 0.3 |
| `WEIGHTS["SCOPE"]["intl"]` | 0.7 | International scope discount | 0.5 – 1.0 |
| `THEMATIC_METHOD` | `"proportional"` | Fractional counting rule for H4 | `"proportional"` or `"fixed_0.5"` |

> **Note:** `scale_small` and `scale_cons` are independent multipliers, not a probability distribution. However, keeping their sum equal to 1.0 preserves the intuitive interpretation that the two tiers together account for the full collaboration weight.

#### Geopolitical Event Markers

```python
GEOPOLITICAL_MARKERS = {
    "OSLO_ACCORDS":        1993,
    "ISRAEL_JORDAN_PEACE": 1994,
    "SECOND_INTIFADA":     2000,
    "ARAB_SPRING":         2011,
    "ABRAHAM_ACCORDS":     2020,
}
```

Used to annotate figures and define pre/post event periods in the DiD regressions. Add or modify events here to test alternative periodisations without touching analytical code.

#### Country and Subject Classification

```python
COUNTRIES_LIST: List[str]   # 20 MENA countries (all lowercase)
NEUTRAL_FIELDS: List[str]   # STEM + clinical medicine subject areas
```

`COUNTRIES_LIST` defines the scope of the regional network. `NEUTRAL_FIELDS` defines what counts as a neutral subject for H4; any Scopus subject area not in this list is implicitly treated as sensitive.

**Current neutral fields:**

```
medicine  |  physics and astronomy  |  engineering  |  chemistry  |  mathematics
```

---

### 4.3 Running the Full Pipeline

Ensure the DuckDB database is populated (via `pipeline/database.py`) before running the analysis.

```bash
# Full pipeline — all six hypotheses
python run.py
```

The pipeline executes in the following fixed order:

```
Step 0:  Calibration
         run_threshold_sensitivity_test(min_n=2, max_n=7)
         → Detects elbow N*; updates config.DELIBERATE_NP_THRESHOLD
         → Output: outputs/tables/threshold_sensitivity.csv

Step 1:  Affinity Normalisation
         execute_step1_normalization() for five case-study dyads:
           israel–morocco | israel–uae | israel–egypt |
           israel–jordan  | israel–bahrain
         → Output: outputs/figures/affinity_trends_*.png

H1:      The Mirage
         evaluate_h1_mirage()
         → Mann-Whitney U test on ΔC distributions
         → Output: h1_mann_whitney.csv | h1_mirage_*.png

H2a:     Arab Spring DiD
         evaluate_h2a_destabilization()
         → Two-way FE panel regression
         → Output: h2a_regression.csv | h2a_did_comparison.png

H2b:     Abraham Accords DiD
         evaluate_h2b_normalization()
         → Multi-group FE panel regression
         → Output: h2b_regression.csv | h2b_did_comparison.png

H2c:     Structural Break
         evaluate_h2c_break_detection() × 2 (full region + Israel-Arab subset)
         → Rolling R² scan; segmented regression
         → Output: break_search_*.png | break_fit_*.png

H3:      Network Topology
         evaluate_h3_topology("israel")
         → Annual EC and BC; Mann-Kendall trend test
         → Output: h3_centrality_keyYears.csv | h3_mann_kendall.csv

H4:      Thematic Bias
         evaluate_h4_thematic_bias()
         → Fisher's exact test; odds ratio with 95% CI
         → Output: h4_fisher_exact.csv | h4_thematic_*.png

Final:   Metadata
         reporter.save_run_metadata()
         → Output: outputs/run_metadata.json
```

---

### 4.4 Selective Execution

To run individual hypotheses without the full pipeline, instantiate `ResearchPipeline` directly:

```python
from engine.orchestrator import ResearchPipeline
from engine.reporter import Reporter

reporter = Reporter()
pipeline = ResearchPipeline(reporter=reporter)

# Calibrate threshold first (required before any deliberate-network query)
_, optimal_n = pipeline.run_threshold_sensitivity_test(min_n=2, max_n=7)

# Run only the hypotheses you need
pipeline.evaluate_h1_mirage()
pipeline.evaluate_h3_topology(target_country="israel")
pipeline.evaluate_h4_thematic_bias()

# Always save the reproducibility record at the end
reporter.save_run_metadata({"deliberate_n": optimal_n})
```

To query the database directly without running hypotheses:

```python
from engine.processor import NetworkAnalyst
import config

with NetworkAnalyst() as analyst:
    # Unrestricted affinity for a specific dyad across all years
    df_unr = analyst.calculate_dyad_affinity("israel", "egypt")

    # Deliberate Network only (applies the N* filter)
    df_del = analyst.calculate_dyad_affinity(
        "israel", "egypt",
        max_countries=config.DELIBERATE_NP_THRESHOLD
    )

    # Full MENA regional table with S_unr, S_del, and ΔC
    regional = analyst.fetch_regional_affinity_data()
    print(regional[regional["delta_c"] > 0.5])  # high consortia-inflation dyads
```

---

## 5. Technical Integrity

### Defensive Programming

Every public method in `NetworkAnalyst` and `ResearchPipeline` follows a consistent exception-handling pattern:

```python
try:
    result = self.conn.sql(query).df()
    return result
except Exception as exc:
    logger.error("method_name(args) failed: %s", exc)
    raise
```

Specific defence mechanisms:

- **Division-by-zero guards** — `salton_index`, `delta_c_metric`, and all SQL-level computations guard against zero denominators explicitly. No floating-point exception can propagate from the mathematical core to the analytical layer.
- **Empty-graph handling** — `compute_network_centrality` returns `{}` for years with no Deliberate Network edges, rather than passing an empty graph to `nx.eigenvector_centrality` and raising `numpy.linalg.LinAlgError`.
- **Convergence failure recovery** — `nx.PowerIterationFailedConvergence` is caught at the call site and logged; the method returns `{}` rather than crashing the topology loop. A numpy eigenvector fallback is attempted first.
- **Cache key safety** — `_affinity_cache` is keyed on the *integer value* of `DELIBERATE_NP_THRESHOLD` at call time, not a reference. Runtime mutations to the config value automatically produce a new cache key, so stale results are never served.
- **Read-only database** — `NetworkAnalyst` opens DuckDB with `read_only=True`. No accidental write to the source data is possible regardless of what SQL is executed.

### Logging

All modules use Python's standard `logging` library with module-level loggers (`logger = logging.getLogger(__name__)`).

| Level | Events |
|:------|:-------|
| `DEBUG` | Connection open, cache key resolution |
| `INFO` | Pipeline initialisation, threshold calibration result, file save events |
| `ERROR` | Database connection failures, query execution failures, caught exceptions |

To enable full logging output at runtime:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s — %(levelname)s — %(message)s"
)
```

### Type Safety

Type integrity is maintained at three independent levels:

1. **Static** — full type hints on all function and method signatures throughout the engine. Compatible with `mypy --strict`.
2. **Runtime contracts** — `@dataclass` definitions in `models.py` enforce field types at instantiation; there is no silent coercion between incompatible types.
3. **Test-time** — `tests/test_models.py` contains explicit `isinstance` assertions for every field of every dataclass, confirming that the pipeline's outputs always conform to their declared contracts regardless of the underlying SQL results.

---

## 6. Output Artefacts

All outputs are written to the `outputs/` directory, which is created automatically on `import config` (no manual setup required).

```
outputs/
├── run_metadata.json                     ← Full reproducibility record
│
├── figures/
│   ├── threshold_sensitivity.png         ← C* vs N elbow detection curve
│   ├── affinity_trends_israel_*.png      ← S_unr and S_del trends per dyad
│   ├── h1_mirage_distribution.png        ← ΔC distributions (fractured vs control)
│   ├── h1_mirage_delta_c.png             ← Time-series of ΔC
│   ├── h2a_did_comparison.png            ← Arab Spring pre/post S_del trends
│   ├── h2b_did_comparison.png            ← Abraham Accords pre/post S_del trends
│   ├── h2c_break_search_*.png            ← Rolling R² scan curve
│   ├── h2c_break_fit_*.png               ← Segmented regression fit at break year
│   ├── h3_centrality_comparison.png      ← EC and BC time series for target country
│   ├── h3_network_topology_*.png         ← Network graph at key study years
│   └── h4_thematic_bias.png             ← Grouped bar chart (neutral vs sensitive)
│
└── tables/
    ├── threshold_sensitivity.csv / .tex  ← N × C* calibration table
    ├── h1_mann_whitney.csv / .tex        ← Mann-Whitney U results
    ├── h2a_regression.csv / .tex         ← H2a panel regression coefficients
    ├── h2b_regression.csv / .tex         ← H2b panel regression coefficients
    ├── h3_centrality_keyYears.csv / .tex ← EC/BC at key geopolitical years
    ├── h3_mann_kendall.csv / .tex        ← Mann-Kendall test results
    └── h4_fisher_exact.csv / .tex        ← Contingency table + Fisher results
```

Every table is saved in both CSV (for downstream processing and replication) and LaTeX (for direct inclusion in academic manuscripts). Float values in LaTeX output are formatted to four decimal places.

---

## 7. Testing

The test suite uses `pytest` and covers all five layers of the engine independently.

```bash
# Run the full test suite
python -m pytest tests/

# Run with coverage report for the engine module
python -m pytest tests/ --cov=engine --cov-report=term-missing

# Run only the mathematical formula tests (fastest; no I/O)
python -m pytest tests/test_formulas.py -v

# Run only integration tests
python -m pytest tests/test_pipeline.py -v -k "ResearchPipeline"

# Run a specific hypothesis test class
python -m pytest tests/test_models_hypothesis.py::TestH4ThematicBias -v
```

### Test Architecture

| File | Layer | Description |
|:-----|:------|:------------|
| `conftest.py` | Infrastructure | In-memory DuckDB (5-paper synthetic dataset); `NetworkAnalyst` fixture; `ResearchPipeline` factory |
| `test_formulas.py` | `engine/utils.py` | 100% formula coverage; pure-function tests, no I/O, sub-millisecond execution |
| `test_analyst.py` | `engine/processor.py` | Config reads, threshold gating, affinity cache, EC on weighted graphs |
| `test_models.py` | `engine/models.py` | Dataclass field types; `PipelineConfig.from_config()` and `to_dict()` |
| `test_pipeline.py` | `engine/orchestrator.py` | Dry-run integration: Load → Process → Export; `run_metadata.json` creation |
| `test_analyzer_extended.py` | `engine/processor.py` | Extended method coverage (timeseries, DiD panel prep, contingency table branches) |
| `test_models_hypothesis.py` | `engine/orchestrator.py` | Hypothesis-level tests for all six `evaluate_*` methods |
| `test_reporter.py` | `engine/reporter.py` | File creation, LaTeX content, metadata JSON structure and keys |
| `test_visuals.py` | `engine/visuals.py` | Smoke tests: every plot method produces a non-empty output file |
| `test_config.py` | `config.py` | Type and value validation for all configuration constants |

### Synthetic Test Dataset

The shared in-memory DuckDB fixture is populated with five papers whose ground-truth values are analytically derived:

| EID | Countries | Year | $n_p$ | $C^*$ per dyad |
|:----|:----------|-----:|------:|---------------:|
| eid1 | israel–egypt | 2015 | 2 | 1.000000 |
| eid2 | israel–morocco | 2020 | 2 | 1.000000 |
| eid3 | egypt–jordan | 2015 | 2 | 1.000000 |
| eid4 | israel–egypt–morocco | 2021 | 3 | 0.333333 |
| eid5 | 8-country mega-project | 2015 | 8 | 0.035714 |

Baseline publication output: israel = 5,000 per year; all other countries = 1,000 per year (1990–2025). This gives an analytically exact Salton denominator of $\sqrt{5{,}000 \times 1{,}000} \approx 2236.07$ for all Israel–other dyads.

### Key Design Principles

- **Stateless** — every test function is independent; no shared mutable state between tests within or across modules.
- **In-memory database** — all database tests use a module-scoped DuckDB `:memory:` connection, so tests are isolated from any on-disk database state and run in under 10 seconds for the entire suite.
- **Isolated destructive operations** — tests that call `close()` or use context managers create their own fresh DuckDB connections rather than using the shared module fixture, preventing connection-poisoning across tests.
- **Mocked visualiser** — `ScientificVisualizer` is replaced with a `MagicMock` in all non-visual tests, so hypothesis tests run without any file I/O.
- **Config restoration** — an `autouse` fixture restores `config.DELIBERATE_NP_THRESHOLD` and `config.DELIBERATE_N` after every test, preventing calibration side-effects from leaking into subsequent tests.

---

---

## 8. Interactive Web Dashboard

### 8.1 Overview

The interactive dashboard is a browser-based companion to the offline pipeline. It lets researchers explore the four hypothesis visualisations for any MENA dyad in real time, adjust the core model parameters with sliders, and observe how the charts respond — without modifying `config.py` or re-running the pipeline.

The dashboard is divided into two independent processes that communicate over HTTP:

| Process | Directory | Entry point | Default port |
|:--------|:----------|:------------|:-------------|
| **Backend** — FastAPI REST API | project root | `api.py` | `8000` |
| **Frontend** — Vite + React SPA | `frontend/` | `frontend/src/App.jsx` | `5173` |

Both processes must be running simultaneously during development. The frontend proxies all `/api/*` requests to the backend, so a single `fetch('/api/metrics?…')` call in the browser code reaches FastAPI without any CORS configuration needed in development.

---

### 8.2 Stack at a Glance

```
┌─────────────────────────────────────────────────────┐
│  Browser (localhost:5173)                           │
│                                                     │
│  React 19  ·  Recharts  ·  TailwindCSS v4          │
│  lucide-react icons  ·  Vite dev server             │
└──────────────┬──────────────────────────────────────┘
               │  HTTP GET /api/config
               │  HTTP GET /api/metrics?…
               ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI  (localhost:8000)                          │
│                                                     │
│  api.py                                             │
│  ├─ GET /api/config   → reads config.py defaults   │
│  └─ GET /api/metrics  → executes DuckDB SQL        │
│                          + NetworkX graph math      │
└──────────────┬──────────────────────────────────────┘
               │  duckdb.connect(DB_PATH, read_only=True)
               ▼
┌─────────────────────────────────────────────────────┐
│  database.db  (DuckDB embedded file)                │
│                                                     │
│  Tables: articles · countries · subjects · baseline │
└─────────────────────────────────────────────────────┘
               ▲
               │  read-only; never mutated by the API
```

---

### 8.3 Application Architecture

#### Backend — `api.py`

`api.py` is a stateless FastAPI application. It reads `config.py` once at import time to derive module-level constants (`_VALID_COUNTRIES`, `_ACCORDS_YEAR`, `_NEUTRAL_PATTERN`), but it **never mutates `config.py`** at runtime. Every request that carries parameter overrides resolves them locally inside the request handler and discards them when the response is sent.

The key architectural decision is that all per-request overrides are passed down the call stack as explicit function arguments, never written back to the module:

```
GET /api/metrics?np_threshold=5&w_small=0.9&w_cons=0.1
          │
          ▼
get_metrics()
  threshold  = 5      ← from query param (overrides config.DELIBERATE_N=4)
  weight_small = 0.9  ← from query param
  weight_cons  = 0.1  ← from query param
          │
          ▼
_build_dataset(conn, target, compare, threshold=5, w_small=0.9, w_cons=0.1)
          │
          ├─ _h1_sql(target, threshold=5)
          ├─ _h2_joint_sql(target, compare)
          ├─ _h2_brokers_sql(target, compare)
          ├─ _h3_all_years_sql(threshold=5, w_small=0.9, w_cons=0.1)
          └─ _h4_yearly_sql(target, compare)
```

This means the server is **thread-safe by design**: two simultaneous requests with different parameters never interfere with each other, and the default configuration is never silently overwritten by a user's slider adjustment.

#### SQL Builders

Each SQL builder is a pure Python function that returns a parameterised SQL string. No query is constructed outside these builders; there are no inline `conn.execute(f"…")` calls elsewhere in the file.

| Builder | Parameters | Returns |
|:--------|:-----------|:--------|
| `_h1_sql(target, threshold)` | Country name, nₚ cutoff | Annual total and regional paper counts for the target |
| `_h2_joint_sql(target, compare)` | Two country names | Annual joint paper count for the dyad |
| `_h2_brokers_sql(target, compare)` | Two country names | Top-3 broker countries per year |
| `_h3_all_years_sql(threshold, w_small, w_cons)` | nₚ cutoff, two weights | Salton-normalised weighted edge list for every year |
| `_h4_yearly_sql(target, compare)` | Two country names | Annual neutral vs. other paper counts |
| `_global_brokers_sql(target, compare)` | Two country names | All-time broker totals with percentage share |
| `_summary_sql(target, compare)` | Two country names | Pre/post Abraham Accords paper counts |
| `_h4_subjects_sql(target, compare)` | Two country names | Top-5 subject areas |
| `_h4_neutral_ratio_sql(target, compare)` | Two country names | Overall neutral STEM paper percentage |

#### H3: Network Centrality

After the H3 SQL query returns a full-range weighted edge list (all MENA dyads, all years, Salton-normalised), `_compute_h3()` rebuilds a `networkx.Graph` per calendar year and computes two centrality measures:

1. **Betweenness centrality** — `nx.betweenness_centrality(G, weight="weight", normalized=True)` — the top-scoring node for that year becomes `h3_broker_name` / `h3_broker_score`.
2. **Eigenvector centrality** — `nx.eigenvector_centrality(G, weight="weight", max_iter=1000)` — the score of the `target` country becomes `h3_target`. A numpy eigenvector fallback is attempted on `PowerIterationFailedConvergence`.

The result is merged back into the year-keyed `data` dict inside `_build_dataset`.

#### Frontend — `frontend/src/App.jsx`

`App.jsx` is the entire frontend. It is a single React component (~950 lines) that owns all application state, performs all data fetching, and renders all four hypothesis tabs. There are no sub-components, no routing, and no global state library.

---

### 8.4 API Reference

#### `GET /api/config`

Returns the current `config.py` defaults so the frontend can initialise sliders to the values the backend actually uses.

**Response**
```json
{
  "np_threshold": 4,
  "w_small": 0.8,
  "w_cons": 0.2,
  "w_intl": 0.7,
  "start_year": 1990,
  "end_year": 2025,
  "geopolitical_markers": {
    "oslo_accords": 1993,
    "israel_jordan_peace": 1994,
    "second_intifada": 2000,
    "arab_spring": 2011,
    "abraham_accords": 2020
  }
}
```

This endpoint never changes; it reflects the constants baked into `config.py` at server start time.

---

#### `GET /api/metrics`

The primary data endpoint. Returns all chart data for the selected dyad.

**Query parameters**

| Parameter | Type | Required | Default | Constraint | Description |
|:----------|:-----|:--------:|:-------:|:----------:|:------------|
| `target` | string | yes | — | valid MENA country | Target country (lowercase) |
| `compare` | string | yes | — | valid MENA country ≠ target | Comparison country |
| `np_threshold` | integer | no | `config.DELIBERATE_N` | 2 ≤ n ≤ 8 | Deliberate-network cutoff nₚ |
| `w_small` | float | no | `config.WEIGHTS["SCALE"]["small"]` | 0.05 ≤ w ≤ 1.0 | Fractional C* weight for deliberate papers |
| `w_cons` | float | no | `config.WEIGHTS["SCALE"]["cons"]` | 0.0 ≤ w ≤ 0.5 | Fractional C* weight for consortium papers |

**Response shape**
```json
{
  "dataset": [
    {
      "year": 1990,
      "h1_total": 450, "h1_reg": 210,
      "h2_joint": 3,   "h2_yearly_brokers": [{"name": "germany", "papers": 2}],
      "h3_broker_name": "turkey", "h3_broker_score": 0.4123, "h3_target": 0.0312,
      "h4_neutral": 2, "h4_other": 1
    }
  ],
  "globalBrokers": [{"name": "usa", "papers": 145, "percent": 23.4}],
  "summary": {"pre": 45, "post": 189, "growth": 320.0},
  "h4_subjects": [{"subject": "Medicine", "papers": 58}],
  "h4_neutral_ratio": 71.3,
  "params": {"np_threshold": 4, "w_small": 0.8, "w_cons": 0.2}
}
```

The `params` field echoes back the resolved parameter values (after applying defaults), so the frontend can display which values are currently active.

---

### 8.5 Logic Flow: Settings Panel → Charts

The flow below traces exactly what happens when a researcher moves the **nₚ threshold slider** from 4 to 6 and clicks "Apply & Recalculate".

```
1. SLIDER MOVE (no API call yet)
   ─────────────────────────────
   User drags npThreshold slider: 4 → 6
   setDraft(d => ({ ...d, npThreshold: 6 }))
   draft = { npThreshold: 6, wSmall: 0.8, wCons: 0.2, wIntl: 0.7 }
   appliedSettings = { npThreshold: 4, ... }  ← unchanged

   isDirty = (JSON.stringify(draft) !== JSON.stringify(appliedSettings))
           = true
   → amber dot appears on the "Parameters" button
   → "Apply & Recalculate" button becomes active


2. APPLY (API call triggered)
   ──────────────────────────
   User clicks "Apply & Recalculate"
   setAppliedSettings({ ...draft })
   appliedSettings = { npThreshold: 6, wSmall: 0.8, wCons: 0.2, wIntl: 0.7 }

   useEffect dependency [targetCountry, compareCountry, appliedSettings] fires
   → fetchData() is called


3. FETCH
   ──────
   fetch('/api/metrics?target=israel&compare=united arab emirates
         &np_threshold=6&w_small=0.8&w_cons=0.2')

   Vite dev-server proxy forwards to:
   http://localhost:8000/api/metrics?…


4. BACKEND RESOLUTION
   ───────────────────
   get_metrics() receives np_threshold=6 (not None)
   threshold = 6  ← override wins; config.DELIBERATE_N=4 is ignored

   _h1_sql("israel", threshold=6)
     → COUNT CASE WHEN np <= 6   ← wider regional category
   _h3_all_years_sql(threshold=6, w_small=0.8, w_cons=0.2)
     → CASE WHEN np <= 6 THEN 0.800000 ELSE 0.200000
     → includes all papers with np > 1 (HAVING np > 1)

   Salton-normalised edge list rebuilt → NetworkX graphs per year
   Eigenvector + Betweenness centrality recomputed


5. RESPONSE → STATE UPDATE
   ─────────────────────────
   setDataset(data.dataset)          → H1 AreaChart re-renders
   setGlobalBrokers(data.globalBrokers) → H2 broker bars re-render
   setSummary(data.summary)          → H2 pre/post stats update
   setSubjects(data.h4_subjects)     → H4 subject bars re-render
   setNeutralRatio(data.h4_neutral_ratio)
   isLoading = false


6. DYNAMIC LABELS
   ────────────────
   H1 legend: `Strictly regional (nₚ ≤ ${appliedSettings.npThreshold})`
            = "Strictly regional (nₚ ≤ 6)"
   H1 description: `…projects (nₚ ≤ 6) in total publication volume.`
```

The `w_intl` slider in the Settings panel is disabled (grayed out with a "pipeline only" badge). It is displayed for transparency — so researchers understand the full parameter space — but it controls a weight applied during the **offline Salton normalisation** step in `engine/processor.py`, not during any API query. Changes to it require re-running the full pipeline.

---

### 8.6 Metric Definitions for the Dashboard

#### H1 — Regional Integration

The **H1 chart** plots two series for the selected target country:

- **All publications (Total)** — every paper that lists the country as an affiliation in the given year.
- **Strictly regional (nₚ ≤ N)** — a subset of those papers where the total count of distinct country affiliations is at most N (the deliberate-network threshold). These papers are far more likely to represent intentional bilateral or small-group collaborations rather than incidental co-authorship in a mega-consortium.

The **threshold N** is the same value exposed by the nₚ slider in the Settings panel. Increasing N (e.g. from 4 to 6) admits more papers into the regional category and raises the blue area; decreasing it tightens the definition of deliberate collaboration and lowers it. The ratio of the two series is the first visual signal of whether a country's international activity is dominated by small partnerships or mega-science membership.

#### H2 — Dyadic Co-authorship Dynamics

The **H2 tab** shows the annual count of papers jointly authored by both selected countries. Reference lines mark the **Arab Spring (2011)** and the **Abraham Accords (2020)** — two geopolitical events hypothesised to have disrupted (2011) and then normalised (2020) scientific ties between Israel and Arab states.

The **broker panel** (right column and stacked bar chart) lists third-party countries that appear in the dyad's joint papers — countries through which bilateral contact may be channelled when direct collaboration is politically constrained.

The **summary statistics** at the bottom of the tab report total papers pre-/post-Abraham Accords and the percentage change between the two periods, computed in `_summary_sql`.

#### H3 — Network Topology: Betweenness and Eigenvector Centrality

The H3 chart tracks two centrality measures on the same axes for every year in the study window. Both are computed from the **Deliberate Network**: the Salton-normalised weighted graph built from papers with at most nₚ ≤ N distinct country affiliations.

---

##### Betweenness Centrality (left axis, 0–1)

**Definition.** For a country $v$ in the regional collaboration network, normalised betweenness centrality is:

$$BC(v) = \frac{2}{(n-1)(n-2)} \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}$$

where $\sigma_{st}$ is the total number of shortest paths from country $s$ to country $t$, $\sigma_{st}(v)$ is the number of those paths that pass through $v$, and $n$ is the number of nodes.

**What it measures.** Betweenness centrality captures a country's role as a *structural bridge* — the extent to which it sits on the paths that connect otherwise disparate parts of the network. In this context, a high betweenness score means other countries must pass through (collaborate via) this country to reach the rest of the region.

**Interpreting the dashboard.**

| Pattern | Interpretation |
|:--------|:---------------|
| **One country with rising BC, all others near zero** | *Centralisation* — hub-and-spoke topology. Scientific collaboration funnels through a single regional hub. The network is fragile: removing that hub disconnects large subgraphs. |
| **Multiple countries sharing moderate BC, values roughly equal** | *Multipolarity* — distributed bridge structure. Several countries independently mediate regional ties. Collaboration channels are redundant and resilient. |
| **Post-event sharp drop in top-BC country** | A geopolitical shock (e.g. Arab Spring) has broken the dominant brokerage path; collaboration is being re-routed or has collapsed. |
| **Post-event new country rises to top BC** | A normalisation event (e.g. Abraham Accords) has created a new bridge relationship (e.g. UAE mediating Israel–Arab ties). |

The chart plots the **top broker for each year** (the country with the highest BC that year) and labels it on hover.

---

##### Eigenvector Centrality (right axis, auto-scaled)

**Definition.** Eigenvector centrality solves the self-referential problem of importance: a node is important if it is connected to important nodes. For node $v$:

$$EC(v) = \frac{1}{\lambda} \sum_{u \in \mathcal{N}(v)} w_{vu} \cdot EC(u)$$

where $w_{vu} = S^{\text{del}}_{vu,t}$ is the Deliberate Network Salton edge weight for that year, $\lambda$ is the dominant eigenvalue of the weighted adjacency matrix, and $\mathcal{N}(v)$ is $v$'s neighbours. Computed via `nx.eigenvector_centrality(G, weight="weight", max_iter=1000)`.

**What it measures.** Unlike degree centrality (which counts raw connections) or betweenness (which counts bridging paths), eigenvector centrality scores a country by the *quality* of its partners. Collaborating with the most active, well-connected countries in the region amplifies the score; collaborating only with peripheral, isolated countries does not.

**Interpreting the dashboard.** The dashboard plots EC for the **target country** specifically — the left dropdown.

| Pattern | Interpretation |
|:--------|:---------------|
| **Rising EC over time** | *Core convergence* — the target country is building ties with the most connected regional players. It is moving from the periphery toward the scientific core. |
| **Sustained high EC** | The target country is embedded in the dense collaborative core of the MENA network. Its partners are themselves highly active. |
| **Falling or near-zero EC** | *Peripheralisation* — the target's partners are weakly connected. Even if the raw paper count is rising (visible in H1), the *structural quality* of collaboration is low. The country is marginalised from the scientific core. |
| **EC rising after a geopolitical event** | New collaborations opened by that event connect the target to well-connected countries, not just to any country. Structurally significant normalisation. |

**Why the right axis is auto-scaled.** Eigenvector centrality values in small, sparse graphs typically range from ~0.001 to ~0.05 — far below the 0–1 range of the left axis. Displaying both on the same scale would flatten the EC line to invisibility. The right axis expands to the actual EC range so both metrics are readable simultaneously.

---

#### H4 — Thematic Compartmentalisation (Safe Harbor Effect)

The **H4 tab** tests whether scientifically and diplomatically isolated country pairs disproportionately confine their collaboration to **politically neutral STEM fields** — using science as a "safe harbor" to maintain contact without triggering political friction.

**Neutral fields** (defined in `config.NEUTRAL_FIELDS`): Medicine, Physics and Astronomy, Engineering, Chemistry, Mathematics.

The **Neutrality Index** is the percentage of joint papers classified as neutral STEM. The **temporal area chart** shows the year-by-year split between neutral and sensitive (Social Sciences, Humanities, Law, etc.) fields.

---

### 8.7 Frontend State Management

The frontend uses React's built-in hooks exclusively — no Redux, Zustand, Jotai, or any other state library.

#### State Variables

```
App Component
│
├── UI / Navigation
│   ├── activeTab           string   "h1" | "h2" | "h3" | "h4"
│   └── showSettings        boolean  settings panel open/closed
│
├── Country Selection
│   ├── targetCountry       string   e.g. "israel"
│   └── compareCountry      string   e.g. "united arab emirates"
│
├── Settings — Three Layers
│   ├── configDefaults      object   loaded once from GET /api/config on mount
│   ├── appliedSettings     object   the values the API was last called with
│   └── draft               object   current slider positions (may be unapplied)
│
├── Server Data
│   ├── dataset             array    per-year records for all four hypotheses
│   ├── globalBrokers       array    all-time broker country list
│   ├── summary             object   { pre, post, growth }
│   ├── subjects            array    top-5 subject areas
│   └── neutralRatio        number   0–100
│
└── Request Lifecycle
    ├── isLoading           boolean  true while fetch is in flight
    └── fetchError          string | null   last error message
```

#### Three-Layer Settings Pattern

The Settings panel maintains three copies of the parameter object to separate concerns:

```
configDefaults  ← loaded from /api/config at mount; read-only reference point
appliedSettings ← sent to the API on the last fetch; what the charts reflect
draft           ← what the sliders currently show; may differ from applied

isDirty = JSON.stringify(draft) !== JSON.stringify(appliedSettings)
```

This pattern prevents the API from being called on every slider tick (which would be expensive) while still making it possible to show the user that changes are pending (the amber dot). It also makes "Reset to defaults" trivial (`setDraft(configDefaults)`) and "Discard" trivial (`setDraft(appliedSettings)`).

```
Slider moves   → setDraft(...)        → isDirty = true  → amber dot shown
"Apply" click  → setAppliedSettings({...draft})
                 useEffect fires       → fetchData()
                 API called with new params
                 Response → setDataset / setGlobalBrokers / ...
                 Charts re-render
```

#### Derived Data — `useMemo`

The broker stacked-bar chart requires a reshaped data structure: instead of a flat array of `{year, brokers:[{name,papers}]}`, Recharts needs `[{year, germany: 3, usa: 2, …}]` with one key per broker country. This reshaping, plus the ranked list of unique broker names, is computed inside a single `useMemo` that depends on `dataset`:

```javascript
const { brokerTimelineData, uniqueBrokers } = useMemo(() => {
  // group by year; accumulate totals for ranking
}, [dataset]);
```

`useMemo` ensures the reshaping only runs when `dataset` changes, not on every render triggered by unrelated state (e.g. tab switching or slider movement).

#### Side Effects — `useEffect`

| `useEffect` | Dependencies | Purpose |
|:------------|:-------------|:--------|
| Config loader | `[]` (mount only) | Fetches `GET /api/config`; initialises all three settings layers |
| Data fetcher | `[targetCountry, compareCountry, appliedSettings]` | Calls `fetchData()` whenever the country selection or applied settings change |

The data-fetcher effect intentionally excludes `fetchData` from its dependency array (suppressed with the `// eslint-disable-line` comment) to avoid an infinite loop, since `fetchData` is a new function reference on every render.

---

### 8.8 Setup and Launch Guide

#### Prerequisites

| Tool | Version | Purpose |
|:-----|:--------|:--------|
| Python | ≥ 3.12 | Backend runtime |
| [uv](https://github.com/astral-sh/uv) | latest | Python dependency management |
| Node.js | ≥ 18 | Frontend build toolchain |
| npm | ≥ 9 | Frontend package management |
| DuckDB database | populated | Source data; see `pipeline/database.py` |

#### Step 1 — Install Python dependencies

```bash
# From the project root
uv sync
```

This installs all packages declared in `pyproject.toml`, including `fastapi`, `uvicorn`, `duckdb`, `networkx`, `pandas`, and `scipy`.

#### Step 2 — Install frontend dependencies

```bash
cd frontend
npm install
```

This installs React 19, Recharts, TailwindCSS v4, lucide-react, and Vite.

#### Step 3 — Start the backend

```bash
# From the project root (not inside frontend/)
uv run uvicorn api:app --reload --port 8000
```

The `--reload` flag enables hot-reloading: changes to `api.py` restart the server automatically. Verify it is running:

```bash
curl http://localhost:8000/health
# → {"status":"ok"}

curl "http://localhost:8000/api/config"
# → {"np_threshold":4,"w_small":0.8,...}
```

#### Step 4 — Start the frontend

In a **second terminal**:

```bash
cd frontend
npm run dev
```

Vite starts at `http://localhost:5173`. Open this URL in your browser.

The Vite dev server proxies `/api/*` to `http://localhost:8000` (configured in `frontend/vite.config.js`), so the browser never makes a cross-origin request during development.

#### Step 5 — Production build

```bash
# Build the frontend for static hosting
cd frontend
npm run build
# Output: frontend/dist/

# Serve the static build from FastAPI (optional — for single-process deployment)
# Add to api.py:
#   from fastapi.staticfiles import StaticFiles
#   app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

#### Troubleshooting

| Symptom | Cause | Fix |
|:--------|:------|:----|
| "Backend Unreachable" error panel | FastAPI not running | Start with `uv run uvicorn api:app --reload --port 8000` |
| Charts show old threshold label (e.g. "≤ 5") | Cached old frontend build in browser | Hard-refresh (`Cmd+Shift+R`) or run `npm run dev` for the live dev server |
| `ModuleNotFoundError: fastapi` | `fastapi` not in environment | Run `uv sync` from project root |
| API returns `400 Invalid country` | Country name contains capitalisation | All values in the dropdowns are pre-set to lowercase; check custom API calls |
| Eigenvector centrality: all zeros | Deliberate Network graph is empty for that year | Threshold may be too small (e.g. nₚ ≤ 2 leaves very few edges); raise np_threshold |

---

### 8.9 "Who Calls What" Reference

The table below traces every significant action in the UI back to the Python function that ultimately services it.

| User Action | React Handler | Fetch URL | FastAPI Handler | SQL Builder(s) | Python Math |
|:------------|:-------------|:----------|:----------------|:---------------|:------------|
| Page load | `useEffect([], mount)` | `GET /api/config` | `get_config()` | — (reads module constants) | — |
| Change target/compare country | `setTargetCountry` / `setCompareCountry` | `GET /api/metrics?target=…&compare=…&…` | `get_metrics()` | All H1–H4 builders | `_compute_h3()` via NetworkX |
| Move nₚ slider | `setDraft(d => ({...d, npThreshold: N}))` | — | — | — | — |
| Click "Apply & Recalculate" | `setAppliedSettings({...draft})` | `GET /api/metrics?…&np_threshold=N` | `get_metrics()` | `_h1_sql(threshold=N)`, `_h3_all_years_sql(threshold=N,…)` | `_compute_h3()` with new edge weights |
| Move w_small slider + Apply | `setDraft` → `setAppliedSettings` | `GET /api/metrics?…&w_small=F` | `get_metrics()` | `_h3_all_years_sql(…, w_small=F)` | NetworkX EC/BC on reweighted graph |
| Move w_cons slider + Apply | `setDraft` → `setAppliedSettings` | `GET /api/metrics?…&w_cons=F` | `get_metrics()` | `_h3_all_years_sql(…, w_cons=F)` | `CASE WHEN np > threshold THEN F` |
| Click "Reset to defaults" | `setDraft(configDefaults)` | — | — | — | — |
| Click "Discard" | `setDraft(appliedSettings)` | — | — | — | — |
| Click "Retry" (error panel) | `fetchData()` | `GET /api/metrics?…` | `get_metrics()` | All builders | `_compute_h3()` |
| Switch to H3 tab | `setActiveTab("h3")` | — (data already in state) | — | — | — |
| Hover H3 chart | `CustomH3Tooltip` render | — | — | — | — |

**Key invariant:** `config.py` is **never written to by the API**. The Settings panel sliders in the browser control what query parameters are sent to the backend; the backend resolves those parameters locally and returns results. The `config.py` file retains its authored values at all times during web-server operation. Permanent changes to defaults require editing `config.py` directly and restarting `uvicorn`.

---

*Research Engine — Bar-Ilan University, Department of Information Science*  
*MENA Scientific Collaboration Study, 1990–2025*
