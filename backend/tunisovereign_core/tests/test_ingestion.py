from grpc_service import baladiya_pb2
from grpc_service.security import sign_packet, verify_packet_signature

from backend.tunisovereign_core.ml_anomaly import evaluate_progress_lag


def _packet(**overrides):
    values = {
        "project_code": "KAS-ROAD-001",
        "municipality": "Kasserine",
        "progress_pct": 42.0,
        "paid_pct": 55.0,
        "photo_hash": "a" * 64,
        "latitude": 35.123456,
        "longitude": 8.654321,
        "iso_timestamp": "2026-11-11T20:00:00+00:00",
    }
    values.update(overrides)
    return baladiya_pb2.MilestonePacket(**values)


def test_hmac_signature_is_deterministic_and_payload_sensitive():
    packet = _packet()
    packet.signature_hmac = sign_packet(packet, secret="test-secret")
    assert verify_packet_signature(packet, secret="test-secret") is True

    packet.progress_pct = 43.0
    assert verify_packet_signature(packet, secret="test-secret") is False

    packet = _packet()
    packet.signature_hmac = sign_packet(packet, secret="another-secret")
    assert verify_packet_signature(packet, secret="test-secret") is False


def test_progress_lag_rule_and_severity():
    ok = evaluate_progress_lag(60.0, 65.0)
    assert ok["lag"] == 5.0
    assert ok["is_anomaly"] is False
    assert ok["severity"] == "LOW"

    lagging = evaluate_progress_lag(40.0, 65.0)
    assert lagging["lag"] == 25.0
    assert lagging["is_anomaly"] is True
    assert lagging["severity"] == "MEDIUM"

    critical = evaluate_progress_lag(30.0, 70.0)
    assert critical["severity"] == "CRITICAL"
    assert critical["score"] == 0.4
