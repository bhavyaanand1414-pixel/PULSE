"""
PULSE — Local Test API Server

A simple test server you can run alongside PULSE to test live monitoring.
It exposes several endpoints with controllable behavior:

    /           → Always returns 200 OK (fast, ~1ms)
    /slow       → Returns 200 OK after a random delay (100-500ms)
    /error      → Returns 500 Internal Server Error
    /flaky      → Randomly returns 200 or 500 (50/50 chance)
    /timeout    → Sleeps for 15 seconds (causes PULSE to record a timeout)
    /status/NNN → Returns the specified HTTP status code

Usage:
    cd backend
    source venv/bin/activate
    uvicorn test_server:app --port 9999

Then register these in PULSE:
    Name: "Local Test - Healthy"    URL: http://localhost:9999/
    Name: "Local Test - Slow"       URL: http://localhost:9999/slow
    Name: "Local Test - Error"      URL: http://localhost:9999/error
    Name: "Local Test - Flaky"      URL: http://localhost:9999/flaky
"""

import random
import asyncio
from fastapi import FastAPI, Response

app = FastAPI(title="PULSE Test API")


@app.get("/")
async def healthy():
    """Always returns 200 OK immediately."""
    return {"status": "ok", "endpoint": "healthy", "service": "pulse-test-api"}


@app.get("/slow")
async def slow():
    """Returns 200 OK after a random delay (100-500ms)."""
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)
    return {"status": "ok", "endpoint": "slow", "delay_ms": round(delay * 1000)}


@app.get("/error")
async def error(response: Response):
    """Always returns 500 Internal Server Error."""
    response.status_code = 500
    return {"status": "error", "endpoint": "error", "message": "Simulated server error"}


@app.get("/flaky")
async def flaky(response: Response):
    """50% chance of 200 OK, 50% chance of 500 error."""
    if random.random() < 0.5:
        return {"status": "ok", "endpoint": "flaky", "message": "Got lucky!"}
    else:
        response.status_code = 500
        return {"status": "error", "endpoint": "flaky", "message": "Unlucky this time"}


@app.get("/timeout")
async def timeout():
    """Sleeps for 15 seconds — should trigger PULSE's 10-second timeout."""
    await asyncio.sleep(15)
    return {"status": "ok", "endpoint": "timeout", "message": "You waited long enough!"}


@app.get("/status/{code}")
async def custom_status(code: int, response: Response):
    """Returns the specified HTTP status code."""
    response.status_code = code
    return {"status_code": code, "endpoint": "custom_status"}
