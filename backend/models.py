"""
SQLAlchemy models for PULSE.

Models define the structure of database tables.
Each class = one table in PostgreSQL.
"""

from sqlalchemy.orm import DeclarativeBase, relationship  # foundation for the classes
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean, Text


class Base(DeclarativeBase):  # inherits class for foundation
    pass  # no additional code needed right now


class Endpoint(Base):
    """
    Represents an API endpoint being monitored.
    Example: "User Service" at "https://api.example.com/users"
    """
    __tablename__ = "endpoints"  # double underscore are called dunders

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # relationship() creates a Python-level link between Endpoint and its Metrics.
    # It does NOT create a database column — it lets you do: endpoint.metrics
    # to get all Metric rows belonging to this endpoint.
    # cascade="all, delete-orphan" means: if you delete an Endpoint,
    # automatically delete all its Metrics too (no orphan data).
    metrics = relationship("Metric", back_populates="endpoint", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="endpoint", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="endpoint", cascade="all, delete-orphan")


class Metric(Base):
    """
    Stores a single API performance measurement.

    Each row represents one observation of an endpoint's behavior at a point in time.
    This is the raw data that anomaly detection will analyze later.

    Fields:
    - endpoint_id: which endpoint this metric belongs to (foreign key)
    - timestamp: when this measurement was recorded
    - response_time: how long the API took to respond (in milliseconds)
    - status_code: HTTP status code returned (200, 404, 500, etc.)
    - is_error: whether this was an error response (status >= 400)
    - request_count: number of requests in this time window
    - error_count: number of error responses in this time window
    """
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True)

    # Foreign key: links each metric to an endpoint.
    # "endpoints.id" refers to the 'id' column in the 'endpoints' table.
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)

    timestamp = Column(DateTime, nullable=False)
    response_time = Column(Float, nullable=False)       # Latency in milliseconds
    status_code = Column(Integer, nullable=False)        # HTTP status code (200, 500, etc.)
    is_error = Column(Boolean, nullable=False)           # True if status_code >= 400
    request_count = Column(Integer, nullable=False)      # Requests in this time window
    error_count = Column(Integer, nullable=False, default=0)  # Errors in this time window

    # back_populates creates the reverse link: metric.endpoint gives the Endpoint object.
    endpoint = relationship("Endpoint", back_populates="metrics")


class Anomaly(Base):
    """
    Stores a detected anomaly — a metric observation that deviates
    significantly from the expected/baseline behavior.

    Fields:
    - endpoint_id: which endpoint the anomaly was found on
    - metric_id: the specific metric observation that was anomalous
    - metric_type: what was anomalous ("response_time", "error_rate", "request_count")
    - observed_value: the actual value that was measured
    - expected_value: what the baseline/average value is
    - anomaly_score: how far off the value is (Z-score for statistical detection)
    - severity: LOW / MEDIUM / HIGH / CRITICAL
    - detection_method: which algorithm found it ("z_score", "isolation_forest", etc.)
    - description: human-readable explanation of the anomaly
    - timestamp: when the anomalous observation occurred
    - detected_at: when PULSE detected it
    """
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)
    metric_id = Column(Integer, ForeignKey("metrics.id"), nullable=True)

    metric_type = Column(String, nullable=False)        # "response_time", "error_rate", "request_count"
    observed_value = Column(Float, nullable=False)       # What was actually measured
    expected_value = Column(Float, nullable=False)       # What the baseline/average is
    anomaly_score = Column(Float, nullable=False)        # Z-score or anomaly score
    severity = Column(String, nullable=False)            # LOW, MEDIUM, HIGH, CRITICAL
    detection_method = Column(String, nullable=False)    # "z_score", "isolation_forest", "hybrid"
    description = Column(String, nullable=True)          # Human-readable explanation

    timestamp = Column(DateTime, nullable=False)         # When the anomalous metric was recorded
    detected_at = Column(DateTime, nullable=False)       # When PULSE found it

    endpoint = relationship("Endpoint", back_populates="anomalies")


class Incident(Base):
    """
    Represents a trackable incident created from one or more anomalies.

    An incident has a lifecycle:
      OPEN → INVESTIGATING → RESOLVED

    Fields:
    - title: short summary (e.g., "High latency on User Service")
    - description: detailed explanation of what happened
    - severity: inherited from the worst anomaly, or set manually
    - status: OPEN, INVESTIGATING, or RESOLVED
    - endpoint_id: which endpoint this incident is about
    - created_at: when the incident was opened
    - updated_at: when the incident was last modified
    - resolved_at: when the incident was marked RESOLVED (null if still open)
    """
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=False)           # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String, nullable=False, default="OPEN")  # OPEN, INVESTIGATING, RESOLVED
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)       # Null until resolved

    endpoint = relationship("Endpoint", back_populates="incidents")
