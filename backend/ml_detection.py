"""
PULSE — Machine Learning Anomaly Detection (Isolation Forest)

This module uses scikit-learn's IsolationForest algorithm to detect
anomalies in API metrics using a MULTI-DIMENSIONAL approach.

How Isolation Forest works:
────────────────────────────
1. It builds a collection ("forest") of random decision trees.
2. Each tree randomly picks a feature and a split value to divide data.
3. ANOMALIES are data points that are easy to isolate — they need
   fewer random splits to be separated from the rest.
4. NORMAL points are deep in the tree (hard to isolate — they blend
   in with the crowd).

Why Isolation Forest?
- Works on MULTIPLE features at once (response_time + error_rate + request_count).
- No assumption about data distribution (unlike Z-score which assumes normal).
- Handles complex anomaly patterns that single-metric Z-score might miss.
- Unsupervised — no labeled training data needed.

Key difference from Z-score:
- Z-score asks: "Is this ONE metric value unusual?"
- Isolation Forest asks: "Is this COMBINATION of values unusual?"

Example: A response time of 300ms might be normal on its own,
but 300ms COMBINED WITH 200 requests and 50% error rate is definitely anomalous.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import Metric, Anomaly, Endpoint


# Minimum data points needed to train Isolation Forest reliably
MIN_DATA_POINTS = 30

# contamination: the expected proportion of anomalies in the dataset.
# 0.05 means we expect about 5% of data points to be anomalous.
# This helps the algorithm calibrate its threshold.
CONTAMINATION = 0.05


def run_isolation_forest_detection(db: Session, endpoint_id: int) -> list[Anomaly]:
    """
    Run Isolation Forest anomaly detection on all metrics for an endpoint.

    Steps:
    1. Fetch all metrics for the endpoint.
    2. Build a feature matrix with: response_time, error_rate, request_count.
    3. Train an IsolationForest model on this data.
    4. Predict which observations are anomalies (-1) vs normal (1).
    5. For anomalies, calculate severity using the anomaly score.
    6. Save results to the database.

    Returns: list of new Anomaly objects saved to the database.
    """
    # Verify endpoint exists
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise ValueError(f"Endpoint {endpoint_id} not found")

    # Fetch metrics ordered chronologically
    metrics = (
        db.query(Metric)
        .filter(Metric.endpoint_id == endpoint_id)
        .order_by(Metric.timestamp.asc())
        .all()
    )

    if len(metrics) < MIN_DATA_POINTS:
        return []

    # ── Build feature matrix ───────────────────────────────────────────
    # Each row = one metric observation
    # Each column = one feature the algorithm considers
    #
    # We use a pandas DataFrame for clarity (column names make it readable)
    df = pd.DataFrame([
        {
            "response_time": m.response_time,
            "error_rate": m.error_count / max(m.request_count, 1),  # Avoid division by zero
            "request_count": float(m.request_count),
            "metric_id": m.id,
            "timestamp": m.timestamp,
        }
        for m in metrics
    ])

    # Features used for detection (only numeric columns)
    feature_columns = ["response_time", "error_rate", "request_count"]
    X = df[feature_columns].values  # Convert to NumPy array for sklearn

    # ── Train Isolation Forest ─────────────────────────────────────────
    # n_estimators: number of trees in the forest (100 is a good default)
    # contamination: expected fraction of anomalies (5%)
    # random_state: fixed seed for reproducible results
    model = IsolationForest(
        n_estimators=100,
        contamination=CONTAMINATION,
        random_state=42,
    )

    # fit_predict() trains the model AND predicts in one step:
    # Returns: 1 for normal, -1 for anomaly
    predictions = model.fit_predict(X)

    # decision_function() returns the anomaly SCORE for each point.
    # More negative = more anomalous. We negate it so higher = more anomalous.
    anomaly_scores = -model.decision_function(X)

    # ── Process results ────────────────────────────────────────────────
    # Check which anomalies we've already detected (avoid duplicates)
    existing_ids = set(
        row[0]
        for row in db.query(Anomaly.metric_id)
        .filter(
            Anomaly.endpoint_id == endpoint_id,
            Anomaly.detection_method == "isolation_forest",
        )
        .all()
        if row[0] is not None
    )

    # Calculate baseline values for descriptions
    mean_rt = float(np.mean(df["response_time"]))
    mean_er = float(np.mean(df["error_rate"]))
    mean_rc = float(np.mean(df["request_count"]))

    new_anomalies = []
    now = datetime.now(timezone.utc)

    for i in range(len(df)):
        if predictions[i] != -1:
            continue  # Not flagged as anomaly — skip

        metric_id = int(df.iloc[i]["metric_id"])
        if metric_id in existing_ids:
            continue  # Already detected

        score = float(anomaly_scores[i])
        severity = _score_to_severity(score)

        # Determine which metric contributed most to the anomaly
        # by checking which feature deviated the most from its mean
        rt_dev = abs(df.iloc[i]["response_time"] - mean_rt) / max(mean_rt, 1)
        er_dev = abs(df.iloc[i]["error_rate"] - mean_er) / max(mean_er, 0.001)
        rc_dev = abs(df.iloc[i]["request_count"] - mean_rc) / max(mean_rc, 1)

        deviations = {
            "response_time": rt_dev,
            "error_rate": er_dev,
            "request_count": rc_dev,
        }
        # Pick the metric that deviated the most
        primary_metric = max(deviations, key=deviations.get)

        observed = float(df.iloc[i][primary_metric])
        expected_map = {
            "response_time": mean_rt,
            "error_rate": mean_er,
            "request_count": mean_rc,
        }
        expected = expected_map[primary_metric]

        description = _build_if_description(
            primary_metric, observed, expected, score
        )

        anomaly = Anomaly(
            endpoint_id=endpoint_id,
            metric_id=metric_id,
            metric_type=primary_metric,
            observed_value=round(observed, 4),
            expected_value=round(expected, 4),
            anomaly_score=round(score, 4),
            severity=severity,
            detection_method="isolation_forest",
            description=description,
            timestamp=df.iloc[i]["timestamp"],
            detected_at=now,
        )
        new_anomalies.append(anomaly)

    if new_anomalies:
        db.add_all(new_anomalies)
        db.commit()

    return new_anomalies


def _score_to_severity(score: float) -> str:
    """
    Convert an Isolation Forest anomaly score to a severity level.

    The score from decision_function() (negated) typically ranges from
    about -0.1 (very normal) to 0.3+ (very anomalous).
    We map these to severity levels based on practical thresholds.
    """
    if score >= 0.25:
        return "CRITICAL"
    elif score >= 0.15:
        return "HIGH"
    elif score >= 0.10:
        return "MEDIUM"
    else:
        return "LOW"


def _build_if_description(
    metric_type: str, observed: float, expected: float, score: float
) -> str:
    """Build a human-readable description for an Isolation Forest anomaly."""
    labels = {
        "response_time": "Response time",
        "error_rate": "Error rate",
        "request_count": "Request count",
    }
    label = labels.get(metric_type, metric_type)

    if metric_type == "error_rate":
        return (
            f"Isolation Forest flagged unusual pattern: {label} is {observed:.1%} "
            f"(baseline {expected:.1%}), anomaly score {score:.3f}"
        )
    else:
        unit = "ms" if metric_type == "response_time" else "reqs"
        return (
            f"Isolation Forest flagged unusual pattern: {label} is {observed:.1f}{unit} "
            f"(baseline {expected:.1f}{unit}), anomaly score {score:.3f}"
        )
