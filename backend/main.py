from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone
from typing import Optional

from database import get_db
from models import Endpoint, Metric, Anomaly, Incident
from schemas import (
    EndpointCreate, EndpointResponse,
    MetricCreate, MetricResponse,
    AnomalyResponse,
    IncidentCreate, IncidentUpdate, IncidentResponse,
)
from detection import run_zscore_detection
from ml_detection import run_isolation_forest_detection

app = FastAPI(title="PULSE API")

# CORS: Allow the React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# --- Anomaly Detection APIs ---

@app.post("/anomalies/detect/{endpoint_id}")
def detect_anomalies(endpoint_id: int, db: Session = Depends(get_db)):
    """
    Trigger Z-score anomaly detection for a specific endpoint.

    How it works:
    1. Fetches all historical metrics for this endpoint.
    2. Calculates the baseline (mean + standard deviation) for each metric type.
    3. Computes the Z-score for every observation.
    4. If |Z-score| >= 2.0, flags it as an anomaly with the appropriate severity.
    5. Saves new anomalies to the database (skips already-detected ones).

    Returns a summary of how many anomalies were found per severity level.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        new_anomalies = run_zscore_detection(db, endpoint_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build a summary grouped by severity
    severity_counts = {}
    for a in new_anomalies:
        severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

    return {
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint.name,
        "detection_method": "z_score",
        "new_anomalies_detected": len(new_anomalies),
        "by_severity": severity_counts,
    }


@app.get("/anomalies", response_model=list[AnomalyResponse])
def list_anomalies(
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    detection_method: Optional[str] = Query(None, description="Filter by method: z_score, isolation_forest"),
    start_time: Optional[datetime] = Query(None, description="Filter anomalies after this time"),
    end_time: Optional[datetime] = Query(None, description="Filter anomalies before this time"),
    db: Session = Depends(get_db),
):
    """
    List all detected anomalies, with optional filters.

    Supports filtering by severity, detection method, and time range.
    Returns newest anomalies first.
    """
    query = db.query(Anomaly)

    if severity:
        query = query.filter(Anomaly.severity == severity.upper())
    if detection_method:
        query = query.filter(Anomaly.detection_method == detection_method)
    if start_time:
        query = query.filter(Anomaly.timestamp >= start_time)
    if end_time:
        query = query.filter(Anomaly.timestamp <= end_time)

    query = query.order_by(Anomaly.timestamp.desc())

    return query.all()


@app.get("/anomalies/{endpoint_id}", response_model=list[AnomalyResponse])
def get_anomalies_by_endpoint(
    endpoint_id: int,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    start_time: Optional[datetime] = Query(None, description="Filter after this time"),
    end_time: Optional[datetime] = Query(None, description="Filter before this time"),
    db: Session = Depends(get_db),
):
    """
    Get all anomalies for a specific endpoint.

    Useful for investigating one service's anomaly history.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    query = db.query(Anomaly).filter(Anomaly.endpoint_id == endpoint_id)

    if severity:
        query = query.filter(Anomaly.severity == severity.upper())
    if start_time:
        query = query.filter(Anomaly.timestamp >= start_time)
    if end_time:
        query = query.filter(Anomaly.timestamp <= end_time)

    query = query.order_by(Anomaly.timestamp.desc())

    return query.all()


@app.post("/anomalies/detect/ml/{endpoint_id}")
def detect_anomalies_ml(endpoint_id: int, db: Session = Depends(get_db)):
    """
    Trigger Isolation Forest (ML) anomaly detection for an endpoint.

    Unlike Z-score which checks one metric at a time, Isolation Forest
    analyzes response_time, error_rate, and request_count TOGETHER
    to find multi-dimensional anomalies.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        new_anomalies = run_isolation_forest_detection(db, endpoint_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    severity_counts = {}
    for a in new_anomalies:
        severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

    return {
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint.name,
        "detection_method": "isolation_forest",
        "new_anomalies_detected": len(new_anomalies),
        "by_severity": severity_counts,
    }


@app.post("/anomalies/detect/hybrid/{endpoint_id}")
def detect_anomalies_hybrid(endpoint_id: int, db: Session = Depends(get_db)):
    """
    Run BOTH Z-score AND Isolation Forest detection for an endpoint.

    This hybrid approach gives the most comprehensive anomaly coverage:
    - Z-score catches single-metric outliers (e.g., one huge latency spike)
    - Isolation Forest catches multi-dimensional patterns (e.g., moderate
      latency + moderate errors + traffic spike = combined anomaly)

    Results from both methods are stored separately with their detection_method
    field, so you can filter and compare them later.
    """
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    try:
        zscore_anomalies = run_zscore_detection(db, endpoint_id)
        ml_anomalies = run_isolation_forest_detection(db, endpoint_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build severity counts for each method
    zscore_counts = {}
    for a in zscore_anomalies:
        zscore_counts[a.severity] = zscore_counts.get(a.severity, 0) + 1

    ml_counts = {}
    for a in ml_anomalies:
        ml_counts[a.severity] = ml_counts.get(a.severity, 0) + 1

    return {
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint.name,
        "detection_method": "hybrid",
        "z_score": {
            "new_anomalies": len(zscore_anomalies),
            "by_severity": zscore_counts,
        },
        "isolation_forest": {
            "new_anomalies": len(ml_anomalies),
            "by_severity": ml_counts,
        },
        "total_new_anomalies": len(zscore_anomalies) + len(ml_anomalies),
    }


# --- Incident Management APIs ---

@app.post("/incidents", response_model=IncidentResponse, status_code=201)
def create_incident(incident_data: IncidentCreate, db: Session = Depends(get_db)):
    """
    Create a new incident to track an issue.

    An incident starts in OPEN status. You can later update it to
    INVESTIGATING or RESOLVED.
    """
    # Verify the endpoint exists
    endpoint = db.query(Endpoint).filter(Endpoint.id == incident_data.endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    now = datetime.now(timezone.utc)
    new_incident = Incident(
        title=incident_data.title,
        description=incident_data.description,
        severity=incident_data.severity.upper(),
        status="OPEN",
        endpoint_id=incident_data.endpoint_id,
        created_at=now,
        updated_at=now,
        resolved_at=None,
    )
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)
    return new_incident


@app.get("/incidents", response_model=list[IncidentResponse])
def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status: OPEN, INVESTIGATING, RESOLVED"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    db: Session = Depends(get_db),
):
    """
    List all incidents, optionally filtered by status and/or severity.
    Returns newest first.
    """
    query = db.query(Incident)

    if status:
        query = query.filter(Incident.status == status.upper())
    if severity:
        query = query.filter(Incident.severity == severity.upper())

    query = query.order_by(Incident.created_at.desc())
    return query.all()


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get a single incident by ID."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.put("/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident(
    incident_id: int,
    update_data: IncidentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing incident (partial update).

    Only fields that are provided in the request body will be changed.
    This uses the "partial update" pattern — send only what you want to change.

    Example: PUT /incidents/1 with {"status": "INVESTIGATING"}
    will only change the status, leaving title/description/severity unchanged.

    If status is changed to RESOLVED, resolved_at is automatically set.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # model_dump(exclude_unset=True) returns only the fields the client sent
    update_fields = update_data.model_dump(exclude_unset=True)

    for field, value in update_fields.items():
        if field == "status" and value:
            value = value.upper()
        if field == "severity" and value:
            value = value.upper()
        setattr(incident, field, value)

    # Auto-set resolved_at when status changes to RESOLVED
    if incident.status == "RESOLVED" and incident.resolved_at is None:
        incident.resolved_at = datetime.now(timezone.utc)

    # If re-opened, clear resolved_at
    if incident.status != "RESOLVED":
        incident.resolved_at = None

    incident.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)
    return incident


@app.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    """
    Quick-resolve an incident. Sets status to RESOLVED and timestamps it.

    This is a convenience endpoint — you could also use PUT with
    {"status": "RESOLVED"}, but this is cleaner for the frontend.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.now(timezone.utc)
    incident.status = "RESOLVED"
    incident.resolved_at = now
    incident.updated_at = now
    db.commit()
    db.refresh(incident)
    return incident


# --- System Health ---

@app.get("/system/health")
def system_health(db: Session = Depends(get_db)):
    """
    Comprehensive system health check.

    Unlike the simple /health endpoint, this actually verifies:
    1. The database connection is alive (runs a real SQL query)
    2. Reports counts of monitored endpoints, metrics, anomalies, incidents

    If the database is down, this endpoint will report it honestly
    rather than falsely claiming everything is healthy.
    """
    # Test database connection with a simple query
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Gather real statistics
    try:
        endpoint_count = db.query(func.count(Endpoint.id)).scalar()
        metric_count = db.query(func.count(Metric.id)).scalar()
        anomaly_count = db.query(func.count(Anomaly.id)).scalar()
        open_incidents = db.query(func.count(Incident.id)).filter(
            Incident.status != "RESOLVED"
        ).scalar()
    except Exception:
        endpoint_count = metric_count = anomaly_count = open_incidents = "unavailable"

    overall = "healthy" if db_status == "connected" else "unhealthy"

    return {
        "status": overall,
        "service": "PULSE API",
        "database": db_status,
        "stats": {
            "monitored_endpoints": endpoint_count,
            "total_metrics": metric_count,
            "total_anomalies": anomaly_count,
            "open_incidents": open_incidents,
        },
    }