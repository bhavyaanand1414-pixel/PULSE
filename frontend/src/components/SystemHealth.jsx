import { useState, useEffect } from "react";
import { getSystemHealth } from "../api";

export default function SystemHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getSystemHealth()
      .then(setHealth)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Checking system health...</div>;
  if (error) return <div className="error-state">Error: {error}</div>;

  const isHealthy = health?.status === "healthy";
  const dbConnected = health?.database === "connected";

  return (
    <div>
      <div className="page-header">
        <h2>System Health</h2>
        <p>Live status of the PULSE monitoring platform</p>
      </div>

      <div className="card" style={{ marginBottom: 28, borderLeft: `4px solid ${isHealthy ? '#22c55e' : '#ef4444'}` }}>
        <h3 style={{ fontSize: '1.25rem', marginBottom: 8, display: 'flex', alignItems: 'center' }}>
          <span className={`status-dot ${isHealthy ? 'healthy' : 'unhealthy'}`}></span>
          {isHealthy ? "All Systems Operational" : "System Degraded"}
        </h3>
        <p style={{ color: 'var(--text-secondary)' }}>
          Last checked: {new Date().toLocaleString()}
        </p>
      </div>

      <div className="health-grid">
        <div className="health-card">
          <h3>Core Services</h3>
          <div className="health-item">
            <span className="label">API Server</span>
            <span className="value" style={{ color: '#4ade80' }}>Online</span>
          </div>
          <div className="health-item">
            <span className="label">Database</span>
            <span className="value" style={{ color: dbConnected ? '#4ade80' : '#f87171' }}>
              {dbConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="health-item">
            <span className="label">Detection Engine</span>
            <span className="value" style={{ color: '#4ade80' }}>Ready</span>
          </div>
        </div>

        <div className="health-card">
          <h3>System Statistics</h3>
          <div className="health-item">
            <span className="label">Monitored Endpoints</span>
            <span className="value">{health?.stats?.monitored_endpoints ?? "N/A"}</span>
          </div>
          <div className="health-item">
            <span className="label">Total Metrics Processed</span>
            <span className="value">{(health?.stats?.total_metrics ?? 0).toLocaleString()}</span>
          </div>
          <div className="health-item">
            <span className="label">Total Anomalies Found</span>
            <span className="value">{(health?.stats?.total_anomalies ?? 0).toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
