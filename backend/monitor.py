"""
PULSE — Live API Monitor

This module adds REAL active monitoring to PULSE.
It periodically sends HTTP GET requests to registered endpoints
and records actual response latency, status codes, and success/failure.

Key design decisions:
─────────────────────
1. SECURITY: URLs are validated to prevent SSRF attacks. Only http/https
   schemes are allowed. Private/internal IP ranges (10.x, 172.16-31.x,
   192.168.x, 169.254.x) are blocked UNLESS the URL is explicitly
   localhost (127.0.0.1 or localhost), which the user controls.

2. ACCURACY: Response time is measured using time.monotonic() which is
   immune to system clock adjustments (NTP, DST, etc.).

3. HONESTY: Each probe measures ONE request from PULSE → target.
   request_count is always 1, error_count is 0 or 1.
   This is NOT the target service's total traffic volume.

4. RESILIENCE: Timeouts, DNS failures, connection refused, TLS errors,
   and unexpected exceptions are all caught and recorded as error metrics.

5. RELOAD-SAFE: The scheduler uses a module-level singleton so that
   FastAPI's --reload mode does not spawn duplicate jobs.
"""

import time
import socket
import ipaddress
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Endpoint, Metric
from detection import run_zscore_detection
from ml_detection import run_isolation_forest_detection

logger = logging.getLogger("pulse.monitor")

# ── Configuration ──────────────────────────────────────────────────────────

DEFAULT_INTERVAL_SECONDS = 30
MIN_INTERVAL_SECONDS = 10
MAX_INTERVAL_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 3

# How many probes must accumulate before auto-running anomaly detection
AUTO_DETECT_THRESHOLD = 30

# ── Module-level scheduler singleton ───────────────────────────────────────
# This prevents duplicate schedulers when uvicorn --reload restarts the app.

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """
    Return the singleton BackgroundScheduler, creating it if necessary.

    We use a module-level variable instead of attaching to the FastAPI app
    because uvicorn --reload reimports modules but may create new app instances,
    and we need to ensure only ONE scheduler exists per process.
    """
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        logger.info("Background scheduler started")
    return _scheduler


def shutdown_scheduler():
    """Gracefully shut down the scheduler on app shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
        _scheduler = None


# ── URL Validation & SSRF Protection ──────────────────────────────────────

# Private IPv4 ranges that are blocked (SSRF protection)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("0.0.0.0/8"),         # "This" network
]

# Hosts that are always allowed (user's own machine)
_ALLOWED_LOCALHOST = {"localhost", "127.0.0.1", "::1"}


def validate_monitor_url(url: str) -> str:
    """
    Validate a URL for live monitoring. Returns the cleaned URL or raises
    ValueError with a descriptive message.

    Security checks:
    1. Must be http or https scheme.
    2. Must have a hostname.
    3. If the hostname resolves to a private IP, it's blocked UNLESS
       the hostname is explicitly localhost/127.0.0.1 (user controls that).
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname.")

    # Allow explicit localhost
    if hostname in _ALLOWED_LOCALHOST:
        return url

    # Resolve hostname and check for private IPs
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname '{hostname}'.")

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        for network in _PRIVATE_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"URL resolves to private IP {ip}. "
                    f"Monitoring private/internal addresses is not allowed. "
                    f"Use localhost for local services you control."
                )

    return url


# ── The Probe Function ────────────────────────────────────────────────────

def probe_endpoint(endpoint_id: int) -> dict:
    """
    Send a single GET request to the endpoint's URL and record the result.

    Measures:
    - response_time: wall-clock latency in milliseconds (monotonic clock)
    - status_code: actual HTTP status or 0 for connection failures
    - is_error: True if status >= 400 or connection failed

    Returns a dict with the recorded metric data.
    """
    db = SessionLocal()
    try:
        endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
        if not endpoint:
            logger.warning(f"Endpoint {endpoint_id} not found, removing job")
            _remove_job(endpoint_id)
            return {"error": "endpoint_not_found"}

        url = endpoint.url
        now = datetime.now(timezone.utc)

        # ── Perform the actual HTTP request ───────────────────────────
        try:
            start = time.monotonic()
            with httpx.Client(
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
            ) as client:
                response = client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000

            status_code = response.status_code
            is_error = status_code >= 400
            error_count = 1 if is_error else 0

        except httpx.TimeoutException:
            elapsed_ms = REQUEST_TIMEOUT_SECONDS * 1000
            status_code = 0
            is_error = True
            error_count = 1
            logger.warning(f"Timeout probing {endpoint.name} ({url})")

        except httpx.TooManyRedirects:
            elapsed_ms = 0
            status_code = 0
            is_error = True
            error_count = 1
            logger.warning(f"Too many redirects probing {endpoint.name} ({url})")

        except httpx.ConnectError:
            elapsed_ms = 0
            status_code = 0
            is_error = True
            error_count = 1
            logger.warning(f"Connection refused probing {endpoint.name} ({url})")

        except Exception as e:
            elapsed_ms = 0
            status_code = 0
            is_error = True
            error_count = 1
            logger.error(f"Unexpected error probing {endpoint.name}: {e}")

        # ── Save the metric ───────────────────────────────────────────
        # request_count=1 and error_count=0/1 because this is ONE probe.
        # We do NOT pretend this represents the target's total traffic.
        metric = Metric(
            endpoint_id=endpoint_id,
            timestamp=now,
            response_time=round(elapsed_ms, 2),
            status_code=status_code,
            is_error=is_error,
            request_count=1,
            error_count=error_count,
            source="live",  # Distinguish from demo/simulated data
        )
        db.add(metric)

        # Update endpoint's last-check fields for the dashboard
        endpoint.last_check_at = now
        endpoint.last_status_code = status_code
        endpoint.last_response_time = round(elapsed_ms, 2)

        db.commit()
        db.refresh(metric)

        logger.info(
            f"Probe {endpoint.name}: {status_code} in {elapsed_ms:.0f}ms"
        )

        # ── Auto-detect anomalies once we have enough data ────────────
        _maybe_auto_detect(db, endpoint_id)

        return {
            "endpoint_id": endpoint_id,
            "response_time": round(elapsed_ms, 2),
            "status_code": status_code,
            "is_error": is_error,
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in probe_endpoint({endpoint_id}): {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def _maybe_auto_detect(db, endpoint_id: int):
    """
    Run anomaly detection automatically once we accumulate enough probes.
    Only runs every AUTO_DETECT_THRESHOLD new metrics to avoid overhead.
    """
    metric_count = (
        db.query(Metric)
        .filter(Metric.endpoint_id == endpoint_id)
        .count()
    )
    if metric_count >= AUTO_DETECT_THRESHOLD and metric_count % AUTO_DETECT_THRESHOLD == 0:
        try:
            run_zscore_detection(db, endpoint_id)
            run_isolation_forest_detection(db, endpoint_id)
            logger.info(f"Auto-detection completed for endpoint {endpoint_id}")
        except Exception as e:
            logger.warning(f"Auto-detection failed for endpoint {endpoint_id}: {e}")


# ── Job Management ────────────────────────────────────────────────────────

def _job_id(endpoint_id: int) -> str:
    """Consistent job ID format for APScheduler."""
    return f"pulse_monitor_{endpoint_id}"


def start_monitoring(endpoint_id: int, interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> dict:
    """
    Start periodic monitoring for an endpoint.

    Validates the endpoint exists and its URL is safe, then schedules
    an APScheduler interval job. If a job already exists, it is replaced.
    """
    interval_seconds = max(MIN_INTERVAL_SECONDS, min(interval_seconds, MAX_INTERVAL_SECONDS))

    db = SessionLocal()
    try:
        endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        # Validate URL safety
        validate_monitor_url(endpoint.url)

        scheduler = get_scheduler()
        job_id = _job_id(endpoint_id)

        # Remove existing job if present (idempotent restart)
        existing = scheduler.get_job(job_id)
        if existing:
            scheduler.remove_job(job_id)

        scheduler.add_job(
            probe_endpoint,
            trigger="interval",
            seconds=interval_seconds,
            id=job_id,
            args=[endpoint_id],
            replace_existing=True,
            max_instances=1,  # Prevent overlapping probes
        )

        logger.info(
            f"Started monitoring '{endpoint.name}' every {interval_seconds}s"
        )

        return {
            "endpoint_id": endpoint_id,
            "endpoint_name": endpoint.name,
            "interval_seconds": interval_seconds,
            "status": "monitoring",
        }

    finally:
        db.close()


def stop_monitoring(endpoint_id: int) -> dict:
    """Stop periodic monitoring for an endpoint."""
    scheduler = get_scheduler()
    job_id = _job_id(endpoint_id)

    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)
        logger.info(f"Stopped monitoring endpoint {endpoint_id}")
        return {"endpoint_id": endpoint_id, "status": "stopped"}
    else:
        return {"endpoint_id": endpoint_id, "status": "not_monitoring"}


def _remove_job(endpoint_id: int):
    """Internal helper to remove a job (used when an endpoint is deleted)."""
    try:
        scheduler = get_scheduler()
        job_id = _job_id(endpoint_id)
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception:
        pass


def get_monitoring_status() -> list[dict]:
    """
    Return the status of all active monitoring jobs.

    Used by the frontend to show which endpoints are being actively probed.
    """
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith("pulse_monitor_"):
            endpoint_id = int(job.id.replace("pulse_monitor_", ""))
            jobs.append({
                "endpoint_id": endpoint_id,
                "job_id": job.id,
                "interval_seconds": int(job.trigger.interval.total_seconds()),
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
    return jobs


def get_endpoint_monitor_status(endpoint_id: int) -> dict:
    """Get monitoring status for a single endpoint."""
    scheduler = get_scheduler()
    job_id = _job_id(endpoint_id)
    job = scheduler.get_job(job_id)

    if job:
        return {
            "endpoint_id": endpoint_id,
            "is_monitoring": True,
            "interval_seconds": int(job.trigger.interval.total_seconds()),
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }
    else:
        return {
            "endpoint_id": endpoint_id,
            "is_monitoring": False,
            "interval_seconds": None,
            "next_run": None,
        }
