import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, precision_score, recall_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASELINE_VOTE_FEATURES = {
    "votes_per_minute": (0.05, 0.10),
    "amount_cv": (0.50, 0.15),
    "new_account_share": (0.05, 0.10),
}


def evaluate_progress_lag(
    progress_pct: float,
    paid_pct: float,
    rolling_lags: list[float] | None = None,
    z_threshold: float = 2.5,
) -> dict:
    lag = float(paid_pct) - float(progress_pct)
    z_score = 0.0
    if rolling_lags and len(rolling_lags) >= 3:
        mean = float(np.mean(rolling_lags))
        std = float(np.std(rolling_lags))
        if std > 0:
            z_score = (lag - mean) / std

    is_anomaly = lag > 20 or z_score > z_threshold
    if lag > 35 or z_score > 4:
        severity = "CRITICAL"
    elif is_anomaly:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "lag": round(lag, 4),
        "z_score": round(z_score, 4),
        "is_anomaly": is_anomaly,
        "severity": severity,
        "score": round(max(0.0, min(1.0, lag / 100.0)), 4),
    }


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_vote_dict(vote) -> dict:
    if isinstance(vote, dict):
        return vote
    return {
        "amount_tnd": vote.amount_tnd,
        "created_at": vote.created_at,
        "account_age_hours": getattr(vote, "account_age_hours", None),
        "voter_hash": vote.voter_hash,
    }


def extract_vote_features(votes, window_minutes: int = 10) -> dict:
    rows = [_as_vote_dict(vote) for vote in votes]
    if not rows:
        return {
            "vote_count": 0,
            "span_minutes": 0.0,
            "votes_per_minute": 0.0,
            "amount_mean": 0.0,
            "amount_std": 0.0,
            "amount_cv": 0.0,
            "new_account_share": 0.0,
        }

    timestamps = sorted(_parse_timestamp(row["created_at"]) for row in rows)
    span_minutes = max(
        (timestamps[-1] - timestamps[0]).total_seconds() / 60.0,
        1.0 / 60.0,
    )
    amounts = np.array([float(row["amount_tnd"]) for row in rows], dtype=float)
    amount_mean = float(np.mean(amounts))
    amount_std = float(np.std(amounts))
    amount_cv = amount_std / amount_mean if amount_mean > 0 else 0.0

    ages = [
        float(row["account_age_hours"])
        for row in rows
        if row.get("account_age_hours") is not None
    ]
    new_account_share = (
        sum(1 for age in ages if age < 24.0) / len(ages) if ages else 0.0
    )

    return {
        "vote_count": len(rows),
        "span_minutes": round(span_minutes, 4),
        "votes_per_minute": round(len(rows) / span_minutes, 4),
        "amount_mean": round(amount_mean, 4),
        "amount_std": round(amount_std, 4),
        "amount_cv": round(amount_cv, 4),
        "new_account_share": round(new_account_share, 4),
        "window_minutes": window_minutes,
    }


def score_sybil_features(features: dict, min_votes: int = 10) -> dict:
    velocity_mean, velocity_std = BASELINE_VOTE_FEATURES["votes_per_minute"]
    cv_mean, cv_std = BASELINE_VOTE_FEATURES["amount_cv"]
    new_mean, new_std = BASELINE_VOTE_FEATURES["new_account_share"]

    z_velocity = (features["votes_per_minute"] - velocity_mean) / velocity_std
    z_low_variance = (cv_mean - features["amount_cv"]) / cv_std
    z_new_accounts = (features["new_account_share"] - new_mean) / new_std

    max_z = max(0.0, z_velocity, z_low_variance, z_new_accounts)
    is_sybil = features["vote_count"] >= min_votes and max_z >= 2.5
    if max_z >= 6.0:
        severity = "CRITICAL"
    elif is_sybil:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "is_sybil": is_sybil,
        "severity": severity,
        "score": round(min(1.0, max_z / 6.0), 4),
        "z_scores": {
            "velocity": round(z_velocity, 4),
            "low_variance": round(z_low_variance, 4),
            "new_accounts": round(z_new_accounts, 4),
        },
        "features": features,
    }


def detect_sybil_votes(votes, window_minutes: int = 10) -> dict:
    features = extract_vote_features(votes, window_minutes=window_minutes)
    return score_sybil_features(features)


def detect_duplicate_photo(photo_hash: str, previous_hashes) -> dict:
    duplicate_count = sum(1 for value in previous_hashes if value == photo_hash)
    is_duplicate = bool(photo_hash) and duplicate_count > 0
    return {
        "is_duplicate": is_duplicate,
        "duplicate_count": duplicate_count,
        "severity": "CRITICAL" if is_duplicate else "LOW",
        "score": 1.0 if is_duplicate else 0.0,
    }


def detect_duplicate_photo_db(milestone_id) -> dict:
    from backend.tunisovereign_core.models import MilestoneReport

    milestone = MilestoneReport.objects.get(pk=milestone_id)
    previous_hashes = MilestoneReport.objects.filter(
        photo_hash=milestone.photo_hash,
        timestamp__lt=milestone.timestamp,
    ).values_list("photo_hash", flat=True)
    return detect_duplicate_photo(milestone.photo_hash, list(previous_hashes))


def detect_sybil_votes_db(proposal_id, window_minutes: int = 10) -> dict:
    from backend.tunisovereign_core.models import Vote

    votes = list(
        Vote.objects.filter(proposal_id=proposal_id)
        .order_by("created_at")
        .values("amount_tnd", "created_at", "voter_hash")
    )
    return detect_sybil_votes(votes, window_minutes=window_minutes)


def _metrics(y_true: list[int], y_pred: list[int]) -> dict:
    return {
        "samples": len(y_true),
        "true_anomalies": int(sum(y_true)),
        "predicted_anomalies": int(sum(y_pred)),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing; run `python -m simulator.tunisian_simulator` first"
        )
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def evaluate_on_simulator(data_dir: str | Path | None = None) -> dict:
    data_dir = Path(data_dir) if data_dir else PROJECT_ROOT / "simulator" / "data"
    vote_rows = _read_csv(data_dir / "votes.csv")
    milestone_rows = _read_csv(data_dir / "milestones.csv")

    vote_groups: dict[str, list[dict]] = {}
    for row in vote_rows:
        for key in ("amount_tnd", "account_age_hours", "label"):
            row[key] = float(row[key])
        vote_groups.setdefault(row["proposal_code"], []).append(row)

    vote_true = []
    vote_pred = []
    for proposal_code, votes in vote_groups.items():
        vote_true.append(int(any(vote["label"] == 1 for vote in votes)))
        vote_pred.append(int(detect_sybil_votes(votes)["is_sybil"]))

    milestone_rows.sort(key=lambda row: row["timestamp"])
    lag_true, lag_pred = [], []
    duplicate_true, duplicate_pred = [], []
    combined_true, combined_pred = [], []
    seen_hashes: set[str] = set()
    rolling_lags: dict[str, list[float]] = {}

    for row in milestone_rows:
        progress = float(row["progress_pct"])
        paid = float(row["paid_pct"])
        project_code = row["project_code"]
        history = rolling_lags.setdefault(project_code, [])
        lag_report = evaluate_progress_lag(progress, paid, rolling_lags=history)
        history.append(paid - progress)

        lag_anomaly = int(lag_report["is_anomaly"])
        lag_true.append(int(row.get("lag_label", row["label"]) == "1"))
        lag_pred.append(lag_anomaly)

        duplicate_anomaly = int(row["photo_hash"] in seen_hashes)
        duplicate_true.append(int(row["duplicate_photo"] == "1"))
        duplicate_pred.append(duplicate_anomaly)

        combined_true.append(int(row["label"] == "1"))
        combined_pred.append(int(lag_anomaly or duplicate_anomaly))
        seen_hashes.add(row["photo_hash"])

    return {
        "votes": _metrics(vote_true, vote_pred),
        "progress_lag": _metrics(lag_true, lag_pred),
        "duplicate_photo": _metrics(duplicate_true, duplicate_pred),
        "combined": _metrics(combined_true, combined_pred),
    }


class TunisianTelemetryAnomalyEngine:
    """Legacy Track 1 benchmark kept until the Streamlit dashboard is migrated."""

    def __init__(self, contamination: float = 0.08, random_state: int = 42):
        self.model = IsolationForest(
            n_estimators=150,
            contamination=contamination,
            random_state=random_state,
        )

    def fit_and_evaluate_synthetic_benchmark(self, n_samples: int = 500) -> dict:
        rng = np.random.default_rng(42)
        hours = np.linspace(0, 72, n_samples)
        moisture = 58.0 + 6.0 * np.sin(2 * np.pi * hours / 24.0) + rng.normal(0, 1.8, n_samples)
        temp = 26.0 - 5.0 * np.cos(2 * np.pi * hours / 24.0) + rng.normal(0, 1.1, n_samples)
        flow = 120.0 + 15.0 * np.sin(2 * np.pi * hours / 12.0) + rng.normal(0, 4.0, n_samples)

        y_true = np.zeros(n_samples, dtype=int)
        anomaly_indices = rng.choice(n_samples, size=40, replace=False)
        for idx in anomaly_indices:
            y_true[idx] = 1
            moisture[idx] -= rng.uniform(18.0, 28.0)
            temp[idx] += rng.uniform(8.0, 14.0)
            flow[idx] += rng.uniform(55.0, 95.0)

        X = np.column_stack([moisture, temp, flow])
        preds_raw = self.model.fit_predict(X)
        y_pred = (preds_raw == -1).astype(int)

        return {
            "samples": n_samples,
            "injected_anomalies": int(y_true.sum()),
            "detected_anomalies": int(y_pred.sum()),
            "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        }


if __name__ == "__main__":
    print(json.dumps(evaluate_on_simulator(), indent=2))
