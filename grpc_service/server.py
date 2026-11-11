"""
Baladiya-Trust gRPC ingestion server (proto3 + grpcio).

Implements MilestoneIngestService:
- StreamMilestones: client-streaming, HMAC-verified milestone packets
- EvaluateProposalRisk: unary risk lookup for a project code
"""
import logging
import os
import sys
import time
from concurrent import futures
from datetime import datetime

import grpc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from backend.tunisovereign_core.ml_anomaly import evaluate_progress_lag
from backend.tunisovereign_core.models import (
    AnomalyEvent,
    MilestoneReport,
    OnChainZKReceipt,
    Proposal,
)
from grpc_service import baladiya_pb2, baladiya_pb2_grpc
from grpc_service.security import verify_packet_signature

logger = logging.getLogger(__name__)


def _trigger_agent(thread_id: str, municipality: str, project_code: str, lag: float) -> str:
    try:
        from agent.langgraph_agent import run_baladiya_agent_loop
    except ImportError:
        logger.warning("LangGraph agent not available yet; thread %s recorded only", thread_id)
        return thread_id

    state = {
        "thread_id": thread_id,
        "municipality": municipality,
        "proposal_code": project_code,
        "darja_input": (
            f"gRPC milestone alert: project {project_code} in {municipality} "
            f"has a payment/progress lag of {lag:.1f} points."
        ),
        "trigger_source": "gRPC_Milestone_Lag",
        "parsed_intent": {},
        "anomaly_report": {"lag": lag, "kind": "PROGRESS_LAG"},
        "budget_decision": {},
        "zk_receipt": {},
        "skills_trace": [],
        "final_explanation": "",
    }
    try:
        run_baladiya_agent_loop(state)
    except Exception:
        logger.exception("Agent loop failed for thread %s", thread_id)
    return thread_id


class MilestoneIngestServicer(baladiya_pb2_grpc.MilestoneIngestServiceServicer):
    def StreamMilestones(self, request_iterator, context):
        accepted = 0
        anomaly_triggered = False
        thread_id = ""

        for packet in request_iterator:
            if not verify_packet_signature(packet):
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Invalid HMAC signature for project {packet.project_code}",
                )

            proposal = Proposal.objects.filter(project_code=packet.project_code).first()
            if proposal is None:
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"Unknown project code {packet.project_code}",
                )

            try:
                timestamp = datetime.fromisoformat(packet.iso_timestamp.replace("Z", "+00:00"))
            except ValueError:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid iso_timestamp")

            MilestoneReport.objects.create(
                proposal=proposal,
                timestamp=timestamp,
                progress_pct=packet.progress_pct,
                paid_pct=packet.paid_pct,
                photo_hash=packet.photo_hash,
                latitude=packet.latitude,
                longitude=packet.longitude,
                ingestion_protocol="gRPC",
            )
            accepted += 1

            history = list(
                MilestoneReport.objects.filter(proposal=proposal)
                .order_by("-timestamp")
                .values_list("progress_pct", "paid_pct")[:20]
            )
            rolling_lags = [paid - progress for progress, paid in history]
            report = evaluate_progress_lag(
                packet.progress_pct, packet.paid_pct, rolling_lags=rolling_lags
            )

            if report["is_anomaly"]:
                AnomalyEvent.objects.create(
                    proposal=proposal,
                    kind=AnomalyEvent.Kind.PROGRESS_LAG,
                    severity=report["severity"],
                    isolation_forest_score=report["score"],
                )

            if report["lag"] > 20:
                anomaly_triggered = True
                thread_id = _trigger_agent(
                    f"grpc-lag-{packet.project_code}-{accepted}",
                    packet.municipality,
                    packet.project_code,
                    report["lag"],
                )

        return baladiya_pb2.IngestAck(
            accepted_count=accepted,
            anomaly_triggered=anomaly_triggered,
            agent_thread_id=thread_id,
        )

    def EvaluateProposalRisk(self, request, context):
        proposal = Proposal.objects.filter(project_code=request.project_code).first()
        if proposal is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Unknown project code {request.project_code}",
            )

        latest = (
            MilestoneReport.objects.filter(proposal=proposal)
            .order_by("-timestamp")
            .first()
        )
        if latest is None:
            return baladiya_pb2.RiskResponse(severity="UNKNOWN", score=0.0, tx_hash="")

        report = evaluate_progress_lag(latest.progress_pct, latest.paid_pct)
        receipt = (
            OnChainZKReceipt.objects.filter(tranche__proposal=proposal)
            .order_by("-block_number")
            .first()
        )
        return baladiya_pb2.RiskResponse(
            severity=report["severity"],
            score=report["score"],
            tx_hash=receipt.tx_hash if receipt else "",
        )


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    baladiya_pb2_grpc.add_MilestoneIngestServiceServicer_to_server(
        MilestoneIngestServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[Baladiya-Trust gRPC] MilestoneIngestService listening on port {port}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve(int(os.getenv("GRPC_PORT", "50051")))
