
\section{Methods}

\subsection{Middle East Borders}
To accurately map the geopolitical contours of the region, we adopt a comprehensive definition of the Middle East and North Africa (MENA) that encompasses all primary state actors involved in the region's shifting diplomatic landscape. The network includes established Middle Eastern nations (e.g., Israel, Egypt, Jordan, Lebanon, Syria, Iraq, Iran, Saudi Arabia, Yemen, Oman, Qatar, Kuwait, United Arab Emirates, Bahrain) alongside relevant North African states (e.g., Morocco) that are central to recent diplomatic normalization efforts. This boundary selection ensures all parties to both historical regional conflicts and recent treaties, such as the Abraham Accords, are represented within the network topology.

\subsection{Data}
The empirical analysis spans a 36-year period, from 1990 to 2025 inclusive. This timeframe was deliberately selected to capture the long-term baseline dynamics of regional scientific production while encompassing two massive exogenous geopolitical shocks. Consequently, the dataset is temporally segmented into three distinct epochs based on their occurrence: 

(1) Pre-Arab Spring (1990--2010), representing the baseline network structure prior to regional destabilization; 
(2) Arab Spring to Pre-Normalization (2011--2019), capturing the network's resilience during widespread geopolitical upheaval; and 
(3) Post-Abraham Accords (2020--2025), isolating the structural impact of formal diplomatic normalization between Israel and the UAE, Bahrain, and Morocco. 

Bibliometric data was retrieved from Scopus, querying for all documents classified as research articles or reviews. We extracted the full set of publications where at least two of the defined regional countries are listed in the authors' affiliations. To establish our comparative baselines, we independently retrieved the global base rates---total annual publication counts---for each country in the region across the exact same 2000--2025 timeframe.

\subsection{Regional Collaboration Network}
We build a regional collaboration network where each node represents a country within our defined regional borders, and an edge denotes the intensity of cross-border scientific co-authorship between them. 

\subsection{Analytical Strategy}
The empirical strategy proceeds in five steps. First, we construct annual collaboration networks and normalize dyadic collaboration strength by countries' overall scientific output. Second, we compare unrestricted collaboration with a restricted network that excludes large multi-country papers in order to evaluate whether apparent ties are driven by mega-science. Third, we estimate the impact of the Arab Spring and the Abraham Accords on regional collaboration patterns. Fourth, we examine whether Israel's structural position within the regional network changes over time. Fifth, we assess whether cross-border collaboration is concentrated in substantively neutral fields.

\vspace{1em}
\hrule
\vspace{1em}
\noindent\textbf{ANALYTICAL IMPLEMENTATION}
\vspace{0.5em}

\subsection{Step 1: Data Preparation \& Network Normalization}
All metrics must be calculated on a \textbf{rolling annual basis ($t$)} from 1990 to 2025. 
First, construct two parallel longitudinal networks from the raw edge list:
\begin{enumerate}
    \item \textbf{The Unrestricted Network:} All regional co-authored papers.
    \item \textbf{The Deliberate Network:} Only papers with 5 or fewer participating countries ($n_{p} \le 5$).
\end{enumerate}

For every year $t$ across both networks, calculate the fractionally counted collaboration strength between country $i$ and country $j$. Distributing the edge weight penalizes hyper-authorship:

\begin{equation}
C_{ij,t}^* = \sum_{p \in P_{ij,t}} \frac{2}{n_p(n_p - 1)}
\end{equation}

Next, calculate the normalized annual affinity, $S_{ij,t}$, using the raw annual global publication counts ($P_{i,t}$) as the baseline scientific mass. Using the raw output in the denominator dynamically absorbs national macroeconomic changes while maintaining a conservative estimation. \textit{Computational note: If either $P_{i,t}$ or $P_{j,t}$ equals zero for a given year, $S_{ij,t}$ must be forced to 0 to prevent undefined errors.}

\begin{equation}
S_{ij,t} = \frac{C_{ij,t}^*}{\sqrt{P_{i,t} \times P_{j,t}}}
\end{equation}

\subsection{Step 2: Testing H1 (The Mirage)}
\textbf{Objective:} Quantify the structural reliance on mega-science for Israel/Non-Normalized dyads.
\begin{itemize}
    \item \textbf{Metric:} Calculate the Collapse Metric ($\Delta C$) for every dyad-year. \textit{Execution note: To avoid division by zero, this metric is ONLY calculated for dyad-years where $S_{ij,t}(\text{Unrestricted}) > 0$. If a dyad has no baseline collaboration, it drops out of this specific test.}
    $$ \Delta C_{ij,t} = \frac{S_{ij,t}(\text{Unrestricted}) - S_{ij,t}(\text{Deliberate})}{S_{ij,t}(\text{Unrestricted})} $$
    \item \textbf{Statistical Test:} Segment the filtered dyads into \textit{Fractured Dyads} (Israel and non-normalized states) and \textit{Control Dyads} (all other regional pairs). Run a \textbf{Mann-Whitney U test} to compare the distributions of $\Delta C$. A significantly higher median $\Delta C$ for the Fractured Dyads confirms H1.
\end{itemize}

\subsection{Step 3: Testing H2 (The Difference-in-Differences Models)}
\textbf{Objective:} Measure the causal impact of geopolitical shocks. \textit{Execution note: This step MUST be performed strictly on the Deliberate Network ($n_{p} \le 5$) weights to exclude the mega-science noise. All regressions in Step 3 MUST use standard errors clustered at the dyad level to account for serial autocorrelation.}

\textbf{Testing H2a (The Arab Spring \& Destabilization):}
\begin{itemize}
    \item \textbf{Model:} Generalized Two-Way Fixed Effects (TWFE) Difference-in-Differences.
    \item \textbf{Coding the Variables:} Create three binary indicators:
    \begin{enumerate}
        \item $\text{Destabilized}_{ij}$: Equals 1 if at least one country in the dyad experienced severe domestic upheaval during the Arab Spring (e.g., Egypt, Syria, Libya, Yemen, Tunisia).
        \item $\text{Israel}_{ij}$: Equals 1 if the dyad involves Israel.
        \item $\text{Post2011}_t$: Equals 1 for all years $t \ge 2011$.
    \end{enumerate}
    \textit{Note: The omitted reference group consists of ``Stable'' regional dyads that neither involve Israel nor experienced severe Arab Spring conflict (e.g., Saudi Arabia, UAE, Qatar).}
    
    \item \textbf{Equation:}
    \begin{equation}
    S_{ij,t} = \beta_0 + \beta_1(\text{Destabilized}_{ij} \times \text{Post2011}_t) + \beta_2(\text{Israel}_{ij} \times \text{Post2011}_t) + \gamma_{ij} + \tau_t + \epsilon_{ij,t}
    \end{equation}
    Where $\gamma_{ij}$ and $\tau_t$ are dyad and year fixed effects.
    
    \item \textbf{Expected Result:} $\beta_1$ must be negative and statistically significant ($\beta_1 < 0$). $\beta_2$ must be statistically indistinguishable from zero ($p > 0.05$), proving Israel's geopolitical stasis.
\end{itemize}

\textbf{Testing H2b (The Abraham Accords):}
\begin{itemize}
    \item \textbf{Model:} Multi-Group Difference-in-Differences.
    \item \textbf{Equation:} 
    \begin{equation}
    S_{ij,t} = \beta_0 + \beta_1(\text{Norm}_{ij} \times \text{Post2020}_t) + \beta_2(\text{NonNorm}_{ij} \times \text{Post2020}_t) + \gamma_{ij} + \tau_t + \epsilon_{ij,t}
    \end{equation}
    Where $\text{Norm}_{ij}$ includes Israel-UAE, Israel-Bahrain, Israel-Morocco, and $\text{NonNorm}_{ij}$ includes Israel's ties with traditional non-normalizing actors. \textit{Note: The omitted reference group here is all non-Israeli regional dyads (Arab-Arab, Arab-Iran, etc.).}
    \item \textbf{Expected Result:} $\beta_1 > 0$ (significant growth) and $\beta_2 \le 0$ (stagnation or decay).
\end{itemize}

\subsection{Step 4: Testing H3 (Topological Peripheralization)}
\textbf{Objective:} Track Israel's relative network influence.
\begin{itemize}
    \item \textbf{Metric:} Treat the Deliberate Network ($n_{p} \le 5$) as an undirected, weighted graph. Calculate the \textbf{Eigenvector Centrality ($EC$)} for every node annually using the $S_{ij,t}$ weights. 
    \item \textbf{Statistical Test:} Extract the time-series vector of Israel's annual $EC$ scores (1990--2025). Run a \textbf{Mann-Kendall Trend Test}. A negative $S$ statistic with $p < 0.05$ confirms a monotonic downward trend in regional influence.
\end{itemize}

\subsection{Step 5: Testing H4 (Thematic Compartmentalization)}
\textbf{Objective:} Prove thematic avoidance without requiring global subject-level baselines.
\begin{itemize}
    \item \textbf{Metric:} Categorize all papers into ``Neutral'' (Exact Sciences, Clinical Medicine, Engineering) or ``Sensitive'' (Social Sciences, Humanities, Arts). \textit{Execution note: If a paper is tagged with Scopus codes from both categories, apply a fractional counting rule (e.g., 0.5 to Neutral, 0.5 to Sensitive) to prevent double-counting in the contingency table.}
    \item \textbf{Statistical Test:} Construct a $2 \times 2$ contingency table calculating the sum of (Neutral vs. Sensitive) papers for (Israel-Arab Dyads vs. Regional Control Dyads). 
    \item \textbf{Analysis:} Run \textbf{Fisher’s Exact Test}. A statistically significant Odds Ratio (OR) $> 1$ indicates that Israel-Arab collaboration is artificially constrained to neutral disciplines compared to the regional baseline.
\end{itemize}

% In order to appropriately assign weights to the edges and avoid artificially inflating the regional network density due to hyper-authored publications, we apply a fractional counting method \cite{}. Mathematically, for any joint publication $p$ involving countries $i$ and $j$, the collaboration weight is distributed evenly across all possible bilateral pairs. The fractional collaboration strength, $C_{ij}^*$, is defined as:

% $$C_{ij}^* = \sum_{p \in P_{ij}} \frac{2}{n_p(n_p - 1)}$$

% where $P_{ij}$ is the set of regional papers co-authored by both country $i$ and country $j$, and $n_p$ is the total number of unique countries affiliated with paper $p$.

% To account for the massive disparities in baseline scientific output among nations, we normalize the fractional edge weights calculated above ($C_{ij}^*$) using Salton's Cosine \cite{}. We calculate this using the global publication mass of the corresponding countries ($P_i$ and $P_j$):

% $$S_{ij} = \frac{C_{ij}^*}{\sqrt{P_i \times P_j}}$$

% Note that this asymmetric normalization strategy introduces a strictly conservative estimation to our affinity metric, $S_{ij}$. Because full-count base rates ($P_i$ and $P_j$) do not penalize for hyper-authorship, they inherently inflate the denominator, making our subsequent analysis conservative and robust against the background noise of global internationalization.
