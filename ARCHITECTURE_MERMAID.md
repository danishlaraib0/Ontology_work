# 🚗 Automotive World Ontology: Production Architecture & Dynamic Query System

This document provides technical Mermaid diagrams reflecting the **production-grade reality** of the Automotive World Model:
1. **Multi-Cadence Data Ingestion** (Scheduled & Event-Triggered Batching, not unrealistic continuous streaming).
2. **Dynamic Querying Architecture** (SLM Intent & Query Planner ➔ Guardrailed Schema-Aware Cypher + Deterministic Solvers ➔ LLM Synthesizer).
3. **Closed-Loop Model Recalibration** (Feedback from observed market data into model parameters).

---

### 1. Dynamic Query Planning & Execution Architecture

This diagram illustrates how an open-ended natural-language question from an automotive executive or product manager is parsed, routed, and safely answered without hallucinating arbitrary Cypher:

```mermaid
flowchart TB
    %% STYLING
    classDef inputStyle fill:#EDE9FE,stroke:#7C3AED,stroke-width:2px,color:#4C1D95,font-weight:bold
    classDef plannerStyle fill:#FEF3C7,stroke:#D97706,stroke-width:2px,color:#78350F,font-weight:bold
    classDef guardStyle fill:#FEE2E2,stroke:#DC2626,stroke-width:2px,color:#991B1B,font-weight:bold
    classDef toolStyle fill:#E0F2FE,stroke:#0284C7,stroke-width:1.5px,color:#075985
    classDef dbStyle fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#14532D,font-weight:bold
    classDef synthStyle fill:#FAF5FF,stroke:#A855F7,stroke-width:2px,color:#581C87,font-weight:bold
    classDef outStyle fill:#ECFDF5,stroke:#059669,stroke-width:2px,color:#064E3B,font-weight:bold

    %% USER QUESTION
    USER_PROMPT["<b>User / Product Manager Question</b><br/><i>'Which competitors are most vulnerable if Dzire cuts price by ₹30,000?'</i>"]:::inputStyle

    %% QUERY PLANNER
    subgraph S_PLANNER ["🧠 1. Intent Classification & Query Planning"]
        direction TB
        SLM_PLANNER["<b>SLM Query Planner (Gemma 9B / Gemini Flash)</b><br/>• Entity Extraction: Target='Dzire', Price_Delta=-30000<br/>• Intent: Competitive Vulnerability + Price Elasticity Simulation<br/>• Selects Execution Path & Missing Evidence Requirements"]:::plannerStyle
        SCHEMA_REF["<b>Metamodel Schema Context</b><br/>Allowed Labels: VehicleModel, Variant, PriceObservation<br/>Allowed Relationships: COMPETES_WITH, HAS_PRICE"]:::toolStyle
        SCHEMA_REF --> SLM_PLANNER
    end

    USER_PROMPT --> SLM_PLANNER

    %% EXECUTION ROUTING
    subgraph S_ROUTER ["⚡ 2. Dual-Track Execution Engine"]
        direction TB

        subgraph PATH_DETERMINISTIC ["Track A: Deterministic Parameterized Tools"]
            TOOL_SIM["<b>Scenario Engine (sales_forecasting.py)</b><br/>Simulates ₹30,000 price cut with segment elasticity"]:::toolStyle
            TOOL_GAP["<b>Competitive Gap Engine (gap_analysis.py)</b><br/>Evaluates rival factor deltas & price overlap"]:::toolStyle
            TOOL_FIT["<b>Fit Scoring Engine (fit_scoring.py)</b><br/>Calculates Fit(s,v) across affected buyer segments"]:::toolStyle
        end

        subgraph PATH_CYPHER ["Track B: Schema-Aware Read-Only Cypher"]
            CYPHER_GEN["<b>Read-Only Cypher Generator</b><br/>Generates custom multi-hop graph traversal"]:::toolStyle
            CYPHER_GUARD["<b>Safety AST Guardrail & Validator</b><br/>• Rejects WRITE ops (MERGE, CREATE, DELETE, SET)<br/>• Enforces 5-second timeout & LIMIT 50 controls<br/>• Validates labels against schema whitelist"]:::guardStyle
            CYPHER_GEN --> CYPHER_GUARD
        end
    end

    SLM_PLANNER ==>|Routine Simulation & Scoring| PATH_DETERMINISTIC
    SLM_PLANNER ==>|Complex Multi-Hop Inquiry| CYPHER_GEN

    %% GRAPH RETRIEVAL
    NEO4J_DB[("<b>Neo4j Knowledge Graph</b><br/>700 Nodes • 2,029 Relationships<br/>Historical dispatches, price ladders, rivalries")]:::dbStyle

    PATH_DETERMINISTIC <-->|Query State & Series| NEO4J_DB
    CYPHER_GUARD <-->|Execute Validated Cypher| NEO4J_DB

    %% SYNTHESIS
    subgraph S_SYNTHESIS ["🔬 3. Evidence-Grounded Reasoning & Synthesis"]
        direction TB
        LLM_SYNTH["<b>LLM Synthesizer (Gemini Pro / Claude)</b><br/>• Combines retrieved subgraphs with simulation curves<br/>• Strictly segregates <b>verified facts</b> from <b>assumptions</b><br/>• Computes composite confidence score & provenance ledger"]:::synthStyle
    end

    PATH_DETERMINISTIC ==>|Simulation Results| LLM_SYNTH
    CYPHER_GUARD ==>|Graph Subgraph Evidence| LLM_SYNTH

    %% GROUNDED OUTPUT
    EXECUTIVE_RESPONSE["<b>Executive Grounded Answer</b><br/>• <b>Vulnerable Rivals:</b> Honda Amaze (90% price overlap), Hyundai Aura<br/>• <b>Simulated Volume Gain:</b> +1,240 units/month (±180 at 80% CI)<br/>• <b>Assumptions:</b> Price elasticity η = -0.85 in entry sedan tier<br/>• <b>Provenance:</b> Sourced from SIAM dispatches & verified OEM price ladders"]:::outStyle

    LLM_SYNTH --> EXECUTIVE_RESPONSE
```

---

### 2. Multi-Cadence Ingestion & Closed-Loop Recalibration

This diagram illustrates the **honest data lifecycle**: scheduled and event-triggered updates instead of unrealistic continuous streaming, coupled with a real model calibration loop:

```mermaid
flowchart LR
    %% STYLING
    classDef cadMonthly fill:#E0F2FE,stroke:#0284C7,stroke-width:2px,color:#075985
    classDef cadWeekly fill:#FEF9C3,stroke:#CA8A04,stroke-width:2px,color:#713F12
    classDef cadEvent fill:#FEE2E2,stroke:#DC2626,stroke-width:2px,color:#7F1D1D
    classDef valStyle fill:#FFFFFF,stroke:#38BDF8,stroke-width:1.5px,color:#0369A1
    classDef neoStyle fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#14532D,font-weight:bold
    classDef recalStyle fill:#FFF1F2,stroke:#E11D48,stroke-width:2px,stroke-dasharray: 5 5,color:#9F1239,font-weight:bold

    %% CADENCES
    subgraph CADENCES ["⏱️ Real-World Data Ingestion Cadences"]
        direction TB
        M_SIAM["<b>Monthly Scheduled:</b><br/>• SIAM OEM wholesale dispatches<br/>• VAHAN state-level registrations"]:::cadMonthly
        W_PRICE["<b>Weekly / Daily Scheduled:</b><br/>• Ex-showroom price adjustments<br/>• Forum sentiment (Team-BHP)<br/>• Search trend volumes"]:::cadWeekly
        E_LAUNCH["<b>Event-Triggered:</b><br/>• New vehicle & trim launches<br/>• Global NCAP crash ratings<br/>• Powertrain transitions"]:::cadEvent
    end

    %% VALIDATION
    subgraph NORMALIZATION ["🛡️ Extraction & Schema Normalization"]
        direction TB
        EXTRACT["<b>Pydantic Validation & Deduplication</b><br/>• Temporal tagging (valid_from, valid_to, is_current)<br/>• Source provenance & credibility tier assignment<br/>• Zero-vs-missing invariant enforcement"]:::valStyle
    end

    CADENCES --> EXTRACT

    %% NEO4J GRAPH
    subgraph GRAPH ["🕸️ Neo4j Knowledge Graph"]
        direction TB
        LOADER["<b>Idempotent MERGE Operations</b><br/>Preserves historical dispatches & price history without overwrites"]:::neoStyle
    end

    EXTRACT --> LOADER

    %% CLOSED LOOP RECALIBRATION
    subgraph RECALIBRATION ["🔄 Closed-Loop Operational Recalibration"]
        direction TB
        COMPARE["<b>Residual Calibration</b><br/>Compares predicted sales vs actual SIAM dispatches<br/>➔ Recalibrates price elasticity coefficients (η)"]:::recalStyle
        DRIFT["<b>Weight Drift Adaptation</b><br/>Detects shifts in search intent volume<br/>➔ Adjusts customer persona buying factor weights"]:::recalStyle
    end

    LOADER --> COMPARE
    LOADER --> DRIFT
    COMPARE -.->|Update Model Elasticity Parameters| CADENCES
    DRIFT -.->|Update Persona Factor Weights| CADENCES
```

---

### 3. Full Enterprise 4-Stage Architecture Blueprint

```mermaid
flowchart TB
    %% STYLING
    classDef stageHeader fill:#1E293B,stroke:#0F172A,stroke-width:2px,color:#F8FAFC,font-weight:bold
    classDef srcCard fill:#F0F9FF,stroke:#0284C7,stroke-width:1.5px,color:#0C4A6E
    classDef layerCard fill:#FFFFFF,stroke:#38BDF8,stroke-width:1.5px,color:#0369A1
    classDef graphEngine fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#14532D,font-weight:bold
    classDef nodeDomain fill:#F0FDF4,stroke:#22C55E,stroke-width:1.5px,color:#14532D
    classDef plannerCard fill:#FEF3C7,stroke:#D97706,stroke-width:2px,color:#78350F,font-weight:bold
    classDef solverCard fill:#FFFBEB,stroke:#F59E0B,stroke-width:1.5px,color:#92400E
    classDef synthCard fill:#FAF5FF,stroke:#7C3AED,stroke-width:2px,color:#4C1D95,font-weight:bold
    classDef solutionCard fill:#F5F3FF,stroke:#8B5CF6,stroke-width:2px,color:#2E1065,font-weight:bold

    %% STAGE 1: INGESTION
    subgraph STAGE_1 ["STAGE 1: MULTI-CADENCE INGESTION & 12 LAYERS"]
        direction TB
        S1_CAD["<b>Multi-Cadence Streams</b><br/>Monthly SIAM/VAHAN • Weekly Pricing/Sentiment • Event Launch Specs"]:::srcCard
        S1_VAL["<b>Pydantic Normalization & Provenance Ledger</b><br/>Temporal valid_from/valid_to tagging & source citations"]:::srcCard
        S1_LAYERS["<b>12-Layer Normalized JSON Datasets</b><br/>L01-L04: Specs & Rivals | L05-L06: Segments & Factors<br/>L07-L08: Reviews & Claims | L09-L12: Intent, Sales, Pricing"]:::layerCard
        S1_CAD --> S1_VAL --> S1_LAYERS
    end

    %% STAGE 2: KNOWLEDGE GRAPH
    subgraph STAGE_2 ["STAGE 2: KNOWLEDGE GRAPH & ONTOLOGY (Neo4j)"]
        direction TB
        G_LOADER["<b>Graph Transformation & Loader (loader.py)</b><br/>Unique constraints on 23 labels • Idempotent MERGE operations"]:::graphEngine
        subgraph G_DOMAINS ["23 Labels • 25 Relationships • 700 Nodes • 2,029 Rels"]
            direction TB
            D_PROD["<b>Product Domain:</b> Brand ➔ Model ➔ Variant ➔ Feature / Engine"]:::nodeDomain
            D_CUST["<b>Customer Domain:</b> CustomerSegment ➔ Prioritizes ➔ BuyingFactor"]:::nodeDomain
            D_COMP["<b>Competitive Dynamics:</b> Model ➔ Competes_With {score, overlap} ➔ Model"]:::nodeDomain
            D_OPIN["<b>Opinion Domain:</b> Review ➔ Contains ➔ Opinion ➔ Aspect"]:::nodeDomain
            D_COMM["<b>Commercial Domain:</b> SalesObservation, PriceObservation, MarketChange"]:::nodeDomain
        end
        G_SCHEMA["<b>Metamodel Schema Registry</b> (schema/metamodel.yaml)"]:::graphEngine
        G_LOADER --> G_DOMAINS
        G_DOMAINS --> G_SCHEMA
    end

    %% STAGE 3: DYNAMIC QUERYING & SOLVERS
    subgraph STAGE_3 ["STAGE 3: DYNAMIC QUERY PLANNING & REASONING"]
        direction TB
        P_USER["<b>User Natural Language Inquiry</b><br/>Executive questions, what-if counterfactuals, comparisons"]:::plannerCard
        P_SLM["<b>SLM Intent & Query Planner (Gemma 9B / Gemini Flash)</b><br/>Entity extraction, intent classification, tool routing"]:::plannerCard
        subgraph P_EXEC ["Hybrid Execution Layer"]
            direction TB
            E_CYPHER["<b>Guardrailed Read-Only Cypher</b><br/>AST validation against schema, execution timeouts & limits"]:::solverCard
            E_SOLVERS["<b>Deterministic Solvers</b><br/>Fit Scoring • Gap Analysis • Sales Forecast • Causal Impact"]:::solverCard
        end
        P_SYNTH["<b>LLM Synthesizer (Gemini Pro / Claude)</b><br/>Separates facts from assumptions, attaches confidence & provenance"]:::synthCard

        P_USER --> P_SLM
        P_SLM ==> E_CYPHER
        P_SLM ==> E_SOLVERS
        E_CYPHER ==> P_SYNTH
        E_SOLVERS ==> P_SYNTH
    end

    %% STAGE 4: CLIENT PROBLEM SOLVING
    subgraph STAGE_4 ["STAGE 4: CLIENT VALUE & CLOSED-LOOP RECALIBRATION"]
        direction TB
        subgraph S4_SOLUTIONS ["Strategic Decision Support"]
            direction TB
            SOL_1["<b>Product Planning:</b> High-ROI feature selection without MSRP inflation"]:::solutionCard
            SOL_2["<b>Audience Targeting:</b> Quantified persona fit scores & barrier removal"]:::solutionCard
            SOL_3["<b>Competitive Defense:</b> Real-time battleground alerts & vulnerability attacks"]:::solutionCard
            SOL_4["<b>Pricing Simulation:</b> Volume elasticity & cannibalization checks"]:::solutionCard
        end
        S4_RECAL["<b>Closed-Loop Operational Recalibration</b><br/>Forecast residuals adjust elasticity η; search trend shifts update weights"]:::plannerCard
        S4_SOLUTIONS --> S4_RECAL
    end

    %% INTER-STAGE PIPELINES
    S1_LAYERS ==>|Idempotent Ingestion| G_LOADER
    G_SCHEMA -.->|Schema Metadata| P_SLM
    G_DOMAINS <==>|Subgraphs & Telemetry| P_EXEC
    P_SYNTH ==>|Grounded Answers| S4_SOLUTIONS
    S4_RECAL -.->|Recalibrated Elasticity & Weights| S1_CAD
```

---

### 📁 Updated File Links
* Editable Draw.io file: [`automotive_intelligence_architecture.drawio`](file:///home/immortal/Desktop/Ontology/automotive_intelligence_architecture.drawio)
* Mermaid file: [`ARCHITECTURE_MERMAID.md`](file:///home/immortal/Desktop/Ontology/ARCHITECTURE_MERMAID.md)
* Executive documentation: [`system_architecture_diagram.md`](file:///home/immortal/.gemini/antigravity-ide/brain/e1407330-0f85-4175-a76e-53800cd82e81/system_architecture_diagram.md)
