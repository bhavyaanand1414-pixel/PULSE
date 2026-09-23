"""
PULSE API — Main application entry point.

This file defines all the API routes (endpoints) for the PULSE platform.
FastAPI handles HTTP requests and uses dependency injection to get
database sessions via get_db().
"""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from models import Endpoint
from schemas import EndpointCreate, EndpointResponse

app = FastAPI(title="PULSE API")


# --- Root & Health Endpoints (existing) ---

@app.get("/")
def root():
    # root is the function that will be called whenever get is sent
    # Whenever someone sends GET /, execute the root() function.
    return {
        "message": "PULSE API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "PULSE API"
    }


# --- Endpoint CRUD APIs ---

@app.post("/endpoints", response_model=EndpointResponse, status_code=201)
def create_endpoint(endpoint_data: EndpointCreate, db: Session = Depends(get_db)):
    """
    Register a new API endpoint to monitor.
    
    How it works:
    1. FastAPI receives JSON body and validates it using EndpointCreate schema.
    2. Depends(get_db) injects a database session automatically.
    3. We create a new Endpoint row, add it to the session, and commit.
    4. db.refresh() reloads the object so we get the auto-generated id.
    5. response_model=EndpointResponse tells FastAPI to format the output.
    """
    new_endpoint = Endpoint(
        name=endpoint_data.name,
        url=endpoint_data.url,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_endpoint)
    db.commit()
    db.refresh(new_endpoint)  # Reload to get the auto-generated id
    return new_endpoint


@app.get("/endpoints", response_model=list[EndpointResponse])
def list_endpoints(db: Session = Depends(get_db)):
    """
    List all monitored API endpoints.
    
    db.query(Endpoint).all() translates to: SELECT * FROM endpoints;
    response_model=list[EndpointResponse] tells FastAPI to return a JSON array.
    """
    endpoints = db.query(Endpoint).all()
    return endpoints


@app.get("/endpoints/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    """
    Get a single monitored endpoint by its ID.
    
    If the endpoint doesn't exist, we raise HTTPException with 404 status.
    FastAPI automatically converts this into a proper error JSON response.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint


@app.delete("/endpoints/{endpoint_id}", status_code=200)
def delete_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    """
    Delete a monitored endpoint by its ID.
    
    We first check if it exists. If not, return 404.
    If it exists, delete it and commit the transaction.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    db.delete(endpoint)
    db.commit()
    return {"message": f"Endpoint '{endpoint.name}' deleted successfully"}