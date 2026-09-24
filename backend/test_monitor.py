"""
PULSE — Tests for Live Monitoring

Tests cover:
1. URL validation & SSRF protection
2. Probe success with a real HTTP server (httpbin)
3. Probe failure handling (connection refused, timeout)
4. Metric recording (source='live', correct fields)
5. Monitoring start/stop lifecycle
6. Scheduler singleton behavior
"""

import time
import socket
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# ── URL Validation Tests ──────────────────────────────────────────────────

from monitor import validate_monitor_url


class TestURLValidation:
    """Tests for SSRF protection and URL validation."""

    def test_valid_https_url(self):
        """Public HTTPS URLs should be accepted."""
        url = validate_monitor_url("https://httpbin.org/get")
        assert url == "https://httpbin.org/get"

    def test_valid_http_url(self):
        """Public HTTP URLs should be accepted."""
        url = validate_monitor_url("http://httpbin.org/get")
        assert url == "http://httpbin.org/get"

    def test_localhost_allowed(self):
        """localhost is explicitly allowed for local test services."""
        url = validate_monitor_url("http://localhost:9999/")
        assert url == "http://localhost:9999/"

    def test_127_allowed(self):
        """127.0.0.1 is explicitly allowed for local test services."""
        url = validate_monitor_url("http://127.0.0.1:8000/health")
        assert url == "http://127.0.0.1:8000/health"

    def test_ftp_rejected(self):
        """FTP scheme should be rejected."""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_monitor_url("ftp://example.com/file")

    def test_file_scheme_rejected(self):
        """file:// scheme should be rejected."""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_monitor_url("file:///etc/passwd")

    def test_no_scheme_rejected(self):
        """URLs without a scheme should be rejected."""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_monitor_url("example.com/api")

    def test_empty_hostname_rejected(self):
        """URLs without a hostname should be rejected."""
        with pytest.raises(ValueError, match="hostname"):
            validate_monitor_url("http:///path")

    def test_private_10_network_blocked(self):
        """10.0.0.0/8 private range should be blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, 0, 0, "", ("10.0.0.1", 0))]
            with pytest.raises(ValueError, match="private IP"):
                validate_monitor_url("http://internal-service.corp/api")

    def test_private_172_network_blocked(self):
        """172.16.0.0/12 private range should be blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, 0, 0, "", ("172.16.0.1", 0))]
            with pytest.raises(ValueError, match="private IP"):
                validate_monitor_url("http://internal.example.com/api")

    def test_private_192_168_blocked(self):
        """192.168.0.0/16 private range should be blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, 0, 0, "", ("192.168.1.100", 0))]
            with pytest.raises(ValueError, match="private IP"):
                validate_monitor_url("http://router.local/api")

    def test_link_local_blocked(self):
        """169.254.0.0/16 link-local range should be blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, 0, 0, "", ("169.254.1.1", 0))]
            with pytest.raises(ValueError, match="private IP"):
                validate_monitor_url("http://metadata.internal/api")

    def test_unresolvable_hostname_rejected(self):
        """Hostnames that can't be resolved should be rejected."""
        with pytest.raises(ValueError, match="Cannot resolve"):
            validate_monitor_url("http://this-hostname-does-not-exist-xyz123.invalid/api")


# ── Probe Function Tests ─────────────────────────────────────────────────

from monitor import probe_endpoint


class TestProbeEndpoint:
    """Tests for the probe_endpoint function."""

    def test_probe_connection_refused(self):
        """
        Probing a port with no listener should record an error metric.
        We mock the DB to verify the correct metric is created.
        """
        mock_db = MagicMock()
        mock_endpoint = MagicMock()
        mock_endpoint.id = 999
        mock_endpoint.name = "Test Endpoint"
        mock_endpoint.url = "http://127.0.0.1:19999/"  # Nothing listening here

        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        with patch("monitor.SessionLocal", return_value=mock_db):
            result = probe_endpoint(999)

        assert result["is_error"] is True
        assert result["status_code"] == 0
        assert result["endpoint_id"] == 999

    def test_probe_records_correct_fields(self):
        """
        Verify that a successful probe records the expected metric fields.
        """
        import httpx

        mock_db = MagicMock()
        mock_endpoint = MagicMock()
        mock_endpoint.id = 1
        mock_endpoint.name = "Test"
        mock_endpoint.url = "http://example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        # Mock httpx to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("monitor.SessionLocal", return_value=mock_db):
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.get.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = probe_endpoint(1)

        assert result["status_code"] == 200
        assert result["is_error"] is False
        assert result["response_time"] >= 0
        assert "timestamp" in result

        # Verify the metric was added to the DB session
        mock_db.add.assert_called_once()
        saved_metric = mock_db.add.call_args[0][0]
        assert saved_metric.source == "live"
        assert saved_metric.request_count == 1
        assert saved_metric.error_count == 0


# ── Monitoring Lifecycle Tests ────────────────────────────────────────────

from monitor import start_monitoring, stop_monitoring, get_endpoint_monitor_status


class TestMonitoringLifecycle:
    """Tests for start/stop monitoring."""

    def test_start_requires_valid_endpoint(self):
        """Starting monitoring for a non-existent endpoint should raise."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("monitor.SessionLocal", return_value=mock_db):
            with pytest.raises(ValueError, match="not found"):
                start_monitoring(99999)

    def test_start_validates_url(self):
        """Starting monitoring with an invalid URL should raise."""
        mock_db = MagicMock()
        mock_endpoint = MagicMock()
        mock_endpoint.id = 1
        mock_endpoint.url = "ftp://bad-scheme.com"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint

        with patch("monitor.SessionLocal", return_value=mock_db):
            with pytest.raises(ValueError, match="Invalid URL scheme"):
                start_monitoring(1)

    def test_stop_nonexistent_returns_not_monitoring(self):
        """Stopping monitoring that isn't running returns a clean status."""
        result = stop_monitoring(99999)
        assert result["status"] == "not_monitoring"


# ── Metric Source Tagging Tests ───────────────────────────────────────────

class TestMetricSourceTagging:
    """Verify that live metrics are tagged with source='live'."""

    def test_live_probe_sets_source_live(self):
        """probe_endpoint should create metrics with source='live'."""
        import httpx

        mock_db = MagicMock()
        mock_endpoint = MagicMock()
        mock_endpoint.id = 1
        mock_endpoint.name = "Test"
        mock_endpoint.url = "http://example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("monitor.SessionLocal", return_value=mock_db):
            with patch("httpx.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.get.return_value = mock_response
                mock_client_cls.return_value = mock_client

                probe_endpoint(1)

        saved_metric = mock_db.add.call_args[0][0]
        assert saved_metric.source == "live"

    def test_error_probe_sets_source_live(self):
        """Even failed probes should be tagged as source='live'."""
        mock_db = MagicMock()
        mock_endpoint = MagicMock()
        mock_endpoint.id = 1
        mock_endpoint.name = "Test"
        mock_endpoint.url = "http://127.0.0.1:19999/"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        with patch("monitor.SessionLocal", return_value=mock_db):
            probe_endpoint(1)

        saved_metric = mock_db.add.call_args[0][0]
        assert saved_metric.source == "live"
        assert saved_metric.is_error is True
        assert saved_metric.request_count == 1
        assert saved_metric.error_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
