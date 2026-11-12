from collections import defaultdict
from datetime import datetime
from typing import Optional

import strawberry
from strawberry.permission import BasePermission
from asgiref.sync import sync_to_async
from django.db.models import Count, Sum
from strawberry.dataloader import DataLoader

from .models import (
    AgentLoopExecution,
    MilestoneReport,
    Municipality,
    OnChainZKReceipt,
    Proposal,
    Tranche,
    Vote,
)


MAX_LIST = 200


def _clamp(limit: int) -> int:
    return max(1, min(limit, MAX_LIST))


class IsAuthenticated(BasePermission):
    message = "Authentication required"

    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context.get("user") is not None


class IsAuditor(BasePermission):
    """Raw votes (voter hashes) and agent traces are for auditors/admins only."""

    message = "Auditor role required"

    def has_permission(self, source, info, **kwargs) -> bool:
        user = info.context.get("user")
        return bool(user and user.role in ("MUNICIPAL_AUDITOR", "NATIONAL_ADMIN"))


@sync_to_async
def _load_proposals(municipality_ids):
    grouped = defaultdict(list)
    queryset = (
        Proposal.objects.filter(municipality_id__in=municipality_ids)
        .select_related("municipality", "author")
        .annotate(votes_count=Count("votes"), raised_tnd=Sum("votes__amount_tnd"))
        .order_by("-created_at")
    )
    for proposal in queryset:
        grouped[str(proposal.municipality_id)].append(proposal)
    return [grouped[str(municipality_id)] for municipality_id in municipality_ids]


@sync_to_async
def _load_votes(proposal_ids):
    grouped = defaultdict(list)
    queryset = Vote.objects.filter(proposal_id__in=proposal_ids).order_by("-created_at")
    for vote in queryset:
        grouped[str(vote.proposal_id)].append(vote)
    return [grouped[str(proposal_id)] for proposal_id in proposal_ids]


@sync_to_async
def _load_milestones(proposal_ids):
    grouped = defaultdict(list)
    queryset = MilestoneReport.objects.filter(proposal_id__in=proposal_ids).order_by(
        "-timestamp"
    )
    for milestone in queryset:
        grouped[str(milestone.proposal_id)].append(milestone)
    return [grouped[str(proposal_id)] for proposal_id in proposal_ids]


@sync_to_async
def _load_tranches(proposal_ids):
    grouped = defaultdict(list)
    queryset = Tranche.objects.filter(proposal_id__in=proposal_ids).order_by("index")
    for tranche in queryset:
        grouped[str(tranche.proposal_id)].append(tranche)
    return [grouped[str(proposal_id)] for proposal_id in proposal_ids]


@sync_to_async
def _load_receipts(tranche_ids):
    grouped = defaultdict(list)
    queryset = OnChainZKReceipt.objects.filter(tranche_id__in=tranche_ids).order_by(
        "-block_number"
    )
    for receipt in queryset:
        grouped[str(receipt.tranche_id)].append(receipt)
    return [grouped[str(tranche_id)] for tranche_id in tranche_ids]


@strawberry.type
class VoteType:
    id: strawberry.ID
    voter_hash: str
    amount_tnd: float
    created_at: datetime

    @classmethod
    def from_model(cls, vote: Vote) -> "VoteType":
        return cls(
            id=strawberry.ID(str(vote.pk)),
            voter_hash=vote.voter_hash,
            amount_tnd=vote.amount_tnd,
            created_at=vote.created_at,
        )


@strawberry.type
class MilestoneType:
    id: strawberry.ID
    timestamp: datetime
    progress_pct: float
    paid_pct: float
    photo_hash: str
    latitude: float
    longitude: float
    ingestion_protocol: str

    @classmethod
    def from_model(cls, milestone: MilestoneReport) -> "MilestoneType":
        return cls(
            id=strawberry.ID(str(milestone.pk)),
            timestamp=milestone.timestamp,
            progress_pct=milestone.progress_pct,
            paid_pct=milestone.paid_pct,
            photo_hash=milestone.photo_hash,
            latitude=milestone.latitude,
            longitude=milestone.longitude,
            ingestion_protocol=milestone.ingestion_protocol,
        )


@strawberry.type
class ReceiptType:
    id: strawberry.ID
    zk_commitment_hash: str
    tx_hash: str
    block_number: int
    network_name: str
    is_verified_on_chain: bool

    @classmethod
    def from_model(cls, receipt: OnChainZKReceipt) -> "ReceiptType":
        return cls(
            id=strawberry.ID(str(receipt.pk)),
            zk_commitment_hash=receipt.zk_commitment_hash,
            tx_hash=receipt.tx_hash,
            block_number=receipt.block_number,
            network_name=receipt.network_name,
            is_verified_on_chain=receipt.is_verified_on_chain,
        )


@strawberry.type
class TrancheType:
    id: strawberry.ID
    index: int
    amount_tnd: float
    released_at: Optional[datetime]

    @classmethod
    def from_model(cls, tranche: Tranche) -> "TrancheType":
        return cls(
            id=strawberry.ID(str(tranche.pk)),
            index=tranche.index,
            amount_tnd=tranche.amount_tnd,
            released_at=tranche.released_at,
        )

    @strawberry.field
    async def receipts(self, info: strawberry.Info) -> list[ReceiptType]:
        rows = await info.context["receipts_loader"].load(self.id)
        return [ReceiptType.from_model(row) for row in rows]


@strawberry.type
class ProposalType:
    id: strawberry.ID
    project_code: str
    title: str
    text: str
    language: str
    category: str
    cluster_id: str
    estimated_cost_tnd: float
    status: str
    created_at: datetime
    votes_count: int
    raised_tnd: float

    @classmethod
    def from_model(cls, proposal: Proposal) -> "ProposalType":
        return cls(
            id=strawberry.ID(str(proposal.pk)),
            project_code=proposal.project_code,
            title=proposal.title,
            text=proposal.text,
            language=proposal.language,
            category=proposal.category,
            cluster_id=proposal.cluster_id,
            estimated_cost_tnd=proposal.estimated_cost_tnd,
            status=proposal.status,
            created_at=proposal.created_at,
            votes_count=getattr(proposal, "votes_count", 0),
            raised_tnd=getattr(proposal, "raised_tnd", 0.0) or 0.0,
        )

    @strawberry.field(permission_classes=[IsAuditor])
    async def votes(self, info: strawberry.Info, limit: int = 50) -> list[VoteType]:
        rows = await info.context["votes_loader"].load(self.id)
        return [VoteType.from_model(row) for row in rows[: _clamp(limit)]]

    @strawberry.field
    async def milestones(self, info: strawberry.Info, limit: int = 50) -> list[MilestoneType]:
        rows = await info.context["milestones_loader"].load(self.id)
        return [MilestoneType.from_model(row) for row in rows[: _clamp(limit)]]

    @strawberry.field
    async def tranches(self, info: strawberry.Info) -> list[TrancheType]:
        rows = await info.context["tranches_loader"].load(self.id)
        return [TrancheType.from_model(row) for row in rows]


@strawberry.type
class MunicipalityType:
    id: strawberry.ID
    name: str
    governorate: str
    total_budget_tnd: float
    matching_pool_tnd: float
    contract_address: str

    @classmethod
    def from_model(cls, municipality: Municipality) -> "MunicipalityType":
        return cls(
            id=strawberry.ID(str(municipality.pk)),
            name=municipality.name,
            governorate=municipality.governorate,
            total_budget_tnd=municipality.total_budget_tnd,
            matching_pool_tnd=municipality.matching_pool_tnd,
            contract_address=municipality.contract_address,
        )

    @strawberry.field
    async def proposals(self, info: strawberry.Info, limit: int = 50) -> list[ProposalType]:
        rows = await info.context["proposals_loader"].load(self.id)
        return [ProposalType.from_model(row) for row in rows[: _clamp(limit)]]


@strawberry.type
class AgentExecutionType:
    thread_id: str
    trigger_source: str
    darja_transcript: str
    final_recommendation: str
    confidence_score: float

    @classmethod
    def from_model(cls, execution: AgentLoopExecution) -> "AgentExecutionType":
        return cls(
            thread_id=execution.thread_id,
            trigger_source=execution.trigger_source,
            darja_transcript=execution.darja_transcript,
            final_recommendation=execution.final_recommendation,
            confidence_score=execution.confidence_score,
        )


@sync_to_async
def _get_municipalities(governorate):
    queryset = Municipality.objects.all().order_by("name")
    if governorate:
        queryset = queryset.filter(governorate=governorate)
    return [MunicipalityType.from_model(row) for row in queryset]


@sync_to_async
def _get_proposals(municipality_id, status, category):
    queryset = (
        Proposal.objects.select_related("municipality", "author")
        .annotate(votes_count=Count("votes"), raised_tnd=Sum("votes__amount_tnd"))
        .order_by("-created_at")
    )
    if municipality_id:
        queryset = queryset.filter(municipality_id=municipality_id)
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category=category)
    return [ProposalType.from_model(row) for row in queryset]


@sync_to_async
def _get_proposal(project_code):
    row = (
        Proposal.objects.select_related("municipality", "author")
        .annotate(votes_count=Count("votes"), raised_tnd=Sum("votes__amount_tnd"))
        .filter(project_code=project_code)
        .first()
    )
    return ProposalType.from_model(row) if row else None


@sync_to_async
def _get_agent_executions(thread_id):
    queryset = AgentLoopExecution.objects.all().order_by("-created_at")
    if thread_id:
        queryset = queryset.filter(thread_id=thread_id)
    return [AgentExecutionType.from_model(row) for row in queryset]


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def municipalities(
        self, governorate: Optional[str] = None, limit: int = 50
    ) -> list[MunicipalityType]:
        return (await _get_municipalities(governorate))[: _clamp(limit)]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def proposals(
        self,
        municipality_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> list[ProposalType]:
        return (await _get_proposals(municipality_id, status, category))[: _clamp(limit)]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def proposal(self, project_code: str) -> Optional[ProposalType]:
        return await _get_proposal(project_code)

    @strawberry.field(permission_classes=[IsAuditor])
    async def agent_executions(
        self, thread_id: Optional[str] = None, limit: int = 50
    ) -> list[AgentExecutionType]:
        return (await _get_agent_executions(thread_id))[: _clamp(limit)]


def build_loaders() -> dict:
    return {
        "proposals_loader": DataLoader(load_fn=_load_proposals),
        "votes_loader": DataLoader(load_fn=_load_votes),
        "milestones_loader": DataLoader(load_fn=_load_milestones),
        "tranches_loader": DataLoader(load_fn=_load_tranches),
        "receipts_loader": DataLoader(load_fn=_load_receipts),
    }


schema = strawberry.Schema(query=Query)
