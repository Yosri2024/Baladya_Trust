"""
Baladiya-Trust reproducible municipal simulator.

Generates:
- 200 proposals (FR + Tunisian Darja) with 25% deliberate duplicates
- normal and sybil vote bursts
- weekly S-curve milestone reports with progress lag and reused photos
- CSV files with ground-truth labels for Precision / Recall / F1
"""
import argparse
import csv
import hashlib
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from grpc_service.security import milestone_signature

BASE_TIME = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
SEED = 42

MUNICIPALITIES = [
    {"name": "Kasserine", "governorate": "Kasserine", "lat": 35.1676, "lon": 8.8365},
    {"name": "Sidi_Bouzid", "governorate": "Sidi_Bouzid", "lat": 35.0382, "lon": 9.4849},
    {"name": "Gafsa", "governorate": "Gafsa", "lat": 34.4250, "lon": 8.7842},
    {"name": "Kairouan", "governorate": "Kairouan", "lat": 35.6781, "lon": 10.0963},
    {"name": "Tozeur", "governorate": "Tozeur", "lat": 33.9197, "lon": 8.1335},
    {"name": "Tunis", "governorate": "Tunis", "lat": 36.8065, "lon": 10.1815},
]

LOCALITIES = [
    "Sbeitla",
    "Regueb",
    "Metlaoui",
    "Cherarda",
    "Nefta",
    "Le Kram",
    "Haffouz",
    "Jelma",
]

CATEGORY_TEMPLATES = {
    "ROAD": [
        "Réparer la route de {q}",
        "tarmim triq {q}",
        "إصلاح طريق {q}",
        "aslah triq {q}",
    ],
    "LIGHTING": [
        "Éclairage public à {q}",
        "tajdid el daw fi {q}",
        "إنارة الشوارع في {q}",
        "daw el charea fi {q}",
    ],
    "SCHOOL": [
        "Rénover l'école de {q}",
        "islah el madrasa fi {q}",
        "ترميم مدرسة {q}",
        "tajdid el madrasa fi {q}",
    ],
    "WASTE": [
        "Collecte des déchets à {q}",
        "tanzif {q}",
        "نظافة {q}",
        "ramy el zbel fi {q}",
    ],
}


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in text)


def _voter_hash(seed: str) -> str:
    return "0x" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def gen_proposals(n: int = 200, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    n_duplicates = n // 4
    n_unique = n - n_duplicates
    proposals = []

    for index in range(n_unique):
        municipality = rng.choice(MUNICIPALITIES)
        category = rng.choice(list(CATEGORY_TEMPLATES))
        locality = rng.choice(LOCALITIES)
        template = rng.choice(CATEGORY_TEMPLATES[category])
        text = template.format(q=locality)
        proposals.append(
            {
                "project_code": f"SIM-{index:04d}",
                "municipality": municipality["name"],
                "governorate": municipality["governorate"],
                "latitude": municipality["lat"],
                "longitude": municipality["lon"],
                "title": f"{category.title()} - {locality}",
                "text": text,
                "language": "ar-TN" if _is_arabic(text) else "fr",
                "category": category,
                "cluster_id": f"CL-{index:03d}",
                "locality": locality,
                "estimated_cost_tnd": round(rng.uniform(20_000, 400_000), 2),
                "author_username": f"sim_citizen_{index % 40:02d}",
                "is_duplicate": False,
            }
        )

    for index in range(n_duplicates):
        base = rng.choice(proposals[:n_unique])
        templates = [
            template
            for template in CATEGORY_TEMPLATES[base["category"]]
            if template.format(q=base["locality"]) != base["text"]
        ]
        text = rng.choice(templates).format(q=base["locality"])
        proposals.append(
            {
                "project_code": f"SIM-D{index:04d}",
                "municipality": base["municipality"],
                "governorate": base["governorate"],
                "latitude": base["latitude"],
                "longitude": base["longitude"],
                "title": base["title"],
                "text": text,
                "language": "ar-TN" if _is_arabic(text) else "fr",
                "category": base["category"],
                "cluster_id": base["cluster_id"],
                "locality": base["locality"],
                "estimated_cost_tnd": round(
                    base["estimated_cost_tnd"] * rng.uniform(0.85, 1.15), 2
                ),
                "author_username": f"sim_citizen_{rng.randint(0, 39):02d}",
                "is_duplicate": True,
            }
        )

    return proposals


def gen_votes(proposal: dict, n: int = 20, sybil: bool = False, seed: int = SEED) -> list[dict]:
    rng = random.Random(f"{seed}:{proposal['project_code']}:{'sybil' if sybil else 'normal'}")
    start = BASE_TIME + timedelta(days=rng.randint(0, 20), minutes=rng.randint(0, 600))
    votes = []

    for index in range(n):
        if sybil:
            created_at = start + timedelta(seconds=rng.randint(0, 180))
            amount = round(10.0 + rng.uniform(-0.05, 0.05), 2)
            account_age_hours = round(rng.uniform(0.1, 24.0), 2)
        else:
            created_at = start + timedelta(hours=rng.randint(0, 24 * 14))
            amount = round(rng.uniform(1.0, 20.0), 2)
            account_age_hours = round(rng.uniform(24.0, 2000.0), 2)

        votes.append(
            {
                "proposal_code": proposal["project_code"],
                "voter_hash": _voter_hash(f"{proposal['project_code']}:{index}:{start.isoformat()}"),
                "amount_tnd": amount,
                "created_at": created_at.isoformat(),
                "account_age_hours": account_age_hours,
                "label": 1 if sybil else 0,
            }
        )

    return votes


def _s_curve(week: float) -> float:
    return 100.0 / (1.0 + math.exp(-0.9 * (week - 6.0)))


def gen_milestones(
    proposal: dict,
    weeks: int = 12,
    lag_from_week: int | None = None,
    seed: int = SEED,
) -> list[dict]:
    rng = random.Random(f"{seed}:{proposal['project_code']}:milestones")
    milestones = []

    for week in range(1, weeks + 1):
        progress = _s_curve(week)
        paid = min(100.0, _s_curve(week) + 8.0)

        if lag_from_week is not None and week >= lag_from_week:
            progress = _s_curve(lag_from_week)
            paid = min(100.0, _s_curve(week) + 8.0)

        lag = paid - progress
        photo_hash = hashlib.sha256(
            f"{proposal['project_code']}:{week}".encode("utf-8")
        ).hexdigest()
        timestamp = BASE_TIME + timedelta(weeks=week)
        latitude = proposal["latitude"] + rng.uniform(-0.01, 0.01)
        longitude = proposal["longitude"] + rng.uniform(-0.01, 0.01)

        milestones.append(
            {
                "project_code": proposal["project_code"],
                "municipality": proposal["municipality"],
                "timestamp": timestamp.isoformat(),
                "progress_pct": round(progress, 2),
                "paid_pct": round(paid, 2),
                "lag": round(lag, 2),
                "photo_hash": photo_hash,
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "duplicate_photo": 0,
                "lag_label": 1 if lag > 20 else 0,
                "label": 1 if lag > 20 else 0,
            }
        )

    return milestones


def _inject_duplicate_photos(
    milestone_sets: list[list[dict]], rng: random.Random, pairs: int = 4
) -> None:
    candidates = [milestones for milestones in milestone_sets if len(milestones) >= 6]
    rng.shuffle(candidates)
    for milestones in candidates[:pairs]:
        source = milestones[3]
        duplicate = milestones[5]
        duplicate["photo_hash"] = source["photo_hash"]
        duplicate["duplicate_photo"] = 1
        duplicate["label"] = 1


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_dataset(
    n_proposals: int = 200,
    seed: int = SEED,
    output_dir: Path | str = "simulator/data",
) -> dict:
    output_dir = Path(output_dir)
    rng = random.Random(seed)
    proposals = gen_proposals(n=n_proposals, seed=seed)

    votes = []
    milestone_sets = []
    for proposal in proposals:
        sybil = proposal["category"] in ("ROAD", "WASTE") and rng.random() < 0.12
        votes.extend(
            gen_votes(
                proposal,
                n=40 if sybil else rng.randint(5, 40),
                sybil=sybil,
                seed=seed,
            )
        )
        lag_from_week = rng.choice([None, None, None, 5, 7, 9])
        milestone_sets.append(
            gen_milestones(
                proposal,
                weeks=12,
                lag_from_week=lag_from_week,
                seed=seed,
            )
        )

    _inject_duplicate_photos(milestone_sets, rng)
    milestones = [row for rows in milestone_sets for row in rows]

    _write_csv(
        output_dir / "proposals.csv",
        proposals,
        [
            "project_code",
            "municipality",
            "governorate",
            "latitude",
            "longitude",
            "title",
            "text",
            "language",
            "category",
            "cluster_id",
            "locality",
            "estimated_cost_tnd",
            "author_username",
            "is_duplicate",
        ],
    )
    _write_csv(
        output_dir / "votes.csv",
        votes,
        [
            "proposal_code",
            "voter_hash",
            "amount_tnd",
            "created_at",
            "account_age_hours",
            "label",
        ],
    )
    _write_csv(
        output_dir / "milestones.csv",
        milestones,
        [
            "project_code",
            "municipality",
            "timestamp",
            "progress_pct",
            "paid_pct",
            "lag",
            "photo_hash",
            "latitude",
            "longitude",
            "duplicate_photo",
            "lag_label",
            "label",
        ],
    )

    labels = []
    for vote in votes:
        labels.append(
            {
                "entity_type": "vote",
                "proposal_code": vote["proposal_code"],
                "timestamp": vote["created_at"],
                "label": vote["label"],
                "anomaly_type": "SYBIL_VOTES" if vote["label"] else "NORMAL",
            }
        )
    for milestone in milestones:
        anomaly_type = "NORMAL"
        if milestone["duplicate_photo"]:
            anomaly_type = "DUPLICATE_PHOTO"
        elif milestone["label"]:
            anomaly_type = "PROGRESS_LAG"
        labels.append(
            {
                "entity_type": "milestone",
                "proposal_code": milestone["project_code"],
                "timestamp": milestone["timestamp"],
                "label": milestone["label"],
                "anomaly_type": anomaly_type,
            }
        )
    _write_csv(
        output_dir / "anomaly_labels.csv",
        labels,
        ["entity_type", "proposal_code", "timestamp", "label", "anomaly_type"],
    )

    return {
        "proposals": len(proposals),
        "duplicates": sum(1 for row in proposals if row["is_duplicate"]),
        "votes": len(votes),
        "sybil_votes": sum(row["label"] for row in votes),
        "milestones": len(milestones),
        "lagging_milestones": sum(
            1 for row in milestones if row["label"] and not row["duplicate_photo"]
        ),
        "duplicate_photos": sum(row["duplicate_photo"] for row in milestones),
        "output_dir": str(output_dir),
    }


def send_milestones_grpc(
    milestones: list[dict],
    target: str = "localhost:50051",
    secret: str | None = None,
) -> dict:
    import grpc

    from grpc_service import baladiya_pb2, baladiya_pb2_grpc

    packets = []
    for row in milestones:
        packet = baladiya_pb2.MilestonePacket(
            project_code=row["project_code"],
            municipality=row["municipality"],
            progress_pct=row["progress_pct"],
            paid_pct=row["paid_pct"],
            photo_hash=row["photo_hash"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            iso_timestamp=row["timestamp"],
        )
        packet.signature_hmac = milestone_signature(
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
        packets.append(packet)

    with grpc.insecure_channel(target) as channel:
        stub = baladiya_pb2_grpc.MilestoneIngestServiceStub(channel)
        ack = stub.StreamMilestones(iter(packets))

    return {
        "accepted_count": ack.accepted_count,
        "anomaly_triggered": ack.anomaly_triggered,
        "agent_thread_id": ack.agent_thread_id,
    }


def seed_django_proposals(proposals: list[dict]) -> dict:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from backend.tunisovereign_core.models import Municipality, Proposal, StakeholderUser

    municipalities = {}
    for row in proposals:
        municipality = municipalities.get(row["municipality"])
        if municipality is None:
            municipality, _ = Municipality.objects.get_or_create(
                name=row["municipality"],
                defaults={
                    "governorate": row["governorate"],
                    "total_budget_tnd": 1_200_000,
                    "matching_pool_tnd": 150_000,
                },
            )
            municipalities[row["municipality"]] = municipality

    author, _ = StakeholderUser.objects.get_or_create(username="sim_author")
    Proposal.objects.filter(project_code__startswith="SIM-").delete()
    created = 0
    for row in proposals:
        Proposal.objects.create(
            municipality=municipalities[row["municipality"]],
            author=author,
            project_code=row["project_code"],
            title=row["title"],
            text=row["text"],
            language=row["language"],
            category=row["category"],
            cluster_id=row["cluster_id"],
            estimated_cost_tnd=row["estimated_cost_tnd"],
            status=Proposal.Status.SUBMITTED,
        )
        created += 1

    return {"municipalities": len(municipalities), "proposals": created}


def main() -> None:
    parser = argparse.ArgumentParser(description="Baladiya-Trust municipal simulator")
    parser.add_argument("--n-proposals", type=int, default=200)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output-dir", default="simulator/data")
    parser.add_argument("--send-grpc", action="store_true")
    parser.add_argument("--target", default="localhost:50051")
    parser.add_argument("--seed-django", action="store_true")
    args = parser.parse_args()

    summary = generate_dataset(
        n_proposals=args.n_proposals,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print("Dataset generated:", summary)

    if args.seed_django:
        import csv as _csv

        with (Path(args.output_dir) / "proposals.csv").open(encoding="utf-8") as handle:
            proposals = list(_csv.DictReader(handle))
        print("Django seed:", seed_django_proposals(proposals))

    if args.send_grpc:
        import csv as _csv

        with (Path(args.output_dir) / "milestones.csv").open(encoding="utf-8") as handle:
            milestones = list(_csv.DictReader(handle))
        for row in milestones:
            row["progress_pct"] = float(row["progress_pct"])
            row["paid_pct"] = float(row["paid_pct"])
            row["latitude"] = float(row["latitude"])
            row["longitude"] = float(row["longitude"])
        print("gRPC ack:", send_milestones_grpc(milestones, target=args.target))


if __name__ == "__main__":
    main()
