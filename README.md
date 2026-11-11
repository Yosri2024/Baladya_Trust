# Baladiya-Trust — DS2 Capstone 2026–2027

> **Track 4:** Participatory Municipal Budgeting, Quadratic Funding and Geo-Verified Public Works
> **Course:** AI Engineering and Software Architecture in the Era of AI and AI Agents
> **Institution:** Higher Institute of Management of Tunis (ISG Tunis) — University of Tunis
> **Target cohort:** 3rd Year Business Intelligence (3-BI) & Business Information Systems (3-BIS)
> **Deadline:** Tuesday, December 8, 2026 at 23:59 (Tunis time)
> **Defenses:** December 9–11, 2026

This repository is our group's implementation of **Baladiya-Trust**, built on the official
`tunisovereign-ds2-starter-template` by Chaouki Bayoudhi. The original course template is kept in
[`READMEBayoudhi.md`](./READMEBayoudhi.md) for reference.

## Team

| Member | Role | Owns |
| :--- | :--- | :--- |
| _TBD_ | M1 — Backend | Django models, JWT/RBAC, REST, GraphQL, gRPC, Docker base |
| _TBD_ | M2 — Data & ML | Simulator, IsolationForest, clustering, Precision/Recall/F1 |
| _TBD_ | M3 — Agent | LangGraph, FastMCP, 3 skills, Groq/Ollama, tests |
| _TBD_ | M4 — Chain & UI | Solidity, Web3.py, ZK commitments, Streamlit, n8n, README/video |

## The problem

Citizens in Tunisian municipalities often lack visibility into how local budgets are allocated and
whether public works are actually progressing. Proposals are duplicated, contractor progress is hard
to verify, and payments can be released without objective evidence.

## What we are building

A platform where citizens submit municipal project proposals (roads, lighting, schools, waste
collection) in Tunisian Darja or French, and public money is allocated and released transparently:

1. **Duplicate proposals are merged** using multilingual embeddings and clustering.
2. **Budget is allocated with quadratic funding**, which rewards projects with many small supporters
   over a few large donors.
3. **Contractor progress is audited**: milestone photos, GPS and progress data are compared with the
   amount already paid.
4. **Funds are released in tranches through a smart contract**, and every release is recorded on-chain.
5. **Privacy is preserved**: voters prove residency through a salted cryptographic commitment and a
   non-transferable voter token, without revealing identity or address.

## Architecture

The project follows the unified 6-layer DS2 architecture, adapted to Track 4:

| Layer | Baladiya-Trust implementation |
| :--- | :--- |
| 1. Backend & auth | Django 6, custom `StakeholderUser` with 4 roles, JWT (SimpleJWT) |
| 2. Multi-protocol APIs | REST (DRF), Strawberry GraphQL with DataLoader, gRPC (proto3) |
| 3. Real-time & UI | Django Channels (SSE/WebSocket), Streamlit + Plotly + Folium |
| 4. Agent | Stateful LangGraph `StateGraph` with PostgreSQL checkpoints and human approval |
| 5. MCP & skills | `BaladiyaTreasuryMCP` + 3 modular Python skill classes |
| 6. Blockchain & ZK | `BaladiyaLedger.sol` + soulbound voter registry, Web3.py, salted commitments |

### End-to-end flow

```text
Citizen (Darja/FR) --REST--> /api/v1/proposals/
Simulator --gRPC--> StreamMilestones --> Django (MilestoneReport)
                                              |
                LangGraph (thread_id + PostgreSQL checkpoint)
  intake -> dedup -> matching(MCP) -> milestone_check(ML) -> policy_gate
                                          | PASS                  | FAIL
                                       zk_prove                replan
                                          |                (hold tranche,
                                       settle               alert auditor)
                                          |
                        Web3.py -> BaladiyaLedger.sol (Anvil)
                                          |
                       OnChainZKReceipt (tx_hash) -> GraphQL -> Streamlit
```

**Rule:** the LLM is used only for language tasks (Darja parsing, explanations, routing). Money,
thresholds and hashing stay deterministic Python and are unit-tested.

## Repository structure

```text
baladiya-trust/
├── agent/
│   ├── langgraph_agent.py          # LangGraph StateGraph (to replace starter sequential function)
│   └── skills/                     # 3 modular skills + pytest
├── backend/tunisovereign_core/
│   ├── models.py                   # Track 4 domain models
│   ├── api_rest.py                 # DRF ViewSets, JWT auth, Darja webhook
│   ├── schema_graphql.py           # Strawberry schema + real DataLoader
│   └── ml_anomaly.py               # IsolationForest + rolling z-score + P/R/F1
├── config/                         # Django project (to be created)
├── contracts/
│   ├── BaladiyaLedger.sol          # Tranche release + soulbound voter registry
│   ├── web3_zk_client.py           # Real Web3.py transactions (to replace simulated tx)
│   └── deploy.py                   # Deploy script (to be created)
├── dashboard/                      # Streamlit command center
├── grpc_service/                   # gRPC servicer + generated stubs
├── mcp_server/                     # BaladiyaTreasuryMCP
├── protos/baladiya.proto           # Contract-first gRPC definition
├── simulator/                      # Reproducible Tunisian municipality simulator
├── workflows/                      # n8n boundary workflow
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md                       # This file
└── READMEBayoudhi.md               # Original course starter README
```

## Current status

_Last updated: 2026-11-11_

The repository currently contains the **unmodified course starter** (Track 1 water/agriculture
stubs). No Baladiya-Trust functionality has been implemented yet.

| Area | Status | Notes |
| :--- | :---: | :--- |
| Fork + local clone + upstream remote | Done | `origin` = Yosri2024 fork, `upstream` = professor repo |
| Environment check | Done | Python 3.14.10, Docker 29.9.3, Compose v5.5.1 |
| Django project scaffold (`config/`, `manage.py`, apps, migrations) | Not started | Guide §5.1 |
| Track 4 models (`Municipality`, `Proposal`, `Vote`, `MilestoneReport`, `Tranche`, …) | Not started | Guide §5.2 |
| JWT auth + 4-role RBAC + register | Not started | Guide §5.3 |
| REST ViewSets, filters, validation | Not started | Guide §5.3 |
| Strawberry GraphQL + real DataLoader | Not started | Guide §5.4 |
| gRPC `baladiya.proto` + registered servicer | Not started | Guide §5.5 |
| Simulator + anomaly injection + labels CSV | Not started | Guide §5.6 |
| ML sybil/progress/photo detectors + P/R/F1 | Not started | Guide §5.7 |
| `BaladiyaTreasuryMCP` resources and tools | Not started | Guide §5.8 |
| 3 skills with pytest | Not started | Guide §5.9 |
| LangGraph `StateGraph` + PostgresSaver + interrupt | Not started | Guide §5.10 |
| `BaladiyaLedger.sol` + Foundry tests + real Web3.py | Not started | Guide §5.11 |
| Dashboard (map, charts, agent trace, tx verifier) | Not started | Guide §5.12 |
| Django Channels SSE/WebSocket + n8n alerts | Not started | Guide §5.12 |
| Docker Compose: backend + grpc + corrected hosts | Not started | Guide §5.12 |
| Tests, UML, slides, video, archive | Not started | Guide §7 |

## Roadmap

### Week 1 — Django foundation and three APIs (Nov 10–17)

- [ ] Create `config/` project, `apps.py`, `__init__.py` files, PostgreSQL settings.
- [ ] Rewrite `models.py` for Baladiya-Trust, run migrations.
- [ ] Draw UML class diagram and proposal-to-payout sequence diagram.
- [ ] Implement register/login/refresh JWT with `role`, `municipality`, `wallet_address`.
- [ ] Implement `IsCitizen`, `IsMunicipalAuditor`, `IsNationalAdmin`; test 200 vs 403.
- [ ] Implement DRF ViewSets for proposals, votes, milestones, anomalies, receipts.
- [ ] Fix Darja webhook authentication (no `AllowAny`).
- [ ] Implement nested GraphQL schema and real DataLoader; test query count.
- [ ] Create `baladiya.proto`, generate stubs, register `MilestoneIngestServiceServicer`.
- [ ] Integration check: register, login, proposal, GraphQL query, gRPC packet. Tag `v0.1`.

### Week 2 — Simulator, ML, MCP and skills (Nov 18–24)

- [ ] Simulator: proposals in French/Darja with duplicates, votes, S-curve milestones, fixed seed.
- [ ] Inject sybil bursts, progress lag > 20 points, reused photo hash; export CSV with labels.
- [ ] IsolationForest sybil detector + rolling z-score + deterministic lag rule.
- [ ] Wire detectors to Django signals/tasks writing `AnomalyEvent`.
- [ ] Implement `BaladiyaTreasuryMCP` (2 resources, 3 tools) and test with MCP Inspector.
- [ ] Implement `DarjaProposalClustererSkill` with Groq normalization + embeddings.
- [ ] Implement `QuadraticFundingMathSkill` and `ZKSoulboundResidencyVoterSkill` with tests.
- [ ] Stream milestones over gRPC; verify anomalies appear in DB and GraphQL. Tag `v0.2`.

### Week 3 — LangGraph and blockchain/ZK (Nov 25–Dec 1)

- [ ] Build `StateGraph` skeleton with conditional edges and stub nodes.
- [ ] Replace stubs with Groq JSON + Pydantic, skills, MCP client, Ollama fallback.
- [ ] Add PostgresSaver checkpointing and `interrupt_before=["settle"]`.
- [ ] Test resume after process stop; persist every run in `AgentLoopExecution`.
- [ ] Write `BaladiyaLedger.sol` + `forge test` + Anvil service + `deploy.py`.
- [ ] Real Web3.py `releaseTranche`, receipts stored in `OnChainZKReceipt`, revert handling.
- [ ] Residency commitment registration; reject duplicate voter commitments.
- [ ] End-to-end nominal and blocked (25% lag) scenarios. Tag `v0.3`.

### Week 4 — Dashboard, automation, packaging (Dec 2–8)

- [ ] Streamlit: municipality map, Plotly charts, agent trace console, tx verifier.
- [ ] Auditor approval button resuming the checkpoint.
- [ ] Django Channels SSE/WebSocket for live anomalies and receipts.
- [ ] n8n: inbound Telegram/webhook to `/api/v1/darja-intent/`, outbound alerts.
- [ ] Docker Compose one-command startup (Django, Postgres, Redis, Anvil, n8n, gRPC, dashboard).
- [ ] Rewrite README with final architecture, setup, API examples.
- [ ] Record 5–10 min demo video, prepare `.pptx` and `.pdf` slides.
- [ ] Submit archive to `homework.isg@gmail.com` before the deadline.

## Getting started (work in progress)

The Django project is not created yet. Once the scaffold from Guide §5.1 is in place, the target
startup procedure will be:

```bash
cp .env.example .env        # never commit .env
docker compose up --build
```

Local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Tests

Planned minimum test set (pytest / pytest-django):

- Auth: citizen gets 403 on `/anomalies/`, auditor gets 200, JWT contains `role` and `municipality`.
- GraphQL: nested municipality → proposals → votes keeps a constant SQL query count.
- Quadratic funding: 100 × 1 TND = 9,900; 1 × 100 TND = 0; insufficient pool is normalized.
- ML: F1 above a fixed threshold on the seeded simulated dataset.
- ZK skill: same input + salt = same commitment; different salt = different commitment.
- Contract: release succeeds; low progress is rejected; duplicate commitment/voter is rejected.
- Agent: 25% lag routes through `replan` and sends no transaction.

## Submission checklist

- [ ] `docker compose up` works on a clean machine.
- [ ] No `.env` or API keys in the archive (keep `.env.example`).
- [ ] README rewritten for Baladiya-Trust.
- [ ] UML diagrams match the real code.
- [ ] Precision/Recall/F1 table from our own simulated data.
- [ ] Slides `.pptx` and `.pdf`, video `.mp4` (5–10 minutes).
- [ ] Archive sent before **December 8, 2026 at 23:59**.

## Credits

Based on the official DS2 starter template by **Chaouki Bayoudhi** (ISG Tunis):
[`tunisovereign-ds2-starter-template`](https://github.com/ChaoukiBayoudhi/tunisovereign-ds2-starter-template).
The original README is preserved in [`READMEBayoudhi.md`](./READMEBayoudhi.md).
