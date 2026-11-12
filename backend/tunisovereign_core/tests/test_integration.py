from concurrent import futures

import grpc
import pytest
from django.db import connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.tunisovereign_core.models import MilestoneReport, Municipality
from grpc_service import baladiya_pb2, baladiya_pb2_grpc
from grpc_service.security import sign_packet
from grpc_service.server import MilestoneIngestServicer


class _ClosingServicer(MilestoneIngestServicer):
    def StreamMilestones(self, request_iterator, context):
        try:
            return super().StreamMilestones(request_iterator, context)
        finally:
            connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_week1_end_to_end_flow():
    municipality = Municipality.objects.create(
        name="Kasserine",
        governorate="Kasserine",
        total_budget_tnd=500_000,
        matching_pool_tnd=50_000,
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
    )
    client = APIClient()

    register = client.post(
        "/api/auth/register/",
        {
            "username": "integration_citizen",
            "password": "integration-pass-123",
            "municipality": "Kasserine",
            "wallet_address": "0x0000000000000000000000000000000000000001",
        },
        format="json",
    )
    assert register.status_code == 201

    login = client.post(
        "/api/auth/token/",
        {"username": "integration_citizen", "password": "integration-pass-123"},
        format="json",
    )
    assert login.status_code == 200
    access = login.json()["access"]
    claims = AccessToken(access)
    assert claims["role"] == "CITIZEN"
    assert claims["municipality"] == "Kasserine"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    proposal_response = client.post(
        "/api/v1/proposals/",
        {
            "municipality": str(municipality.pk),
            "project_code": "KAS-E2E-001",
            "title": "Réhabilitation route Sbeitla",
            "text": "tarmim triq Sbeitla",
            "language": "ar-TN",
            "category": "ROAD",
            "estimated_cost_tnd": 120_000,
        },
        format="json",
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]

    graphql_response = client.post(
        "/graphql/",
        {
            "query": """
                query Proposal($code: String!) {
                    proposal(projectCode: $code) {
                        id
                        projectCode
                        title
                        votesCount
                        raisedTnd
                    }
                }
            """,
            "variables": {"code": "KAS-E2E-001"},
        },
        format="json",
    )
    assert graphql_response.status_code == 200
    graphql_body = graphql_response.json()
    assert "errors" not in graphql_body, graphql_body
    assert graphql_body["data"]["proposal"]["projectCode"] == "KAS-E2E-001"

    packet = baladiya_pb2.MilestonePacket(
        project_code="KAS-E2E-001",
        municipality="Kasserine",
        progress_pct=50.0,
        paid_pct=55.0,
        photo_hash="a" * 64,
        latitude=35.1676,
        longitude=8.8365,
        iso_timestamp="2026-11-12T10:00:00+00:00",
    )
    packet.signature_hmac = sign_packet(packet)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    baladiya_pb2_grpc.add_MilestoneIngestServiceServicer_to_server(
        _ClosingServicer(), server
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = baladiya_pb2_grpc.MilestoneIngestServiceStub(channel)
            ack = stub.StreamMilestones(iter([packet]))
    finally:
        server.stop(0).wait(timeout=5)

    assert ack.accepted_count == 1
    assert ack.anomaly_triggered is False
    assert MilestoneReport.objects.filter(proposal_id=proposal_id).count() == 1
