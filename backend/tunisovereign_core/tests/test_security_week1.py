"""Regression tests for the Week 1 review: GraphQL auth, passwords, residency, pagination."""
import json

import pytest
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.tunisovereign_core.models import Municipality, Proposal, StakeholderUser, Vote

GOOD_PASSWORD = "Zx98!unusual7"
VOTES_QUERY = "{ proposals { projectCode votesCount votes { voterHash amountTnd } } }"


@pytest.fixture
def world(db):
    sbeitla = Municipality.objects.create(
        name="Sbeitla", governorate="Kasserine", total_budget_tnd=1e6, matching_pool_tnd=1e5
    )
    regueb = Municipality.objects.create(
        name="Regueb", governorate="Sidi_Bouzid", total_budget_tnd=1e6, matching_pool_tnd=1e5
    )
    citizen = StakeholderUser.objects.create_user(
        "citizen", password=GOOD_PASSWORD, municipality="Sbeitla"
    )
    auditor = StakeholderUser.objects.create_user(
        "auditor", password=GOOD_PASSWORD, municipality="Sbeitla",
        role=StakeholderUser.Role.MUNICIPAL_AUDITOR,
    )
    local = Proposal.objects.create(
        municipality=sbeitla, author=citizen, project_code="SBE-1", title="t", text="x", category="ROAD"
    )
    foreign = Proposal.objects.create(
        municipality=regueb, author=citizen, project_code="REG-1", title="t", text="x", category="ROAD"
    )
    Vote.objects.create(proposal=local, voter_hash="0x" + "ab" * 32, amount_tnd=5)
    return {"sbeitla": sbeitla, "regueb": regueb, "citizen": citizen, "auditor": auditor,
            "local": local, "foreign": foreign}


def _api(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def _gql(query, user=None):
    headers = {}
    if user is not None:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {AccessToken.for_user(user)}"
    return Client().post(
        "/graphql/", data=json.dumps({"query": query}), content_type="application/json", **headers
    ).json()


# ---- 1) GraphQL authentication -------------------------------------------------------
def test_graphql_rejects_anonymous(world):
    body = _gql(VOTES_QUERY)
    assert body.get("errors")
    assert not (body.get("data") or {}).get("proposals")


def test_graphql_hides_raw_votes_from_citizens(world):
    body = _gql("{ proposals { projectCode votes { voterHash } } }", world["citizen"])
    assert body.get("errors")  # votes field requires an auditor


def test_graphql_citizen_still_sees_totals(world):
    body = _gql("{ proposals { projectCode votesCount raisedTnd } }", world["citizen"])
    assert body.get("errors") is None
    assert {p["projectCode"] for p in body["data"]["proposals"]} == {"SBE-1", "REG-1"}


def test_graphql_auditor_sees_votes(world):
    body = _gql(VOTES_QUERY, world["auditor"])
    assert body.get("errors") is None


def test_graphql_invalid_token_is_anonymous(world):
    response = Client().post(
        "/graphql/", data=json.dumps({"query": VOTES_QUERY}), content_type="application/json",
        HTTP_AUTHORIZATION="Bearer not-a-real-token",
    ).json()
    assert response.get("errors")


# ---- 2) Password validation ----------------------------------------------------------
@pytest.mark.parametrize("weak", ["12345678", "password", "weak-user"])
def test_register_rejects_weak_passwords(db, weak):
    response = APIClient().post(
        "/api/auth/register/",
        {"username": "weak-user", "password": weak, "municipality": "Sbeitla"},
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.json()


def test_register_accepts_strong_password(db):
    response = APIClient().post(
        "/api/auth/register/",
        {"username": "newcomer", "password": GOOD_PASSWORD, "municipality": "Sbeitla"},
        format="json",
    )
    assert response.status_code == 201


# ---- 3) Residency --------------------------------------------------------------------
def test_citizen_cannot_vote_outside_own_municipality(world):
    response = _api(world["citizen"]).post(
        "/api/v1/votes/", {"proposal": world["foreign"].pk, "amount_tnd": 3}, format="json"
    )
    assert response.status_code == 400


def test_citizen_can_vote_in_own_municipality(world):
    response = _api(world["citizen"]).post(
        "/api/v1/votes/", {"proposal": world["local"].pk, "amount_tnd": 3}, format="json"
    )
    assert response.status_code == 201


def test_citizen_cannot_propose_outside_own_municipality(world):
    response = _api(world["citizen"]).post(
        "/api/v1/proposals/",
        {"municipality": str(world["regueb"].pk), "project_code": "REG-X", "title": "t",
         "text": "x", "category": "ROAD"},
        format="json",
    )
    assert response.status_code == 400


def test_citizen_can_propose_in_own_municipality(world):
    response = _api(world["citizen"]).post(
        "/api/v1/proposals/",
        {"municipality": str(world["sbeitla"].pk), "project_code": "SBE-X", "title": "t",
         "text": "x", "category": "ROAD"},
        format="json",
    )
    assert response.status_code == 201


# ---- 4) Pagination -------------------------------------------------------------------
def test_list_endpoints_are_paginated(world):
    body = _api(world["citizen"]).get("/api/v1/proposals/").json()
    assert {"count", "next", "previous", "results"} <= set(body)
    assert body["count"] == 2


def test_graphql_limit_is_respected(world):
    body = _gql("{ proposals(limit: 1) { projectCode } }", world["citizen"])
    assert len(body["data"]["proposals"]) == 1
