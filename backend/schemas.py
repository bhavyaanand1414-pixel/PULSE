"""
Pydantic schemas for PULSE API.

Schemas define the shape of data that flows in and out of the API.
- "Create" schemas define what the client sends when creating a resource.
- "Response" schemas define what the API returns to the client.

This is separate from models.py, which defines the database table structure.
"""

from pydantic import BaseModel
from datetime import datetime


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
