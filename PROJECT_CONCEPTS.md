The overarching objective of this project is to develop and apply a computational framework for identifying persistent channels and structural weaknesses in Israel’s international scientific collaboration under geopolitical pressure. By analyzing observed collaboration behavior over time, the project aims to provide a systematic diagnostic of how international collaboration is structured, where it is constrained, and where it remains viable.

Specific Aim 1: Identify structural channels of collaboration
To characterize the structural organization of Israel’s international scientific collaboration by examining the scale and topology of collaboration networks. This aim evaluates whether collaboration is disproportionately organized around small-scale partnerships rather than large multi-country consortia, and how collaboration is embedded within network communities, brokerage structures, and clusters. The analysis will determine which structural forms of collaboration persist over time and under varying geopolitical circumstances.

Specific Aim 2: Assess Israel’s position within regional and global collaboration systems
To evaluate Israel’s relative position within both regional (MENA) and global scientific collaboration networks over time. This aim examines changes in Israel’s network centrality, connectivity, and relative rank, assessing whether Israel becomes relatively more peripheral or remains structurally integrated as collaboration networks evolve. The analysis will distinguish between absolute growth in productivity and collaboration and Israel’s relative positioning within the system.

Specific Aim 3: Identify thematic channels and concentration patterns
To analyze the disciplinary composition of Israel’s international collaboration and determine whether collaboration is selectively concentrated in specific scientific domains. This aim evaluates whether cross-border collaboration is disproportionately sustained in certain fields, identifying thematic channels that remain active as well as areas that are structurally underrepresented.

Specific Aim 4: Detect structural irregularities and policy-relevant weak points
To identify systematic deviations in Israel’s collaboration structure relative to regional and global baselines, and to distinguish between structural weaknesses and persistent channels. This aim integrates the structural, positional, and thematic analyses to produce a unified diagnostic of collaboration patterns. It focuses on identifying where collaboration is consistently weaker than expected and where it remains stable, thereby generating actionable insights into constraints and opportunities for strengthening international scientific engagement.

This project adopts a computational, longitudinal design to analyze Israel’s international scientific collaboration as an observable system evolving under geopolitical pressure. The analysis proceeds in four structured stages, each corresponding to a predefined objective and a set of measurable indicators.
The research evaluates collaboration structure along three core dimensions:
	•	scale of collaboration,
	•	network position, and
	•	thematic composition.

These dimensions are operationalized using predefined metrics and applied consistently across time, enabling systematic comparison across geopolitical periods and analytical contexts.

Stage 1: Construction of Longitudinal Collaboration Networks (Israel–MENA and Israel–Global)
The first stage constructs annual collaboration networks based on bibliometric data (extracted from Scopus and/or OpenAlex), covering Israel and countries in the Middle East and North Africa (MENA), as well as Israel’s global collaboration system. This stage serves as the primary analytical entry point.
Each network will be defined as a weighted graph in which:
	•	nodes represent countries,
	•	edges represent co-authorship ties, and
	•	edge weights reflect collaboration intensity using fractional counting.
To distinguish collaboration scale, the network will be decomposed into two layers:
	•	small-scale (“deliberate”) collaborations (limited number of participating countries, e.g., ≤5), and
	•	multi-country (“consortia-based”) collaborations.

For each dyad-year, the project will compute:
	•	the share of collaboration occurring in small-scale versus consortia-based forms, and
	•	total collaboration intensity normalized by scientific output.

In addition, major geopolitical events (e.g., the First and Second Intifada, peace agreements with Egypt and Jordan, and the Abraham Accords) will be incorporated as temporal markers, enabling the analysis of structural changes in collaboration patterns across defined geopolitical periods.

Stage 2: Structural and Topological Analysis
The second stage evaluates the structural organization of collaboration using predefined indicators corresponding to scale, network position, and topology.
First, the scale of collaboration will be evaluated using the share of collaboration in small-scale versus consortia-based formats, along with temporal trends in collaboration scale.
Second, network position will be evaluated using eigenvector centrality, weighted degree (connectivity), and relative rank within the network. This analysis will allow comparison of Israel’s position to that of comparable countries and track their trajectories over time.
Third, network topology will be evaluated using modularity (community structure), clustering coefficients, network density, and the presence of brokerage roles. These measures provide a multi-dimensional characterization of collaboration structure, enabling systematic assessment of Israel’s position within evolving network communities and its role as a connector or peripheral actor.

Stage 3: Thematic Composition Analysis
The third stage analyzes the disciplinary composition of collaboration using subject classifications.
Publications will be categorized into broad domains using established classification systems (e.g., Scopus journal subject classifications and OpenAlex topics), distinguishing between neutral/pragmatic fields (e.g., engineering, natural sciences, clinical medicine) and socially or politically sensitive fields (e.g., social sciences, humanities).
For each collaboration dyad and year, the project will compute:
	•	the distribution of collaboration across domains, and
	•	relative representation compared to regional and global baselines.
This analysis enables the identification of thematic concentration patterns, indicating where collaboration is sustained and where it is structurally limited.

Stage 4: Integration and Structural Diagnosis
The final stage integrates results across all analytical dimensions to produce a unified diagnostic of Israel’s international collaboration system, considering both regional and global contexts.
The analysis will distinguish between:
	•	Structural Weak Points: areas where collaboration is consistently lower than expected, unevenly distributed, or asymmetrical relative to baseline patterns.
	•	Persistent Channels: forms of collaboration that remain stable over time, are less affected by geopolitical events, and represent viable pathways for continued international engagement.
This diagnostic framework provides a systematic basis for identifying both constraints and opportunities within the collaboration system and highlights policy-relevant areas where intervention may strengthen international scientific collaboration.

Feasibility and Data Availability
The project builds on existing bibliometric data and preliminary analyses of the Israel–MENA collaboration system conducted by the proposer and his students, ensuring feasibility within the proposed timeframe. As part of this work, an interactive analytical tool was developed to explore and visualize collaboration scale, structure, and thematic composition (see: https://eshokhat.github.io/scime/), enabling rapid validation of indicators and sensitivity analyses. These preliminary efforts demonstrate that the proposed framework can be implemented effectively and produce stable, interpretable structural patterns across the core analytical dimensions.

Limitations and Risk Mitigation While coauthorship provides a robust large-scale proxy for international collaboration, it does not capture all forms of scientific interaction (e.g., informal exchanges or shared infrastructure). The project addresses this limitation by explicitly framing its contribution as a structural analysis of publications-based manifested collaboration patterns. In addition, methodological choices such as database selection, counting methods, and collaboration thresholds may influence observed patterns. To mitigate these risks, the analysis will incorporate robustness checks across alternative data sources (e.g., Scopus and OpenAlex), counting schemes (fractional vs. full), and parameterizations (e.g., collaboration scale thresholds). This ensures that identified structural patterns reflect stable system properties rather than artifacts of measurement choices.
