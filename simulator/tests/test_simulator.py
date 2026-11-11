import csv
from pathlib import Path

from backend.tunisovereign_core.ml_anomaly import (
    detect_duplicate_photo,
    detect_sybil_votes,
    evaluate_on_simulator,
)
from simulator.tunisian_simulator import gen_milestones, gen_proposals, gen_votes, generate_dataset


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_simulator_is_reproducible_and_labelled(tmp_path):
    first = generate_dataset(n_proposals=40, output_dir=tmp_path / "first")
    second = generate_dataset(n_proposals=40, output_dir=tmp_path / "second")

    assert {**first, "output_dir": None} == {**second, "output_dir": None}
    assert first["proposals"] == 40
    assert first["duplicates"] == 10
    assert first["sybil_votes"] == 40
    assert first["duplicate_photos"] == 4

    for filename in ("proposals.csv", "votes.csv", "milestones.csv", "anomaly_labels.csv"):
        assert (tmp_path / "first" / filename).read_bytes() == (
            tmp_path / "second" / filename
        ).read_bytes()

    votes = _read(tmp_path / "first" / "votes.csv")
    milestones = _read(tmp_path / "first" / "milestones.csv")
    labels = _read(tmp_path / "first" / "anomaly_labels.csv")

    assert {"proposal_code", "amount_tnd", "label"} <= set(votes[0])
    assert {"project_code", "progress_pct", "paid_pct", "lag_label", "label"} <= set(
        milestones[0]
    )
    assert {"entity_type", "label", "anomaly_type"} <= set(labels[0])
    assert any(row["label"] == "1" for row in votes)
    assert any(row["lag_label"] == "1" for row in milestones)


def test_detectors_catch_injected_anomalies():
    proposals = gen_proposals(n=20)
    proposal = proposals[0]

    normal = gen_votes(proposal, n=20, sybil=False)
    sybil = gen_votes(proposal, n=40, sybil=True)
    assert detect_sybil_votes(normal)["is_sybil"] is False
    assert detect_sybil_votes(sybil)["is_sybil"] is True

    lagging = gen_milestones(proposal, lag_from_week=5)
    assert any(row["lag_label"] == 1 for row in lagging)
    clean = gen_milestones(proposal)
    assert all(row["lag_label"] == 0 for row in clean)

    duplicate = detect_duplicate_photo(clean[3]["photo_hash"], [clean[3]["photo_hash"]])
    assert duplicate["is_duplicate"] is True


def test_simulator_benchmark_reaches_expected_metrics(tmp_path):
    generate_dataset(n_proposals=40, output_dir=tmp_path)
    metrics = evaluate_on_simulator(tmp_path)

    assert metrics["votes"]["f1_score"] == 1.0
    assert metrics["progress_lag"]["f1_score"] == 1.0
    assert metrics["duplicate_photo"]["f1_score"] == 1.0
    assert metrics["combined"]["f1_score"] == 1.0
