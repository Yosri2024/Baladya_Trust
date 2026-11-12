import json
import uuid
from datetime import datetime, timezone

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from rest_framework_simplejwt.tokens import AccessToken

from backend.tunisovereign_core.models import (
    AgentLoopExecution,
    MilestoneReport,
    Municipality,
    OnChainZKReceipt,
    Proposal,
    StakeholderUser,
    Tranche,
    Vote,
)


@pytest.fixture
def auditor_headers(db):
    auditor = StakeholderUser.objects.create_user(
        username="graphql-auditor",
        password="Auditor-pass-2026!",
        role=StakeholderUser.Role.MUNICIPAL_AUDITOR,
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(auditor)}"}


@pytest.fixture
def graphql_data(db):
    author = StakeholderUser.objects.create_user(username="graphql-author", password="test")
    kasserine = Municipality.objects.create(
        name="Kasserine",
        governorate="Kasserine",
        total_budget_tnd=1_200_000,
        matching_pool_tnd=150_000,
    )
    sidi_bouzid = Municipality.objects.create(
        name="Sidi Bouzid",
        governorate="Sidi_Bouzid",
        total_budget_tnd=1_000_000,
        matching_pool_tnd=120_000,
    )
    road = Proposal.objects.create(
        municipality=kasserine,
        author=author,
        project_code="KAS-ROAD-001",
        title="Réparer la route de Sbeitla",
        text="Route dégradée",
        category="ROAD",
    )
    school = Proposal.objects.create(
        municipality=kasserine,
        author=author,
        project_code="KAS-SCHOOL-001",
        title="Rénover l'école",
        text="École primaire",
        category="SCHOOL",
    )
    waste = Proposal.objects.create(
        municipality=sidi_bouzid,
        author=author,
        project_code="SBZ-WASTE-001",
        title="Collecte des déchets",
        text="Déchets ménagers",
        category="WASTE",
    )

    for index, proposal in enumerate((road, road, school, waste), start=1):
        Vote.objects.create(
            proposal=proposal,
            voter_hash="0x" + f"{index:064x}",
            amount_tnd=5 + index,
        )

    MilestoneReport.objects.create(
        proposal=road,
        timestamp=datetime.now(timezone.utc),
        progress_pct=40,
        paid_pct=55,
        photo_hash="a" * 64,
        latitude=35.0,
        longitude=8.0,
    )
    tranche = Tranche.objects.create(proposal=road, index=1, amount_tnd=1000)
    execution = AgentLoopExecution.objects.create(
        thread_id="graphql-test",
        trigger_source="pytest",
        final_recommendation="ok",
        confidence_score=0.9,
    )
    unique = uuid.uuid4().hex
    OnChainZKReceipt.objects.create(
        agent_execution=execution,
        tranche=tranche,
        zk_commitment_hash="0x" + unique,
        tx_hash="0x" + unique[::-1],
        block_number=1,
    )
    return {"road": road, "school": school, "waste": waste}


@pytest.mark.django_db
def test_nested_query_is_batched_under_four_queries(graphql_data, auditor_headers):
    query = """
    query {
      municipalities {
        name
        proposals {
          projectCode
          votesCount
          raisedTnd
          votes { amountTnd }
          milestones { progressPct }
        }
      }
    }
    """
    client = Client()
    with CaptureQueriesContext(connection) as captured:
        response = client.post(
            "/graphql/",
            data=json.dumps({"query": query}),
            content_type="application/json",
            **auditor_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("errors") is None
    # 1 query to load the authenticated user + 4 batched data queries (no N+1)
    assert len(captured.captured_queries) <= 5

    municipalities = {row["name"]: row for row in body["data"]["municipalities"]}
    assert set(municipalities) == {"Kasserine", "Sidi Bouzid"}

    kasserine_proposals = {
        row["projectCode"]: row for row in municipalities["Kasserine"]["proposals"]
    }
    assert kasserine_proposals["KAS-ROAD-001"]["votesCount"] == 2
    assert kasserine_proposals["KAS-ROAD-001"]["raisedTnd"] == 13.0
    assert len(kasserine_proposals["KAS-ROAD-001"]["votes"]) == 2
    assert len(kasserine_proposals["KAS-ROAD-001"]["milestones"]) == 1
    assert kasserine_proposals["KAS-SCHOOL-001"]["votesCount"] == 1

    assert municipalities["Sidi Bouzid"]["proposals"][0]["projectCode"] == "SBZ-WASTE-001"


@pytest.mark.django_db
def test_receipts_are_loaded_through_tranches(graphql_data, auditor_headers):
    query = """
    query {
      proposal(projectCode: "KAS-ROAD-001") {
        tranches { index amountTnd receipts { txHash blockNumber } }
      }
    }
    """
    response = Client().post(
        "/graphql/",
        data=json.dumps({"query": query}),
        content_type="application/json",
        **auditor_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body.get("errors") is None
    tranches = body["data"]["proposal"]["tranches"]
    assert len(tranches) == 1
    assert tranches[0]["amountTnd"] == 1000.0
    assert len(tranches[0]["receipts"]) == 1
    assert tranches[0]["receipts"][0]["blockNumber"] == 1
