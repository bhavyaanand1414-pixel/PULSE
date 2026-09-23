"""
SQLAlchemy models for PULSE.

Models define the structure of database tables.
Each class = one table in PostgreSQL.
"""

from sqlalchemy.orm import DeclarativeBase, relationship  # foundation for the classes
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean


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
