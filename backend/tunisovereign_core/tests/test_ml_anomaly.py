from datetime import datetime, timedelta, timezone

from backend.tunisovereign_core.ml_anomaly import (
    detect_duplicate_photo,
    detect_sybil_votes,
    evaluate_progress_lag,
)


def _votes(count, minutes, amount, age, spread=0.0):
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return [
        {
            "amount_tnd": amount + (index % 2) * spread,
            "created_at": start + timedelta(seconds=index * minutes * 60 / count),
            "account_age_hours": age,
            "voter_hash": f"0x{index:064d}",
        }
        for index in range(count)
    ]


def test_sybil_burst_is_detected():
    report = detect_sybil_votes(_votes(40, 3, 10.0, 2.0, spread=0.01))
    assert report["is_sybil"] is True
    assert report["severity"] == "CRITICAL"
    assert report["features"]["votes_per_minute"] > 5


def test_normal_votes_are_not_flagged():
    report = detect_sybil_votes(_votes(30, 60 * 24 * 7, 10.0, 500.0, spread=5.0))
    assert report["is_sybil"] is False
    assert report["severity"] == "LOW"


def test_duplicate_photo_hash_is_detected():
    digest = "a" * 64
    assert detect_duplicate_photo(digest, [digest])["is_duplicate"] is True
    assert detect_duplicate_photo(digest, ["b" * 64])["is_duplicate"] is False


def test_progress_lag_severity():
    assert evaluate_progress_lag(60.0, 61.0)["severity"] == "LOW"
    assert evaluate_progress_lag(40.0, 65.0)["severity"] == "MEDIUM"
    assert evaluate_progress_lag(20.0, 80.0)["severity"] == "CRITICAL"
