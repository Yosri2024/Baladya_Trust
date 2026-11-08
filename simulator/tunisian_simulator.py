"""
Tunisian Governorate Telemetry & Anomaly Stream Simulator
Generates diurnal/seasonal telemetry across Kasserine, Sidi Bouzid, Gafsa, Kairouan, and Tozeur,
injects controlled stress anomalies, and triggers the TuniSovereign-AI pipeline.
"""
import hashlib
import hmac
import math
import random
from datetime import datetime, timezone


GOVERNORATE_NODES = [
    {"node_code": "KAS-SBEITLA-PLOT-04", "governorate": "Kasserine", "base_moisture": 54.0, "base_temp": 27.0},
    {"node_code": "SBZ-REGUEB-PLOT-02", "governorate": "Sidi_Bouzid", "base_moisture": 52.0, "base_temp": 28.5},
    {"node_code": "GAF-METLAOUI-NODE-01", "governorate": "Gafsa", "base_moisture": 49.0, "base_temp": 30.0},
    {"node_code": "KAI-CHERARDA-PLOT-07", "governorate": "Kairouan", "base_moisture": 55.0, "base_temp": 27.5},
    {"node_code": "TOZ-NEFTA-OASIS-03", "governorate": "Tozeur", "base_moisture": 48.0, "base_temp": 32.0},
]


def generate_telemetry_batch(hours: int = 24, inject_anomaly_at_hour: int = 14, secret_key: str = "tunisovereign-hmac") -> list:
    rng = random.Random(42)
    packets = []
    for h in range(hours):
        for node in GOVERNORATE_NODES:
            diurnal = math.sin(2 * math.pi * h / 24.0)
            moisture = node["base_moisture"] + 5.0 * diurnal + rng.uniform(-1.5, 1.5)
            temp_c = node["base_temp"] - 4.5 * math.cos(2 * math.pi * h / 24.0) + rng.uniform(-0.8, 0.8)

            if h in (inject_anomaly_at_hour, inject_anomaly_at_hour + 1) and node["governorate"] == "Kasserine":
                moisture -= 24.5
                temp_c += 9.5

            iso_ts = datetime.now(timezone.utc).isoformat()
            payload_str = f"{node['node_code']}|{node['governorate']}|MOISTURE|{moisture:.2f}|{iso_ts}"
            sig = hmac.new(secret_key.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

            packets.append({
                "hour": h,
                "node_code": node["node_code"],
                "governorate": node["governorate"],
                "metric_type": "MOISTURE",
                "moisture_pct": round(moisture, 2),
                "temp_c": round(temp_c, 2),
                "iso_timestamp": iso_ts,
                "signature_hmac": sig,
            })
    return packets


if __name__ == "__main__":
    batch = generate_telemetry_batch(hours=24, inject_anomaly_at_hour=14)
    print(f"Generated {len(batch)} signed Tunisian telemetry packets across {len(GOVERNORATE_NODES)} governorates.")
    anomalies = [p for p in batch if p["moisture_pct"] < 35.0]
    print(f"Injected critical anomaly packets (<35% moisture): {len(anomalies)}")
    if anomalies:
        print("Sample critical packet:", anomalies[0])
