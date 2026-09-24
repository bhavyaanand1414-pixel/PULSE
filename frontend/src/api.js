/**
 * PULSE API Client
 * 
 * Centralizes all backend API calls in one place.
 * Every function returns a Promise that resolves to JSON data.
 * The BASE_URL points to the FastAPI server.
 */

const BASE_URL = "http://localhost:8000";

// Generic fetch wrapper with error handling
async function apiFetch(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// --- Endpoints ---
export const getEndpoints = () => apiFetch("/endpoints");
export const getEndpoint = (id) => apiFetch(`/endpoints/${id}`);
export const createEndpoint = (data) =>
  apiFetch("/endpoints", { method: "POST", body: JSON.stringify(data) });
export const deleteEndpoint = (id) =>
  apiFetch(`/endpoints/${id}`, { method: "DELETE" });

// --- Metrics ---
export const getMetrics = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/metrics${query ? `?${query}` : ""}`);
};
export const getMetricsByEndpoint = (endpointId, params = {}) => {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/metrics/${endpointId}${query ? `?${query}` : ""}`);
};

// --- Anomalies ---
export const getAnomalies = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/anomalies${query ? `?${query}` : ""}`);
};
export const getAnomaliesByEndpoint = (endpointId, params = {}) => {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/anomalies/${endpointId}${query ? `?${query}` : ""}`);
};
export const detectAnomalies = (endpointId, method = "hybrid") =>
  apiFetch(`/anomalies/detect/${method}/${endpointId}`, { method: "POST" });

// --- Incidents ---
export const getIncidents = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/incidents${query ? `?${query}` : ""}`);
};
export const createIncident = (data) =>
  apiFetch("/incidents", { method: "POST", body: JSON.stringify(data) });
export const updateIncident = (id, data) =>
  apiFetch(`/incidents/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const resolveIncident = (id) =>
  apiFetch(`/incidents/${id}/resolve`, { method: "POST" });

// --- System Health ---
export const getSystemHealth = () => apiFetch("/system/health");

// --- Live Monitoring ---
export const startMonitoring = (endpointId, intervalSeconds = 30) =>
  apiFetch(`/monitoring/${endpointId}/start`, {
    method: "POST",
    body: JSON.stringify({ interval_seconds: intervalSeconds }),
  });
export const stopMonitoring = (endpointId) =>
  apiFetch(`/monitoring/${endpointId}/stop`, { method: "POST" });
export const probeEndpoint = (endpointId) =>
  apiFetch(`/monitoring/${endpointId}/probe`, { method: "POST" });
export const getMonitoringStatus = () => apiFetch("/monitoring/status");
export const getEndpointMonitoringStatus = (endpointId) =>
  apiFetch(`/monitoring/${endpointId}/status`);
