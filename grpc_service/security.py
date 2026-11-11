import hashlib
import hmac
import os


def milestone_payload(
    project_code: str,
    municipality: str,
    progress_pct: float,
    paid_pct: float,
    photo_hash: str,
    latitude: float,
    longitude: float,
    iso_timestamp: str,
) -> str:
    return "|".join(
        [
            project_code.strip(),
            municipality.strip(),
            f"{float(progress_pct):.2f}",
            f"{float(paid_pct):.2f}",
            photo_hash.strip().lower(),
            f"{float(latitude):.6f}",
            f"{float(longitude):.6f}",
            iso_timestamp.strip(),
        ]
    )


def milestone_signature(
    project_code: str,
    municipality: str,
    progress_pct: float,
    paid_pct: float,
    photo_hash: str,
    latitude: float,
    longitude: float,
    iso_timestamp: str,
    secret: str | None = None,
) -> str:
    key = (secret or os.getenv("MILESTONE_HMAC_SECRET", "baladiya-dev-hmac-secret")).encode()
    payload = milestone_payload(
        project_code,
        municipality,
        progress_pct,
        paid_pct,
        photo_hash,
        latitude,
        longitude,
        iso_timestamp,
    )
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_packet_signature(packet, secret: str | None = None) -> bool:
    expected = milestone_signature(
        packet.project_code,
        packet.municipality,
        packet.progress_pct,
        packet.paid_pct,
        packet.photo_hash,
        packet.latitude,
        packet.longitude,
        packet.iso_timestamp,
        secret=secret,
    )
    return hmac.compare_digest(expected, packet.signature_hmac)


def sign_packet(packet, secret: str | None = None) -> str:
    return milestone_signature(
        packet.project_code,
        packet.municipality,
        packet.progress_pct,
        packet.paid_pct,
        packet.photo_hash,
        packet.latitude,
        packet.longitude,
        packet.iso_timestamp,
        secret=secret,
    )
