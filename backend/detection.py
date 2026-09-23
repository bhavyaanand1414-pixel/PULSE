"""
PULSE — Statistical Anomaly Detection Engine

This module implements Z-score based anomaly detection for API metrics.

How Z-score detection works:
──────────────────────────────
1. For each endpoint, we look at historical metrics to establish a "baseline"
   (what normal behavior looks like).

2. We calculate the MEAN (average) and STANDARD DEVIATION (spread) of each
   metric type (response_time, error_rate, request_count).

3. For each new observation, we calculate the Z-score:

       Z = (observed_value - mean) / standard_deviation

4. The Z-score tells us "how many standard deviations away from normal
   is this value?"

   - Z = 0    → exactly average (normal)
   - Z = 2    → 2 std devs from average (starting to be unusual)
   - Z = 3    → 3 std devs from average (very unusual, ~0.3% probability)
   - Z = 4+   → extremely unusual

5. Based on the Z-score, we assign a severity level:
   - |Z| >= 2.0  → LOW      (somewhat unusual)
   - |Z| >= 2.5  → MEDIUM   (unusual)
   - |Z| >= 3.0  → HIGH     (very unusual)
   - |Z| >= 4.0  → CRITICAL (extremely unusual)

Why Z-score?
- Simple and well-understood (easy to explain in an interview)
- Works well when data is roughly normally distributed
- Doesn't require machine learning or training
- Fast to compute
"""

import numpy as np
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import Metric, Anomaly, Endpoint


# ── Severity Thresholds ────────────────────────────────────────────────────
# These Z-score thresholds determine severity levels.
# A Z-score of 2 means the value is 2 standard deviations from the mean.

SEVERITY_THRESHOLDS = {
    "CRITICAL": 4.0,
    "HIGH": 3.0,
    "MEDIUM": 2.5,
    "LOW": 2.0,
}

# Minimum number of data points needed to compute meaningful statistics.
# With too few points, the mean and std dev are unreliable.
MIN_DATA_POINTS = 20


def classify_severity(z_score: float) -> str | None:
    """
    Convert a Z-score into a severity level.

    We use the absolute value because anomalies can go both directions:
    - High latency (positive Z) is bad
    - Unusually low traffic (negative Z) might also be concerning

    Returns None if the Z-score is below the LOW threshold (not anomalous).
    """
    abs_z = abs(z_score)
    if abs_z >= SEVERITY_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    elif abs_z >= SEVERITY_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif abs_z >= SEVERITY_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    elif abs_z >= SEVERITY_THRESHOLDS["LOW"]:
        return "LOW"
    return None  # Not anomalous


def run_zscore_detection(db: Session, endpoint_id: int) -> list[Anomaly]:
    """
    Run Z-score anomaly detection on all metrics for a given endpoint.

    Steps:
    1. Fetch all metrics for the endpoint, ordered by time.
    2. Extract arrays of response_time, error_rate, and request_count.
    3. Calculate mean and std dev for each metric type.
    4. Compute Z-score for each observation.
    5. If Z-score exceeds the LOW threshold, create an Anomaly record.

    Returns: list of new Anomaly objects that were saved to the database.
    """
    # Verify endpoint exists
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise ValueError(f"Endpoint {endpoint_id} not found")

    # Fetch all metrics for this endpoint, ordered chronologically
    metrics = (
        db.query(Metric)
        .filter(Metric.endpoint_id == endpoint_id)
        .order_by(Metric.timestamp.asc())
        .all()
    )

    if len(metrics) < MIN_DATA_POINTS:
        return []  # Not enough data for meaningful detection

    # ── Extract metric values into NumPy arrays ────────────────────────
    # NumPy arrays are efficient for mathematical operations on large datasets.
    response_times = np.array([m.response_time for m in metrics])
    request_counts = np.array([m.request_count for m in metrics], dtype=float)

    # Error rate = error_count / request_count (proportion of failed requests)
    # We use np.where to avoid division by zero when request_count is 0
    error_rates = np.where(
        request_counts > 0,
        np.array([m.error_count for m in metrics]) / request_counts,
        0.0,
    )

    # ── Calculate baselines (mean and standard deviation) ──────────────
    # mean = average value (the "center" of normal behavior)
    # std  = standard deviation (how spread out the values are)
    baselines = {
        "response_time": {
            "values": response_times,
            "mean": float(np.mean(response_times)),
            "std": float(np.std(response_times)),
            "unit": "ms",
        },
        "error_rate": {
            "values": error_rates,
            "mean": float(np.mean(error_rates)),
            "std": float(np.std(error_rates)),
            "unit": "%",
        },
        "request_count": {
            "values": request_counts,
            "mean": float(np.mean(request_counts)),
            "std": float(np.std(request_counts)),
            "unit": "reqs",
        },
    }

    # ── Detect anomalies ───────────────────────────────────────────────
    new_anomalies = []
    now = datetime.now(timezone.utc)

    # Check which anomalies we've already detected (avoid duplicates)
    existing_anomaly_metric_ids = set(
        row[0]
        for row in db.query(Anomaly.metric_id)
        .filter(
            Anomaly.endpoint_id == endpoint_id,
            Anomaly.detection_method == "z_score",
        )
        .all()
        if row[0] is not None
    )

    for i, metric in enumerate(metrics):
        for metric_type, baseline in baselines.items():
            # Skip if standard deviation is 0 (all values identical — no variation)
            if baseline["std"] == 0:
                continue

            observed = float(baseline["values"][i])

            # ── Calculate Z-score ──────────────────────────────────
            # Z = (observed - mean) / std_dev
            # This tells us how many standard deviations the value is
            # from the average.
            z_score = (observed - baseline["mean"]) / baseline["std"]

            severity = classify_severity(z_score)

            if severity is None:
                continue  # Not anomalous — skip

            # Skip if we already detected this metric+type combination
            if metric.id in existing_anomaly_metric_ids:
                continue

            # For response_time and error_rate, we only care about HIGH values
            # (slow responses and high errors are bad).
            # For request_count, both spikes and drops can be anomalous.
            if metric_type in ("response_time", "error_rate") and z_score < 0:
                continue  # Below average latency/errors is fine, not anomalous

            # ── Create description ─────────────────────────────────
            description = _build_description(
                metric_type, observed, baseline["mean"], z_score, baseline["unit"]
            )

            anomaly = Anomaly(
                endpoint_id=endpoint_id,
                metric_id=metric.id,
                metric_type=metric_type,
                observed_value=round(observed, 4),
                expected_value=round(baseline["mean"], 4),
                anomaly_score=round(abs(z_score), 4),
                severity=severity,
                detection_method="z_score",
                description=description,
                timestamp=metric.timestamp,
                detected_at=now,
            )
            new_anomalies.append(anomaly)

    # Bulk save all detected anomalies
    if new_anomalies:
        db.add_all(new_anomalies)
        db.commit()

    return new_anomalies


def _build_description(
    metric_type: str,
    observed: float,
    mean: float,
    z_score: float,
    unit: str,
) -> str:
    """
    Build a human-readable description of an anomaly.

    Example output:
    "Response time is 850.5ms, which is 4.2 standard deviations above
     the average of 120.3ms"
    """
    direction = "above" if z_score > 0 else "below"
    abs_z = abs(z_score)

    labels = {
        "response_time": "Response time",
        "error_rate": "Error rate",
        "request_count": "Request count",
    }
    label = labels.get(metric_type, metric_type)

    if unit == "%":
        return (
            f"{label} is {observed:.1%}, which is {abs_z:.1f} standard deviations "
            f"{direction} the average of {mean:.1%}"
        )
    else:
        return (
            f"{label} is {observed:.1f}{unit}, which is {abs_z:.1f} standard deviations "
            f"{direction} the average of {mean:.1f}{unit}"
        )
