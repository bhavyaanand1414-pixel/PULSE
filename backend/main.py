from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from database import get_db
from models import Endpoint, Metric
from schemas import (
    EndpointCreate, EndpointResponse,
    MetricCreate, MetricResponse,
)

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


# --- Metrics APIs ---

@app.post("/metrics", response_model=MetricResponse, status_code=201)
def create_metric(metric_data: MetricCreate, db: Session = Depends(get_db)):
    """
    Record a new API performance metric.

    How it works:
    1. Validate the request body using MetricCreate schema.
    2. Check that the referenced endpoint actually exists (integrity check).
    3. Create the Metric row with the current UTC timestamp.
    4. Save it to PostgreSQL and return the saved object.
    """
    # First, verify the endpoint exists
    endpoint = db.query(Endpoint).filter(Endpoint.id == metric_data.endpoint_id).first()
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint with id {metric_data.endpoint_id} not found"
        )

    new_metric = Metric(
        endpoint_id=metric_data.endpoint_id,
        timestamp=datetime.now(timezone.utc),
        response_time=metric_data.response_time,
        status_code=metric_data.status_code,
        is_error=metric_data.is_error,
        request_count=metric_data.request_count,
        error_count=metric_data.error_count,
    )
    db.add(new_metric)
    db.commit()
    db.refresh(new_metric)
    return new_metric


@app.get("/metrics", response_model=list[MetricResponse])
def list_metrics(
    start_time: Optional[datetime] = Query(None, description="Filter metrics after this time (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="Filter metrics before this time (ISO format)"),
    db: Session = Depends(get_db),
):
    """
    List all metrics, optionally filtered by time range.

    Query parameters (both optional):
    - start_time: Only return metrics recorded after this timestamp.
    - end_time: Only return metrics recorded before this timestamp.

    Example: GET /metrics?start_time=2026-09-01T00:00:00&end_time=2026-09-30T23:59:59

    How filtering works:
    We start with a base query and progressively add .filter() conditions.
    Each .filter() appends a WHERE clause to the SQL query.
    """
    query = db.query(Metric)

    if start_time:
        query = query.filter(Metric.timestamp >= start_time)
    if end_time:
        query = query.filter(Metric.timestamp <= end_time)

    # Order by newest first so the most recent data appears at the top
    query = query.order_by(Metric.timestamp.desc())

    return query.all()


@app.get("/metrics/{endpoint_id}", response_model=list[MetricResponse])
def get_metrics_by_endpoint(
    endpoint_id: int,
    start_time: Optional[datetime] = Query(None, description="Filter metrics after this time"),
    end_time: Optional[datetime] = Query(None, description="Filter metrics before this time"),
    db: Session = Depends(get_db),
):
    """
    Get all metrics for a specific endpoint, optionally filtered by time range.

    This is useful for examining one API's behavior over time.
    Example: GET /metrics/1?start_time=2026-09-20T00:00:00
    """
    # Verify the endpoint exists
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    query = db.query(Metric).filter(Metric.endpoint_id == endpoint_id)

    if start_time:
        query = query.filter(Metric.timestamp >= start_time)
    if end_time:
        query = query.filter(Metric.timestamp <= end_time)

    query = query.order_by(Metric.timestamp.desc())

    return query.all()