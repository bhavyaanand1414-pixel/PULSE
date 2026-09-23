"""
Pydantic schemas for PULSE API.

Schemas define the shape of data that flows in and out of the API.
- "Create" schemas define what the client sends when creating a resource.
- "Response" schemas define what the API returns to the client.

This is separate from models.py, which defines the database table structure.
"""

from pydantic import BaseModel, model_validator
from datetime import datetime
from typing import Optional


# --- Endpoint Schemas ---

class EndpointCreate(BaseModel):
    """
    Schema for creating a new monitored endpoint.
    The client sends 'name' and 'url'. 
    The server will auto-generate 'id' and 'created_at'.
    """
    name: str
    url: str


class EndpointResponse(BaseModel):
    """
    Schema for returning endpoint data to the client.
    Includes all fields: id, name, url, created_at.
    
    model_config with from_attributes=True tells Pydantic to read data
    from SQLAlchemy model objects (which use attribute access like obj.name)
    instead of only accepting dictionaries.
    """
    id: int
    name: str
    url: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Metric Schemas ---

class MetricCreate(BaseModel):
    """
    Schema for recording a new API metric.
    
    The client sends the raw measurement data.
    'is_error' is optional — if not provided, it will be computed
    automatically from status_code (True if status_code >= 400).
    """
    endpoint_id: int
    response_time: float           # Latency in milliseconds
    status_code: int               # HTTP status code (200, 500, etc.)
    is_error: Optional[bool] = None  # Auto-computed if not provided
    request_count: int = 1         # Defaults to 1 (single request)
    error_count: int = 0           # Defaults to 0

    @model_validator(mode="after")
    def compute_is_error(self):
        """
        model_validator runs AFTER all fields are set.
        If the client didn't send 'is_error', compute it from status_code.
        Any HTTP status >= 400 is an error (4xx = client error, 5xx = server error).
        """
        if self.is_error is None:
            self.is_error = self.status_code >= 400
        return self


class MetricResponse(BaseModel):
    """
    Schema for returning metric data to the client.
    Includes all fields including the auto-generated id and timestamp.
    """
    id: int
    endpoint_id: int
    timestamp: datetime
    response_time: float
    status_code: int
    is_error: bool
    request_count: int
    error_count: int

    model_config = {"from_attributes": True}
