# Baladiya-Trust UML

## Class diagram

```mermaid
classDiagram
    class StakeholderUser {
        +int id
        +string username
        +string role
        +string municipality
        +string wallet_address
        +string residency_commitment
        +string preferred_dialect
    }

    class Municipality {
        +UUID id
        +string name
        +string governorate
        +float total_budget_tnd
        +float matching_pool_tnd
        +string contract_address
    }

    class Proposal {
        +int id
        +string project_code
        +string title
        +string text
        +string language
        +string category
        +string cluster_id
        +float estimated_cost_tnd
        +string status
        +datetime created_at
    }

    class Vote {
        +int id
        +string voter_hash
        +float amount_tnd
        +datetime created_at
    }

    class MilestoneReport {
        +int id
        +datetime timestamp
        +float progress_pct
        +float paid_pct
        +string photo_hash
        +float latitude
        +float longitude
        +string ingestion_protocol
    }

    class Tranche {
        +int id
        +int index
        +float amount_tnd
        +datetime released_at
    }

    class AnomalyEvent {
        +int id
        +datetime detected_at
        +string kind
        +string severity
        +float isolation_forest_score
    }

    class AgentLoopExecution {
        +int id
        +string thread_id
        +string trigger_source
        +text darja_transcript
        +json parsed_intent_json
        +json mcp_tools_invoked
        +json skills_executed
        +text final_recommendation
        +float confidence_score
        +datetime created_at
    }

    class OnChainZKReceipt {
        +int id
        +string zk_commitment_hash
        +json public_inputs_json
        +string tx_hash
        +int block_number
        +string network_name
        +bool is_verified_on_chain
    }

    StakeholderUser "1" --> "*" Proposal : author
    Municipality "1" --> "*" Proposal : hosts
    Proposal "1" --> "*" Vote : receives
    Proposal "1" --> "*" MilestoneReport : reports
    Proposal "1" --> "*" Tranche : releases
    Proposal "1" --> "*" AnomalyEvent : flags
    AgentLoopExecution "1" --> "0..1" OnChainZKReceipt : anchors
    Tranche "0..1" --> "*" OnChainZKReceipt : settles

    note for Proposal "project_code is unique"
    note for Vote "UniqueConstraint(proposal, voter_hash)"
    note for Tranche "UniqueConstraint(proposal, index)"
    note for OnChainZKReceipt "zk_commitment_hash and tx_hash are unique"
```

## Proposal-to-payout sequence

```mermaid
sequenceDiagram
    autonumber
    actor C as Citizen
    participant API as Django REST / GraphQL
    participant DB as PostgreSQL
    participant G as gRPC Ingest
    participant ML as ML Detector
    participant A as LangGraph Agent
    participant M as BaladiyaTreasuryMCP
    participant Z as ZK Skill
    participant W as Web3 / BaladiyaLedger

    C->>API: POST /api/auth/register/ then /api/auth/token/
    API->>DB: Create StakeholderUser
    API-->>C: JWT with role, municipality, wallet

    C->>API: POST /api/v1/proposals/
    API->>DB: Proposal(status=SUBMITTED)
    C->>API: POST /api/v1/votes/
    API->>DB: Vote(voter_hash, amount_tnd)
    Note over API,DB: QF matching = (sum sqrt(c_i))^2 - sum c_i

    G->>G: Verify HMAC milestone packet
    G->>DB: MilestoneReport(progress_pct, paid_pct, photo_hash)
    G->>ML: evaluate_progress_lag()
    ML-->>G: severity and score

    alt lag above 20 or statistical anomaly
        G->>DB: Create AnomalyEvent
        G->>A: Trigger agent with thread_id
    else compliant milestone
        G-->>G: Accept packet without agent
    end

    A->>M: get_municipality_treasury()
    M->>DB: Read budgets, votes, tranches
    M-->>A: Treasury and matching snapshot
    A->>M: compute_quadratic_funding()
    M-->>A: Matching amount and pool cap
    A->>M: check_tranche_eligibility()
    M-->>A: Eligible or blocking reasons

    alt eligible and human approval
        A->>Z: Create salted ZK commitment
        Z-->>A: zk_commitment_hash
        A->>W: releaseTranche(proposal, index, commitment)
        W-->>A: tx_hash and block_number
        A->>DB: OnChainZKReceipt
        API->>DB: GraphQL reads receipt
        API-->>C: tx_hash and project status
    else blocked
        A->>DB: Hold tranche / record anomaly
        A-->>C: Explain blocking reason
    end
```

The Web3/ZK release is the target flow implemented in the blockchain week; REST, GraphQL, gRPC,
ML, MCP and the model relations above are already in the repository.
