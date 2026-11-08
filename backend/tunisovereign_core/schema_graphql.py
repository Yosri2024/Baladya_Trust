import strawberry
from typing import List, Optional
from strawberry.dataloader import DataLoader


@strawberry.type
class ZKReceiptType:
    zk_commitment_hash: str
    tx_hash: str
    block_number: int
    network_name: str
    is_verified_on_chain: bool


@strawberry.type
class AgentExecutionType:
    thread_id: str
    trigger_source: str
    darja_transcript: str
    final_recommendation: str
    confidence_score: float
    zk_receipt: Optional[ZKReceiptType]


@strawberry.type
class GovernorateCoopGraphType:
    name: str
    governorate: str
    track_domain: str
    daily_quota_limit: float
    recent_agent_executions: List[AgentExecutionType]


async def batch_load_executions(keys: List[str]) -> List[List[AgentExecutionType]]:
    # DataLoader batch function preventing N+1 SQL queries across governorates
    return [[] for _ in keys]


@strawberry.type
class Query:
    @strawberry.field
    def governorate_cooperatives(self, governorate: Optional[str] = None) -> List[GovernorateCoopGraphType]:
        sample_receipt = ZKReceiptType(
            zk_commitment_hash="0x8f4e2b9a1c3d5e7f00112233445566778899aabbccddeeff0011223344556677",
            tx_hash="0x3a91c8d72b1e4f09182736455463728190abcdef1234567890abcdef12345678",
            block_number=142,
            network_name="Foundry-Anvil-Local",
            is_verified_on_chain=True,
        )
        sample_exec = AgentExecutionType(
            thread_id="thread-kasserine-001",
            trigger_source="Darja_Voice_and_gRPC_Anomaly",
            darja_transcript="Ya khouya el sonda fi Sabiba habtet barcha wel zitoun atchan",
            final_recommendation="Authorized 3,150L emergency drip release for Plot KAS-04 (within 4,200L quota).",
            confidence_score=0.94,
            zk_receipt=sample_receipt,
        )
        return [
            GovernorateCoopGraphType(
                name="GDA Sbeitla & Sabiba Sovereign Water Co-op",
                governorate=governorate or "Kasserine",
                track_domain="Track_01_TunicChain_Water_Agri",
                daily_quota_limit=4200.0,
                recent_agent_executions=[sample_exec],
            )
        ]


schema = strawberry.Schema(query=Query)
