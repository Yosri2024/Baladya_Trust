import math
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db.models import Sum

from backend.tunisovereign_core.models import (
    AnomalyEvent,
    Municipality,
    Proposal,
    Tranche,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        """Fallback shim used only when the mcp package is not installed."""

        def __init__(self, name: str):
            self.name = name

        def resource(self, uri: str, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def tool(self, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def prompt(self, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def run(self):
            print(f"[{self.name}] FastMCP server initialized (install 'mcp' for transport).")


mcp = FastMCP("BaladiyaTreasuryMCP")


def _quadratic_match(contributions) -> float:
    amounts = [float(value) for value in contributions if float(value) > 0]
    if not amounts:
        return 0.0
    total = sum(amounts)
    match = (sum(math.sqrt(amount) for amount in amounts) ** 2) - total
    return round(max(0.0, match), 2)


def _municipality_or_none(name: str):
    return (
        Municipality.objects.filter(name__iexact=name).first()
        or Municipality.objects.filter(governorate__iexact=name).first()
    )


@mcp.resource("baladiya://municipality/{municipality_name}/treasury")
def get_municipality_treasury_resource(municipality_name: str) -> dict:
    """Read-only treasury snapshot for the agent and MCP Inspector."""
    return get_municipality_treasury(municipality_name)


@mcp.resource("baladiya://proposal/{project_code}/audit")
def get_proposal_audit(project_code: str) -> dict:
    """Read-only audit trail for one municipal project."""
    proposal = Proposal.objects.filter(project_code=project_code).first()
    if proposal is None:
        return {"error": "PROPOSAL_NOT_FOUND", "project_code": project_code}

    latest = proposal.milestones.order_by("-timestamp").first()
    anomalies = list(
        proposal.anomalies.order_by("-detected_at").values(
            "kind", "severity", "isolation_forest_score", "detected_at"
        )
    )
    tranches = list(
        proposal.tranches.order_by("index").values(
            "index", "amount_tnd", "released_at"
        )
    )

    return {
        "project_code": proposal.project_code,
        "title": proposal.title,
        "municipality": proposal.municipality.name,
        "status": proposal.status,
        "estimated_cost_tnd": proposal.estimated_cost_tnd,
        "votes_count": proposal.votes.count(),
        "raised_tnd": round(
            proposal.votes.aggregate(total=Sum("amount_tnd"))["total"] or 0.0, 2
        ),
        "latest_milestone": (
            {
                "timestamp": latest.timestamp.isoformat(),
                "progress_pct": latest.progress_pct,
                "paid_pct": latest.paid_pct,
                "lag": round(latest.paid_pct - latest.progress_pct, 2),
                "photo_hash": latest.photo_hash,
            }
            if latest
            else None
        ),
        "anomalies": anomalies,
        "tranches": tranches,
        "anomaly_count": len(anomalies),
    }


@mcp.tool()
def get_municipality_treasury(municipality_name: str) -> dict:
    """Return budget, contributions, quadratic matching and released tranches."""
    municipality = _municipality_or_none(municipality_name)
    if municipality is None:
        return {"error": "MUNICIPALITY_NOT_FOUND", "municipality": municipality_name}

    proposals = list(municipality.proposals.all())
    contributions = 0.0
    quadratic_match = 0.0
    for proposal in proposals:
        amounts = list(proposal.votes.values_list("amount_tnd", flat=True))
        contributions += sum(amounts)
        quadratic_match += _quadratic_match(amounts)

    released = (
        Tranche.objects.filter(
            proposal__municipality=municipality, released_at__isnull=False
        ).aggregate(total=Sum("amount_tnd"))["total"]
        or 0.0
    )
    capped_match = min(quadratic_match, municipality.matching_pool_tnd)
    available_budget = max(0.0, municipality.total_budget_tnd - released)

    return {
        "municipality": municipality.name,
        "governorate": municipality.governorate,
        "contract_address": municipality.contract_address,
        "total_budget_tnd": round(municipality.total_budget_tnd, 2),
        "matching_pool_tnd": round(municipality.matching_pool_tnd, 2),
        "contributions_tnd": round(contributions, 2),
        "quadratic_matching_required_tnd": round(quadratic_match, 2),
        "capped_matching_tnd": round(capped_match, 2),
        "matching_pool_remaining_tnd": round(
            max(0.0, municipality.matching_pool_tnd - capped_match), 2
        ),
        "released_tnd": round(released, 2),
        "available_budget_tnd": round(available_budget, 2),
        "proposal_count": len(proposals),
        "budget_utilization_pct": round(
            (released / municipality.total_budget_tnd * 100.0)
            if municipality.total_budget_tnd > 0
            else 0.0,
            2,
        ),
    }


@mcp.tool()
def compute_quadratic_funding(
    contributions: list[float],
    matching_pool_tnd: float | None = None,
) -> dict:
    """Compute (sum sqrt(c_i))^2 - sum(c_i), then cap by the available pool."""
    amounts = [float(value) for value in contributions]
    if any(amount < 0 for amount in amounts):
        return {"error": "NEGATIVE_CONTRIBUTION"}

    positive = [amount for amount in amounts if amount > 0]
    total = sum(positive)
    raw_match = (sum(math.sqrt(amount) for amount in positive) ** 2) - total
    match = max(0.0, raw_match)
    capped = min(match, matching_pool_tnd) if matching_pool_tnd is not None else match

    return {
        "contributor_count": len(positive),
        "total_contributions_tnd": round(total, 2),
        "quadratic_match_tnd": round(match, 2),
        "capped_match_tnd": round(capped, 2),
        "matching_pool_tnd": (
            round(float(matching_pool_tnd), 2) if matching_pool_tnd is not None else None
        ),
        "pool_exhausted": bool(
            matching_pool_tnd is not None and match > matching_pool_tnd
        ),
        "matching_ratio": round(match / total, 4) if total > 0 else 0.0,
    }


@mcp.tool()
def check_tranche_eligibility(project_code: str) -> dict:
    """Recommend whether the next tranche can be released; never moves funds."""
    proposal = Proposal.objects.filter(project_code=project_code).first()
    if proposal is None:
        return {"error": "PROPOSAL_NOT_FOUND", "project_code": project_code}

    latest = proposal.milestones.order_by("-timestamp").first()
    critical = proposal.anomalies.filter(
        severity=AnomalyEvent.Severity.CRITICAL
    ).exists()
    duplicate_photo = proposal.anomalies.filter(
        kind=AnomalyEvent.Kind.DUPLICATE_PHOTO
    ).exists()
    released_count = proposal.tranches.filter(released_at__isnull=False).count()
    max_tranche = proposal.tranches.order_by("-index").values_list("index", flat=True).first()

    reasons = []
    if latest is None:
        reasons.append("NO_MILESTONE_REPORT")
        lag = None
    else:
        lag = round(latest.paid_pct - latest.progress_pct, 2)
        if lag > 20:
            reasons.append("PROGRESS_LAG_ABOVE_20")
    if critical:
        reasons.append("CRITICAL_ANOMALY_OPEN")
    if duplicate_photo:
        reasons.append("DUPLICATE_PHOTO_OPEN")
    if released_count >= 4:
        reasons.append("ALL_TRANCHES_RELEASED")

    eligible = not reasons
    next_index = (max_tranche or 0) + 1
    return {
        "project_code": proposal.project_code,
        "eligible": eligible,
        "reasons": reasons,
        "latest_progress_pct": latest.progress_pct if latest else None,
        "latest_paid_pct": latest.paid_pct if latest else None,
        "latest_lag": lag,
        "released_tranches": released_count,
        "next_tranche_index": next_index,
        "recommended_amount_tnd": round(proposal.estimated_cost_tnd / 4.0, 2),
        "requires_human_approval": True,
    }


@mcp.prompt()
def baladiya_auditor_prompt(municipality_name: str, language: str = "ar-TN") -> str:
    return (
        f"You are the Baladiya-Trust municipal auditor for {municipality_name}, Tunisia. "
        f"Answer in {language}. Verify the treasury with MCP resources, check tranche "
        "eligibility, and never release public money without a verified milestone, no open "
        "critical anomaly and a human approval."
    )


if __name__ == "__main__":
    mcp.run()
