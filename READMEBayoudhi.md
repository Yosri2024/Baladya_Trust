# 🇹🇳 TuniSovereign-AI: Multi-Protocol Django 6, Agentic Swarms, MCP & Zero-Knowledge Blockchain Starter Template

> **Official DS2 Capstone Starter Template (Academic Year 2026–2027)**  
> **Course:** *AI Engineering and Software Architecture in the Era of AI and AI Agents*  
> **Target Audience:** 3rd Year Licence in Business Intelligence (`3-BI`) & Business Information Systems (`3-BIS`)  
> **Institution:** Higher Institute of Management of Tunis (**ISG Tunis**) — University of Tunis  
> **Prepared by:** Chaouki Bayoudhi  
> **Core Stack:** Python 3.11+ · Django 6 · DRF · Strawberry GraphQL · gRPC (`proto3`) · IsolationForest · FastMCP · LangGraph · Solidity (`Foundry Anvil`) · Web3.py · n8n · Streamlit

## 📅 Key Academic Dates (DS2 2026–2027)

| Milestone | Date & Time | Details |
| :--- | :--- | :--- |
| **Project Kickoff** | **Tuesday, November 10, 2026** | Start of the 4-Week Engineering Schedule |
| **Final Submission Deadline** | **Tuesday, December 8, 2026 at 23:59 (Tunis Time)** | Submit single `.zip` or `.rar` archive to `homework.isg@gmail.com` |
| **In-Class Oral Defenses** | **Wednesday, Dec 9 – Friday, Dec 11, 2026** | Live code walkthrough, parameter modification & individual Q&A |

## 🏗️ System Architecture Overview

**TuniSovereign-AI** is a 6-layer service-oriented and agentic reference architecture designed for Tunisian public-interest infrastructure across interior and coastal governorates (*Kasserine, Sidi Bouzid, Gafsa, Kairouan, Tozeur, Sfax, Béja*).

```text
+---------------------------------------------------------------------------------------------------+
|                   LAYER 6: PROGRAMMATIC COMMAND CENTER & BOUNDARY AUTOMATION                      |
|     Streamlit + Plotly Geospatial Cockpit (Port 8501)  |  n8n Boundary Webhook Workflows (5678)   |
+-------------------------------------------+-------------------------------------------------------+
                                            |
                    REST (JSON) / Strawberry GraphQL (/graphql/) / WebSockets
                                            v
+---------------------------------------------------------------------------------------------------+
|                 LAYER 1: MULTI-PROTOCOL DJANGO 6 CORE & CUSTOM JWT RBAC GATEWAY                   |
|  - StakeholderUser (4 Roles: COOP_MEMBER, REGIONAL_AUDITOR, NATIONAL_ADMIN, AGENT_SERVICE)        |
|  - DRF ViewSets + Custom SimpleJWT Claims (role, governorate, wallet_address)                     |
|  - Strawberry GraphQL Schema + DataLoader Batching (Zero N+1 SQL Queries)                         |
|  - gRPC Binary Servicer (proto3 on Port 50051) <--- Tunisian Diurnal Sensor Simulator (HMAC-SHA)  |
+-------------------+-----------------------------------+-------------------------------------------+
                    |                                   |
                    v                                   v
+---------------------------------------+   +-------------------------------------------------------+
| LAYER 2: DUAL ML ANOMALY & FORECAST   |   | LAYER 3 & 4: STATEFUL LANGGRAPH AGENT + FASTMCP       |
| - IsolationForest + Rolling Z-Score   |   | - Cyclic StateGraph (Intake -> Anomaly -> MCP Tool    |
| - Diurnal Semi-Arid / Cold-Chain Sim  |   |   -> Policy Self-Correction Gate -> ZK Prover)        |
| - Precision / Recall / F1 Harness     |   | - FastMCP Server (@mcp.resource & @mcp.tool)          |
+---------------------------------------+   | - 3 Modular Skills (Darja NLP, Anomaly, ZK Web3)      |
                                            +---------------------------+---------------------------+
                                                                        |
                                                       Web3.py + Salted SHA-256 Witness
                                                                        v
+---------------------------------------------------------------------------------------------------+
|              LAYER 5: ZERO-KNOWLEDGE PRIVACY COMMITMENTS & SOLIDITY SMART CONTRACT                |
|  TuniSovereignLedger.sol on Local Foundry Anvil (Port 8545, ChainID 31337) or Polygon Amoy        |
|  Verifies: approved_units <= max_quota on-chain without exposing private citizen/plot coordinates |
+---------------------------------------------------------------------------------------------------+
```

## 📂 Repository Structure

```text
tunisovereign_ds2_starter_template/
├── backend/
│   └── tunisovereign_core/
│       ├── models.py                      # 7 core Django 6 ORM models & custom StakeholderUser
│       ├── api_rest.py                    # DRF ViewSets, custom SimpleJWT claims & Darja webhook
│       ├── schema_graphql.py              # Strawberry GraphQL schema with DataLoader batching
│       └── ml_anomaly.py                  # IsolationForest + Rolling Z-Score & Precision/Recall/F1 harness
├── protos/
│   └── tunisovereign.proto                # Contract-first Protocol Buffers (proto3) specification
├── grpc_service/
│   └── server.py                          # Binary gRPC server (StreamTelemetry & TriggerUrgentAudit)
├── simulator/
│   └── tunisian_simulator.py              # Multi-governorate diurnal telemetry & anomaly stream generator
├── mcp_server/
│   └── tunisovereign_mcp.py               # Official Python FastMCP server (@mcp.resource & @mcp.tool)
├── agent/
│   ├── langgraph_agent.py                 # 5-node stateful LangGraph StateGraph orchestration loop
│   └── skills/
│       └── tunisovereign_skills.py        # 3 modular skills: DarjaDialectParser, TelemetryAnomaly, ZKSettlement
├── contracts/
│   ├── TuniSovereignLedger.sol            # Solidity ^0.8.20 smart contract enforcing quota compliance
│   └── web3_zk_client.py                  # Web3.py client & salted zero-knowledge commitment prover
├── workflows/
│   └── tunisovereign_n8n_boundary_workflow.json  # Ready-to-import n8n webhook & alert workflow
├── dashboard/
│   └── streamlit_command_center.py        # Interactive Streamlit + Plotly Command-Center Dashboard
├── docker-compose.yml                     # Full containerized stack (Postgres 16, Redis 7, Anvil, n8n, UI)
├── Dockerfile                             # Python 3.11 container image definition
├── requirements.txt                       # Python dependencies anchored on Django >= 6.0
├── .env.example                           # Environment template for Django, Postgres, Groq/Ollama & Web3
└── LICENSE                                # MIT License
```

## 🚀 Quickstart Guide

### Option A: Containerized Stack with Docker Compose

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Build and launch all services (PostgreSQL 16, Redis 7, Foundry Anvil EVM, n8n, and Streamlit Cockpit):**
   ```bash
   docker compose up --build
   ```

3. **Access running endpoints:**
   - **Streamlit Command Center:** `http://localhost:8501`
   - **Foundry Anvil Local EVM RPC:** `http://localhost:8545` (`ChainID: 31337`)
   - **n8n Boundary Workflow Editor:** `http://localhost:5678`

### Option B: Local Python Virtual Environment (Step-by-Step Verification)

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Compile the Protocol Buffers (`proto3`) schema into Python gRPC stubs:**
   ```bash
   python -m grpc_tools.protoc \
     -I./protos \
     --python_out=./grpc_service \
     --grpc_python_out=./grpc_service \
     ./protos/tunisovereign.proto
   ```

3. **Run the Tunisian Governorate Telemetry Simulator:**
   ```bash
   python simulator/tunisian_simulator.py
   ```

4. **Run the `IsolationForest` ML Anomaly Benchmark (`Precision`, `Recall`, `F1-Score`):**
   ```bash
   python backend/tunisovereign_core/ml_anomaly.py
   ```
   *Sample Output:*
   ```text
   ML Anomaly Evaluation Metrics: {'samples': 500, 'injected_anomalies': 40, 'detected_anomalies': 40, 'precision': 0.875, 'recall': 0.875, 'f1_score': 0.875}
   ```

5. **Execute the End-to-End Stateful `LangGraph` Agent + `FastMCP` + ZK Blockchain Settlement Loop:**
   ```bash
   python agent/langgraph_agent.py
   ```
   *Sample Output:*
   ```text
   [TuniSovereign-AI Agent | Thread ds2-kasserine-2026-001] Parsed Darja request for Kasserine (Node KAS-SBEITLA-PLOT-04). Anomaly status: CRITICAL (confidence=0.841). MCP approved 3200.0 units (<= 4200.0 max quota). Anchored ZK Commitment 0x7b98ec43b497351b... in Tx 0x3f8a901c2d4e6f8a...
   ```

6. **Launch the Interactive Command-Center Cockpit:**
   ```bash
   streamlit run dashboard/streamlit_command_center.py
   ```

## 🌍 The 8 Tunisian National Impact Tracks

Every student group (4 students) implements the unified 6-layer **Django 6** architecture applied to **Track 01 (Default Flagship)** or one of the 8 Tunisian National Impact Tracks:

| Track | Code Name | Tunisian Socio-Economic Domain & Core Mission |
| :---: | :--- | :--- |
| **Track 01** | **TunicChain-Sovereign** *(Flagship)* | Autonomous ZK Water, SONEDE/GDA Aquifer & Agricultural Cooperative Network for Interior Governorates |
| **Track 02** | **PharmaSovereign-TN** | Autonomous ZK Drug Authenticity, PCT Cold-Chain Telemetry & Anti-Shortage Protocol |
| **Track 03** | **TuniRemit-DAO** | Autonomous Diaspora Remittance-to-Capital Swarm & Regional Micro-Syndicate Engine |
| **Track 04** | **Baladiya-Trust** | Participatory Municipal Budgeting, Quadratic Funding & Geo-Verified Public Works Engine |
| **Track 05** | **Tunihara-MedGuard** | Predictive CNAM Subsidized Chronic-Care Medication Guard & Epidemiological Forecaster |
| **Track 06** | **TuniSkill-DID** | Autonomous University-to-Industry Skills-Mismatch Auditor & W3C Verifiable Credential Marketplace |
| **Track 07** | **SolarSouk-STEG** | Autonomous Agrivoltaic & Rooftop Solar Micro-Grid Balancing & ZK Carbon-Credit Cooperative |
| **Track 08** | **SoukElFallah-FairTrade** | Autonomous Olive-Oil, Dates & Cereal Anti-Speculation, Price-Stabilization & Export Traceability |

## 🗓️ Structured 4-Week Engineering Roadmap (Nov 10 – Dec 8, 2026)

- **Week 1 (Nov 10 – Nov 17, 2026) — Multi-Protocol Django 6 Foundation (`REST + GraphQL + gRPC + Auth`):**
  Initialize PostgreSQL/Redis in `docker-compose.yml`, custom `StakeholderUser` (4 roles), UML Class & Sequence Diagrams, custom `SimpleJWT` endpoints, DRF ViewSets, Strawberry GraphQL with `DataLoader`, and `grpcio` telemetry ingestion.
- **Week 2 (Nov 18 – Nov 24, 2026) — ML Anomaly Engine, Custom `FastMCP` Server & Modular Skills:**
  Implement `IsolationForest` + Rolling Statistical Z-Score anomaly detection with Precision/Recall/F1 evaluation, expose domain `@mcp.resource()` and `@mcp.tool()` endpoints via `FastMCP`, and unit-test the 3 modular Agent Skills.
- **Week 3 (Nov 25 – Dec 1, 2026) — Cyclic `LangGraph` Agent & ZK Solidity Settlement:**
  Wire the 5-node `LangGraph` state machine with policy self-correction loops, compile and deploy `TuniSovereignLedger.sol` on local Foundry Anvil, and anchor salted SHA-256 / ZK range commitments via `Web3.py`.
- **Week 4 (Dec 2 – Dec 8, 2026) — Command-Center Dashboard, `n8n` Boundary Automation & Packaging:**
  Connect the live Governorate Map, Telemetry Charts, Agent Trace Console, and On-Chain Verifier in Streamlit/Web UI, import `workflows/tunisovereign_n8n_boundary_workflow.json`, record the 5–10 min `.mp4` demo video, and submit by **Tuesday, December 8, 2026 at 23:59**.

## 📊 20-Point Evaluation Rubric Summary

| Section | Architectural Component | Points |
| :--- | :--- | :---: |
| **1** | **UML Modeling & Architectural Justification** (Class Diagram, Sequence Diagram, Protocol & Agent Comparison Matrices) | **2.50** |
| **2** | **Django 6 Core, Custom JWT RBAC & Multi-Protocol API Layer** (DRF REST + Strawberry GraphQL `DataLoader` + `gRPC` `proto3`) | **4.00** |
| **3** | **ML Anomaly Detection & Forecasting Engine** (`IsolationForest` + Z-Score/Forecasting + Precision/Recall/F1 Benchmark) | **2.50** |
| **4** | **Stateful `LangGraph` Loop, Custom `FastMCP` Server & 3 Modular Agent Skills** | **3.00** |
| **5** | **Blockchain Smart Contract (`TuniSovereignLedger.sol`) & Zero-Knowledge Privacy Layer** | **1.50** |
| **6** | **Programmatic Dashboard, Real-Time Streaming, `n8n` Boundary Automation & Docker Reproducibility** | **1.50** |
| **7** | **Individual Oral Defense, Live Code Walkthrough & Q&A Mastery** | **5.00** |
| **Total** | **DS2 Capstone Total Score** | **20.00** |

## 📬 Submission Instructions

Send a single compressed archive (`.zip` or `.rar`) to **`homework.isg@gmail.com`** before **Tuesday, December 8, 2026 at 23:59 (Tunis Time)** with the subject line:
```text
[DS2 2026-2027 - Track #X] Track Name - [Section: BI1/BI2/BIS1/BIS2] - [Group Number & Members]
```
Your archive must include:
1. Complete executable source code, `docker-compose.yml`, and `README.md`.
2. Presentation slides (`.pptx` and `.pdf`) containing your UML diagrams, architecture diagrams, comparison matrices, screenshots, and F1 evaluation metrics.
3. A 5–10 minute end-to-end demonstration video (`.mp4`).

**Author & Coordinator:** Chaouki Bayoudhi — Higher Institute of Management of Tunis (ISG Tunis), University of Tunis.
