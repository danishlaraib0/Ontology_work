# 🚗 Automotive World Model: Complete System Guide

A clear, non-technical explanation of the **Automotive World Model** architecture, how each file and module works, how data flows through the system, and step-by-step walkthroughs of user journeys.

---

## 📌 Table of Contents
1. [What is this Project? (The Big Picture)](#1-what-is-this-project-the-big-picture)
2. [Directory & Module Structure (What Files Do)](#2-directory--module-structure-what-files-do)
3. [What We Do & How We Do It (Under the Hood)](#3-what-we-do--how-we-do-it-under-the-hood)
4. [Step-by-Step User Flows](#4-step-by-step-user-flows)
   - [Flow 1: Adding a Car from the UI](#flow-1-adding-a-car-from-the-ui)
   - [Flow 2: Asking an Intelligence Query](#flow-2-asking-an-intelligence-query)
   - [Flow 3: Running a Decision Simulation](#flow-3-running-a-decision-simulation)
5. [Common Questions & FAQ](#5-common-questions--faq)

---

## 1. What is this Project? (The Big Picture)

The **Automotive World Model** is an enterprise AI decision intelligence platform for the automotive industry (currently focused on passenger vehicles in India, such as Maruti Suzuki Dzire, Honda Amaze, Hyundai Aura, and Tata Punch).

### The Problem It Solves:
Traditional automotive executives rely on fragmented spreadsheets, delayed monthly reports (SIAM wholesale dispatches, VAHAN registrations), and guesswork to understand competitor moves, buyer dissatisfaction, and pricing strategy.

### The Solution:
Instead of just being a standard chatbot that makes up answers, this system builds a **living digital twin (Knowledge Graph)** of the automotive market inside **Neo4j**:
- It tracks specifications, prices, customer complaints, buyer personas, and competitor rivalries as interconnected nodes.
- When an executive asks a question (like *"What are the key gaps in Hyundai Aura?"* or *"What happens if Dzire cuts price by ₹30,000?"*), the system parses the intent, queries verified facts from the graph, runs mathematical market simulations, and generates a grounded executive briefing backed by real evidence.
- It allows users to onboard any new car autonomously from the web UI with real-time status visibility.

---

## 2. Directory & Module Structure (What Files Do)

Here is a simple map of all folders and key files in the codebase:

```
Ontology/
├── data_collector/       # 📡 Gathers 12 layers of automotive intelligence
├── graph_db/             # 🧠 Neo4j graph schemas, constraints, and loaders
├── intelligence/         # ⚡ AI Query planner, Cypher generator, and reasoning
├── decisions/            # ⚖️ Strategic simulations, counterfactuals, and approvals
├── ingestion/            # 🔄 Background vehicle onboarding and status tracking
├── ui/                   # 🖥️ Web dashboard (HTML, CSS, JS)
├── observability/        # 🔒 Tamper-evident cryptographic audit log
├── api.py                # 🌐 FastAPI web server
└── cli.py                # ⌨️ Command-line interface for terminal users
```

### Detailed Breakdown by Module:

### 1. `data_collector/` — The 12-Tier Data Harvester
Collects deep information for any car across 12 structured tiers and saves them as JSON files in `data_collector/output/<brand>/<model>/`.
- [collector.py](file:///home/immortal/Desktop/Ontology/data_collector/collector.py): Main orchestrator that runs the 12 collection layers sequentially with rate pacing and progress callbacks.
- [layers.py](file:///home/immortal/Desktop/Ontology/data_collector/layers.py): Implements each specific layer:
  - **L01: Vehicle Master** (brand, model, launch year, segment, body type).
  - **L02: Spec Master** (engines, transmissions, fuel types, mileage, dimensions).
  - **L03: Feature Taxonomy** (safety features, ADAS, touchscreen, sunroof).
  - **L04: Competitor Master** (direct rivals, price overlap, cross-shopping).
  - **L05: Audience Segments** (buyer profiles: Daily Commuter, Young Families).
  - **L06: Buying Factors** (mileage, safety, reliability, resale value).
  - **L07: Reviews** (expert feedback from AutoCar, ZigWheels, MotorBeam).
  - **L08: Opinion Dataset** (customer complaints, sentiment, verified pros/cons).
  - **L09: Search Intent** (common Google search questions and queries).
  - **L10: Sales Volume** (monthly dispatch figures and market share).
  - **L11: Pricing Data** (ex-showroom variant price ladder).
  - **L12: Ontology Summary** (executive intelligence card).
- [storage.py](file:///home/immortal/Desktop/Ontology/data_collector/storage.py): Manages local caching and JSON persistence so data is never needlessly re-fetched.

---

### 2. `graph_db/` — The Neo4j Brain
Connects to Neo4j and transforms raw JSON datasets into a unified knowledge graph.
- [connection.py](file:///home/immortal/Desktop/Ontology/graph_db/connection.py): Manages database connection pool and credentials.
- [schema.py](file:///home/immortal/Desktop/Ontology/graph_db/schema.py): Enforces database constraints and unique indexes (e.g., uniqueness on `VehicleModel.name`, `Variant.variant_id`).
- [loader.py](file:///home/immortal/Desktop/Ontology/graph_db/loader.py): Reads collected JSON files and creates nodes (`VehicleModel`, `Competitor`, `Segment`, `Feature`, `PriceObservation`, `Opinion`) and relationships (`COMPETES_WITH`, `TARGETS_SEGMENT`, `HAS_OPINION`).

---

### 3. `intelligence/` — The AI Query Planner & Reasoning Engine
Translates human questions into accurate answers without hallucinating.
- [dynamic_query_engine.py](file:///home/immortal/Desktop/Ontology/intelligence/dynamic_query_engine.py): The main coordinator that takes a query string, triggers the planner, executes graph queries, and formats the executive report.
- [query_planner.py](file:///home/immortal/Desktop/Ontology/intelligence/query_planner.py): Intent classifier using a hybrid approach:
  - **Fast-Path Rules**: Instant keyword matching for known cars and standard questions (0ms latency, 100% deterministic).
  - **LLM Fallback**: Uses LLM when queries are complex or phrased unusually.
- [schema_registry.py](file:///home/immortal/Desktop/Ontology/intelligence/schema_registry.py): Whitelist registry that ensures the AI only queries known labels and properties that actually exist in Neo4j.
- [cypher_generator.py](file:///home/immortal/Desktop/Ontology/intelligence/cypher_generator.py): Translates complex queries into read-only Neo4j Cypher code and validates it against security rules (blocks all `DELETE`, `MERGE`, or `DROP` operations).

---

### 4. `decisions/` — Strategy, Simulation & Governance
Simulates the business impact of pricing and product changes.
- [engine.py](file:///home/immortal/Desktop/Ontology/decisions/engine.py): Simulates price elasticity, volume impact, and competitor cross-shopping effects.
- [approval_service.py](file:///home/immortal/Desktop/Ontology/decisions/approval_service.py): "Four-eyes" approval workflow (requires authorized sign-off before any recommended strategy is executed).
- [action_bridge.py](file:///home/immortal/Desktop/Ontology/decisions/action_bridge.py): Connects approved proposals to execution logs, separating real catalog changes from observational data.
- [evaluation.py](file:///home/immortal/Desktop/Ontology/decisions/evaluation.py): Compares past decisions against subsequent market sales to measure whether expectations were met.

---

### 5. `ingestion/` — Ingestion Manager & Status Tracker
- [ingestion_manager.py](file:///home/immortal/Desktop/Ontology/ingestion/ingestion_manager.py): Background job manager. Tracks vehicle onboarding status (`QUEUED` ➔ `RUNNING` ➔ `COMPLETED` / `FAILED`), percentage progress (5% ➔ 100%), live log streaming, and graph node counts.

---

### 6. `ui/` & `api.py` — Web Dashboard & Server
- [index.html](file:///home/immortal/Desktop/Ontology/ui/index.html): Dark glassmorphic interface with top status badge, graph traversal visualizer, markdown report display, and the multi-state "+ Add Vehicle" modal.
- [style.css](file:///home/immortal/Desktop/Ontology/ui/style.css): Polished CSS tokens, animations, pulse dots, log terminal styling, and responsive layout.
- [app.js](file:///home/immortal/Desktop/Ontology/ui/app.js): Client-side controller handling query submissions, dynamic `/api` routing, modal interactions, and polling with runaway safeguards.
- [api.py](file:///home/immortal/Desktop/Ontology/api.py): FastAPI web server serving static UI assets and exposing REST APIs (`/api/query`, `/api/add_car`, `/api/ingestion_status/{job_id}`, `/api/ingestion_jobs`).

---

### 7. `observability/` — Security & Audit
- [audit_log.py](file:///home/immortal/Desktop/Ontology/observability/audit_log.py): Cryptographic SHA-256 tamper-evident hash chain logging every decision, query, and administrative action.

---

## 3. What We Do & How We Do It (Under the Hood)

```
        ┌────────────────────────────────────────────────────────┐
        │                 USER / EXECUTIVE                        │
        └──────────────┬──────────────────────────┬──────────────┘
                       │                          │
        1. Query Market Intelligence        2. Onboard New Vehicle
                       │                          │
                       ▼                          ▼
        ┌──────────────────────────────┐   ┌──────────────────────────────┐
        │   Dynamic Query Engine       │   │      Ingestion Manager       │
        │ • Intent Planning (FastPath) │   │ • Background Thread Worker   │
        │ • Read-Only Cypher Safety    │   │ • 12 Data Layers Extracted   │
        └──────────────┬───────────────┘   └──────────────┬───────────────┘
                       │                                  │
                       └──────────────┬───────────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │     Neo4j Knowledge Graph    │
                       │ • Models, Variants, Specs    │
                       │ • Opinions, Segments, Rela   │
                       └──────────────┬──────────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ Grounded Executive Synthesis │
                       │ Facts vs. Assumptions Ledger │
                       └──────────────────────────────┘
```

### The Three Pillars of Execution:

1. **Deterministic Fast-Paths First**:
   Instead of asking an LLM to guess everything, standard queries (like *"gaps in aura"* or *"compare amaze and aura"*) are recognized instantly by predefined domain fast-paths. This eliminates hallucinations, reduces cost, and returns results in milliseconds.

2. **Graph-Grounded Evidence**:
   Every claim the AI produces comes from actual nodes in Neo4j. If the AI says *"Hyundai Aura has NVH issues"*, it links directly to opinion nodes extracted from real customer and expert reviews.

3. **Governed Decision-Making**:
   Decisions (such as changing prices or altering variants) must follow a rigorous lifecycle:
   `Proposal` ➔ `Counterfactual Simulation` ➔ `4-Eyes Human Approval` ➔ `Audit Log` ➔ `Observed Outcome Validation`.

---

## 4. Step-by-Step User Flows

### Flow 1: Adding a Car from the UI
```
[User clicks "+ Add Vehicle"]
               │
               ▼
[Enters Make & Model or Clicks Quick-Pick Chip (e.g. Tata Punch)]
               │
               ▼
[Clicks "🚀 Start Autonomous Ingestion"]
               │
               ▼
[Modal transforms into Live Status Screen]
├── Glowing animated progress bar (5% ➔ 100%)
├── Active step indicator (e.g. "Layer 4/12: Competitor Master")
└── Timestamped streaming terminal logs
               │
               ▼
[Background: IngestionManager runs 12-layer extraction + Neo4j merge]
               │
               ▼
[Modal reaches COMPLETED (100%)]
├── Shows merged statistics (e.g. +167 nodes, +400 relationships)
└── Displays "🎯 Query this Car Now" button (Click to immediately analyze!)
```

---

### Flow 2: Asking an Intelligence Query
```
[User types question into Query Dock (e.g. "gaps in aura")]
               │
               ▼
[Submits form or presses Enter]
               │
               ▼
[UI Step 1: Query Planner identifies intent & selected tool]
               │
               ▼
[UI Step 2: Animated Graph Traversal displays paths traversed in Neo4j]
               │
               ▼
[UI Step 3: Executive Markdown Report renders]
├── Grounded Findings (Verified metrics)
├── Strategic Product Analysis
└── Assumptions & Uncertainty Ledger
```

---

### Flow 3: Running a Decision Simulation (CLI / API)
```
[Executive Proposes Action: "Cut Dzire ZXi price by ₹30,000"]
               │
               ▼
[Decision Engine evaluates cross-shopping & segment price elasticity]
               │
               ▼
[Simulated Scenario Result: +1,240 volume/mo, net revenue impact]
               │
               ▼
[Governance Check: Requires 2-person executive approval]
               │
               ▼
[Approved action logged to Cryptographic Audit Hash Chain]
```

---

## 5. Common Questions & FAQ

### Q1: Why use a Graph Database (Neo4j) instead of normal SQL or Vector DB?
**Answer:** The automotive market is defined by **relationships**, not isolated rows. A vehicle is connected to *competitors* by price brackets, to *customer opinions* by sentiment, and to *buyer segments* by preferences. Neo4j allows multi-hop traversals (e.g., finding which competitor steals sales when a specific safety feature is missing) in a single millisecond query, which would require dozens of slow table joins in SQL.

### Q2: Does the AI make up (hallucinate) numbers or queries?
**Answer:** No. We use a **guardrailed dual-track architecture**:
1. Most common inquiries use deterministic fast-paths with pre-tested Cypher queries.
2. When dynamic Cypher is generated, it passes through an AST (Abstract Syntax Tree) validator that rejects write commands (`DELETE`, `MERGE`, `DROP`), enforces query limits (`LIMIT 50`), and checks against an explicit schema whitelist.
3. In the final report, verified graph facts are strictly separated from modeling assumptions.

### Q3: What happens when I click "+ Add Vehicle" in the UI?
**Answer:** The UI sends a `POST /api/add_car` request. The backend registers a job and runs the 12-layer collector in a non-blocking background thread. Each layer pulls specifications, reviews, sales, and taxonomy, caches them to disk, and merges the nodes directly into Neo4j. The UI polls `/api/ingestion_status/{job_id}` every 1.5 seconds to display real-time terminal logs.

### Q4: Why does adding a car take ~30 seconds?
**Answer:** Quality and rate limits. The data collector extracts 12 distinct intelligence tiers. To avoid triggering search engine rate limits or IP bans (15 requests/minute), the pipeline spaces each tier with safe rate pacing (~2.5s per layer). If data for that car is already cached locally, it loads almost instantly.

### Q5: How do I run and access the application?
**Answer:**
1. Ensure Neo4j is running on your machine (`localhost:7687`).
2. Start the API server:
   ```bash
   python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Open your browser and navigate to:
   - **http://localhost:8000/** (Web Dashboard)
4. (Optional) Run queries directly in your terminal:
   ```bash
   python3 cli.py
   ```

### Q6: Can the AI change live car prices in real life automatically?
**Answer:** Never. The system enforces strict governance separation:
- `PriceObservation`: Historical or observed public prices.
- `ActionProposal`: Hypothetical business actions.
- `ApprovalRecord`: Requires dual executive authorization (4-eyes principle) before any change proposal can be marked approved. Real-world execution is always insulated by authorization gates.

### Q7: Why were there two ports (8000 and 3000)? Which one should I use?
**Answer:**
- **Port 8000** is the main FastAPI server which serves **both** the API and the web interface. **Always use Port 8000.**
- Port 3000 was only a temporary standalone static server (`python3 -m http.server 3000`). We configured the frontend JavaScript so that whether you visit port 8000 or port 3000, it automatically and dynamically connects to the correct API backend.

### Q8: What happens if an ingestion fails or the network drops?
**Answer:**
The system captures the exact error in the background worker, sets the job status to `FAILED`, logs the error message in the terminal window in red, and stops the polling loop so the browser does not hang or freeze. You can click "+ Add Another" or retry anytime.

### Q9: How do I test the system without using the web UI?
**Answer:**
You can run automated test suites and validation scripts directly from the terminal:
```bash
# Test ingestion tracking and status lifecycle:
python3 -m unittest evaluation/test_ingestion_manager.py

# Test decision governance and world model validation:
python3 -m unittest evaluation/test_validation_fixes.py

# Test dynamic queries:
python3 -m unittest evaluation/test_dynamic_query.py
```

### Q10: Where is the data stored on my disk?
**Answer:**
- **Collected raw JSON data**: Saved in `data_collector/output/<brand>/<model>/`.
- **Ingestion job history**: Saved in `data_collector/output/ingestion_jobs.json`.
- **Graph Database**: Stored in your local Neo4j instance at `bolt://localhost:7687`.
- **Cryptographic Audit Logs**: Saved in `observability/audit_log.json`.
