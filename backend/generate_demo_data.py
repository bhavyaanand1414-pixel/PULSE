"""
PULSE — Demo Data Generator

This script generates SIMULATED API metrics for testing and demonstration.
It creates realistic patterns of normal and anomalous API behavior.

THIS IS NOT REAL PRODUCTION DATA — it is clearly labeled demo data.

Usage:
    cd backend
    source venv/bin/activate
    python generate_demo_data.py

What it generates:
    - 3 demo API endpoints (if they don't already exist)
    - 7 days of metrics, one data point every 5 minutes per endpoint
    - Normal behavior: stable latency, consistent traffic, low errors
    - Anomalies: latency spikes, traffic surges, error bursts

Each endpoint has slightly different "personality" to make the data realistic:
    - User Service: fast (avg 120ms), high traffic
    - Payment Service: medium speed (avg 250ms), medium traffic
    - Search Service: variable speed (avg 180ms), lower traffic
"""

import random
import sys
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import Endpoint, Metric


# ── Configuration ──────────────────────────────────────────────────────────

# Demo endpoints to create (name, url, avg_latency_ms, avg_requests_per_interval)
DEMO_ENDPOINTS = [
    {
        "name": "User Service [demo]",
        "url": "https://api.demo.pulse/v1/users",
        "avg_latency": 120,     # Average response time in ms
        "avg_requests": 50,     # Average requests per 5-min window
        "error_rate": 0.02,     # 2% baseline error rate
    },
    {
        "name": "Payment Service [demo]",
        "url": "https://api.demo.pulse/v1/payments",
        "avg_latency": 250,
        "avg_requests": 30,
        "error_rate": 0.01,     # 1% baseline — payments are reliable
    },
    {
        "name": "Search Service [demo]",
        "url": "https://api.demo.pulse/v1/search",
        "avg_latency": 180,
        "avg_requests": 40,
        "error_rate": 0.03,     # 3% baseline
    },
]

# Time range: 7 days of history, one data point every 5 minutes
DAYS_OF_DATA = 7
INTERVAL_MINUTES = 5

# Anomaly settings
# Probability that any given 5-min interval is anomalous
ANOMALY_PROBABILITY = 0.03  # ~3% of intervals will have an anomaly


# ── Helper Functions ───────────────────────────────────────────────────────

def generate_normal_metric(config: dict, timestamp: datetime) -> dict:
    """
    Generate a single NORMAL metric data point.

    Uses random.gauss() (Gaussian/normal distribution) to create realistic
    variation around the average values. In real APIs, response times naturally
    fluctuate around a baseline — this simulates that behavior.

    random.gauss(mean, std_dev):
        - mean: the center value (e.g., 120ms average latency)
        - std_dev: how much it varies (higher = more spread)
        Example: gauss(120, 20) mostly produces values between 80-160ms
    """
    # Latency: normally distributed around the endpoint's average
    # std_dev = 15% of average gives realistic variation
    response_time = max(10, random.gauss(config["avg_latency"], config["avg_latency"] * 0.15))

    # Request count: varies around average with some noise
    request_count = max(1, int(random.gauss(config["avg_requests"], config["avg_requests"] * 0.2)))

    # Errors: each request has a small chance of failing
    error_count = sum(1 for _ in range(request_count) if random.random() < config["error_rate"])

    # Pick status code: most are 200, some errors are 4xx or 5xx
    if error_count > 0:
        # Mix of client errors (404, 400) and server errors (500, 503)
        status_code = random.choice([400, 404, 500, 503])
    else:
        status_code = 200

    return {
        "timestamp": timestamp,
        "response_time": round(response_time, 2),
        "status_code": status_code,
        "is_error": error_count > 0,
        "request_count": request_count,
        "error_count": error_count,
    }


def generate_anomalous_metric(config: dict, timestamp: datetime) -> dict:
    """
    Generate an ANOMALOUS metric data point.

    Randomly picks one of three anomaly types:
    1. Latency Spike: response time jumps to 3-10x normal
    2. Traffic Surge: request volume jumps to 3-8x normal
    3. Error Burst: error rate jumps dramatically

    In real systems, these are the patterns that indicate something is wrong.
    """
    anomaly_type = random.choice(["latency_spike", "traffic_surge", "error_burst"])

    if anomaly_type == "latency_spike":
        # Response time jumps to 3-10x the normal average
        spike_multiplier = random.uniform(3, 10)
        response_time = round(config["avg_latency"] * spike_multiplier, 2)
        request_count = max(1, int(random.gauss(config["avg_requests"], config["avg_requests"] * 0.2)))
        error_count = sum(1 for _ in range(request_count) if random.random() < config["error_rate"])
        status_code = 200  # Slow but still responding

    elif anomaly_type == "traffic_surge":
        # Request volume spikes to 3-8x normal
        surge_multiplier = random.uniform(3, 8)
        request_count = max(1, int(config["avg_requests"] * surge_multiplier))
        response_time = round(random.gauss(config["avg_latency"] * 1.5, config["avg_latency"] * 0.3), 2)
        response_time = max(10, response_time)
        # More traffic → slightly more errors
        error_count = sum(1 for _ in range(request_count) if random.random() < config["error_rate"] * 2)
        status_code = 200

    else:  # error_burst
        # Error rate jumps to 30-80%
        burst_error_rate = random.uniform(0.3, 0.8)
        request_count = max(1, int(random.gauss(config["avg_requests"], config["avg_requests"] * 0.2)))
        error_count = sum(1 for _ in range(request_count) if random.random() < burst_error_rate)
        response_time = round(random.gauss(config["avg_latency"] * 2, config["avg_latency"] * 0.5), 2)
        response_time = max(10, response_time)
        status_code = random.choice([500, 502, 503])

    return {
        "timestamp": timestamp,
        "response_time": response_time,
        "status_code": status_code,
        "is_error": error_count > 0,
        "request_count": request_count,
        "error_count": error_count,
    }


# ── Main Script ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("PULSE — Demo Data Generator")
    print("=" * 60)
    print()
    print("⚠️  This generates SIMULATED data for testing purposes.")
    print("    It is NOT real production API data.")
    print()

    db = SessionLocal()

    try:
        # ── Step 1: Create demo endpoints ──────────────────────────────
        print("Step 1: Creating demo endpoints...")
        endpoint_ids = {}  # Maps endpoint name → database id

        for ep_config in DEMO_ENDPOINTS:
            # Check if this endpoint already exists (avoid duplicates)
            existing = db.query(Endpoint).filter(Endpoint.name == ep_config["name"]).first()
            if existing:
                print(f"  ✓ '{ep_config['name']}' already exists (id={existing.id})")
                endpoint_ids[ep_config["name"]] = existing.id
            else:
                new_ep = Endpoint(
                    name=ep_config["name"],
                    url=ep_config["url"],
                    created_at=datetime.now(timezone.utc),
                )
                db.add(new_ep)
                db.commit()
                db.refresh(new_ep)
                print(f"  + Created '{ep_config['name']}' (id={new_ep.id})")
                endpoint_ids[ep_config["name"]] = new_ep.id

        print()

        # ── Step 2: Generate metrics ───────────────────────────────────
        print("Step 2: Generating metrics...")

        # Calculate time range
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=DAYS_OF_DATA)
        total_intervals = (DAYS_OF_DATA * 24 * 60) // INTERVAL_MINUTES  # ~2016 intervals for 7 days

        print(f"  Time range: {start_time.strftime('%Y-%m-%d %H:%M')} → {now.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"  Intervals: {total_intervals} per endpoint (every {INTERVAL_MINUTES} min)")
        print()

        total_metrics = 0
        total_anomalies = 0

        for ep_config in DEMO_ENDPOINTS:
            ep_id = endpoint_ids[ep_config["name"]]
            ep_anomalies = 0
            metrics_batch = []  # Collect metrics for bulk insert

            print(f"  Generating for '{ep_config['name']}'...", end=" ", flush=True)

            for i in range(total_intervals):
                timestamp = start_time + timedelta(minutes=i * INTERVAL_MINUTES)

                # Decide if this interval should be anomalous
                if random.random() < ANOMALY_PROBABILITY:
                    metric_data = generate_anomalous_metric(ep_config, timestamp)
                    ep_anomalies += 1
                else:
                    metric_data = generate_normal_metric(ep_config, timestamp)

                # Create the Metric object
                metric = Metric(
                    endpoint_id=ep_id,
                    **metric_data,  # Unpack all the generated fields
                )
                metrics_batch.append(metric)

            # Bulk insert all metrics for this endpoint at once (much faster)
            db.add_all(metrics_batch)
            db.commit()

            total_metrics += len(metrics_batch)
            total_anomalies += ep_anomalies
            print(f"✓ {len(metrics_batch)} metrics ({ep_anomalies} anomalous)")

        # ── Summary ────────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("✅ Demo data generation complete!")
        print(f"   Total metrics created: {total_metrics}")
        print(f"   Total anomalous intervals: {total_anomalies}")
        print(f"   Endpoints: {len(DEMO_ENDPOINTS)}")
        print()
        print("You can now:")
        print("  1. Start the API:  uvicorn main:app --reload")
        print("  2. View metrics:   GET http://localhost:8000/metrics")
        print("  3. View by endpoint: GET http://localhost:8000/metrics/{endpoint_id}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
