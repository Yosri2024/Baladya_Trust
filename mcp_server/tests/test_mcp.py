from datetime import datetime, timezone

import pytest

from backend.tunisovereign_core.models import (
    AnomalyEvent,
    MilestoneReport,
    Municipality,
    Proposal,
    StakeholderUser,
    Tranche,
    Vote,
)
from mcp_server.tunisovereign_mcp import (
    check_tranche_eligibility,
    compute_quadratic_funding,
    get_municipality_treasury,
    get_municipality_treasury_resource,
    get_proposal_audit,
)


@pytest.fixture
def municipality(db):
    return Municipality.objects.create(
        name="Kasserine",
        governorate="Kasserine",
        total_budget_tnd=10_000.0,
        matching_pool_tnd=1_000.0,
    )


@pytest.fixture
def proposal(municipality):
    author = StakeholderUser.objects.create_user(username="mcp_author")
    return Proposal.objects.create(
        municipality=municipality,
        author=author,
        project_code="KAS-ROAD-001",
        title="Route Sbeitla",
        text="tarmim triq Sbeitla",
        language="ar-TN",
        category=Proposal.Category.ROAD,
        estimated_cost_tnd=4_000.0,
    )


def test_quadratic_funding_formula_and_pool_cap():
    dispersed = compute_quadratic_funding([1.0] * 100)
    concentrated = compute_quadratic_funding([100.0])
    capped = compute_quadratic_funding([1.0] * 100, matching_pool_tnd=5_000.0)

    assert dispersed["quadratic_match_tnd"] == 9_900.0
    assert concentrated["quadratic_match_tnd"] == 0.0
    assert capped["capped_match_tnd"] == 5_000.0
    assert capped["pool_exhausted"] is True


@pytest.mark.django_db
def test_treasury_resource_aggregates_votes_and_tranches(proposal):
    for index in range(4):
        Vote.objects.create(
            proposal=proposal,
            voter_hash=f"0x{index:064d}",
            amount_tnd=1.0,
        )
    Tranche.objects.create(
        proposal=proposal,
        index=1,
        amount_tnd=1_000.0,
        released_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    treasury = get_municipality_treasury("Kasserine")
    assert treasury["contributions_tnd"] == 4.0
    assert treasury["quadratic_matching_required_tnd"] == 12.0
    assert treasury["released_tnd"] == 1_000.0
    assert treasury["available_budget_tnd"] == 9_000.0
    assert get_municipality_treasury_resource("Kasserine") == treasury


@pytest.mark.django_db
def test_audit_and_tranche_eligibility_block_on_lag(proposal):
    MilestoneReport.objects.create(
        proposal=proposal,
        timestamp=datetime(2026, 9, 10, tzinfo=timezone.utc),
        progress_pct=40.0,
        paid_pct=70.0,
        photo_hash="a" * 64,
        latitude=35.16,
        longitude=8.83,
    )
    AnomalyEvent.objects.create(
        proposal=proposal,
        kind=AnomalyEvent.Kind.PROGRESS_LAG,
        severity=AnomalyEvent.Severity.CRITICAL,
        isolation_forest_score=0.7,
    )

    audit = get_proposal_audit(proposal.project_code)
    eligibility = check_tranche_eligibility(proposal.project_code)

    assert audit["anomaly_count"] == 1
    assert audit["latest_milestone"]["lag"] == 30.0
    assert eligibility["eligible"] is False
    assert "PROGRESS_LAG_ABOVE_20" in eligibility["reasons"]
    assert "CRITICAL_ANOMALY_OPEN" in eligibility["reasons"]
    assert eligibility["requires_human_approval"] is True
