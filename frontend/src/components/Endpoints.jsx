import { useState, useEffect } from "react";
import {
  getEndpoints, createEndpoint, deleteEndpoint,
  startMonitoring, stopMonitoring, probeEndpoint,
} from "../api";

export default function Endpoints() {
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [actionLoading, setActionLoading] = useState({});

  // Form state
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formMonitor, setFormMonitor] = useState(false);
  const [formInterval, setFormInterval] = useState(30);

  const fetchEndpoints = () => {
    setLoading(true);
    getEndpoints()
      .then(setEndpoints)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchEndpoints();
    // Auto-refresh every 15 seconds to show updated last_check fields
    const timer = setInterval(fetchEndpoints, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await createEndpoint({
        name: formName,
        url: formUrl,
        monitoring_enabled: formMonitor,
        monitoring_interval: formInterval,
      });
      setFormName("");
      setFormUrl("");
      setFormMonitor(false);
      setFormInterval(30);
      setShowForm(false);
      fetchEndpoints();
    } catch (err) {
      alert(`Failed to create endpoint: ${err.message}`);
    }
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`Delete "${name}" and all its metrics?`)) return;
    try {
      await deleteEndpoint(id);
      fetchEndpoints();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleToggleMonitoring = async (ep) => {
    setActionLoading(prev => ({ ...prev, [ep.id]: true }));
    try {
      if (ep.monitoring_enabled) {
        await stopMonitoring(ep.id);
      } else {
        await startMonitoring(ep.id, ep.monitoring_interval || 30);
      }
      fetchEndpoints();
    } catch (err) {
      alert(`Monitoring action failed: ${err.message}`);
    }
    setActionLoading(prev => ({ ...prev, [ep.id]: false }));
  };

  const handleProbe = async (ep) => {
    setActionLoading(prev => ({ ...prev, [`probe_${ep.id}`]: true }));
    try {
      const result = await probeEndpoint(ep.id);
      alert(
        `Probe result for "${ep.name}":\n` +
        `Status: ${result.status_code}\n` +
        `Latency: ${result.response_time.toFixed(1)}ms\n` +
        `Error: ${result.is_error}`
      );
      fetchEndpoints();
    } catch (err) {
      alert(`Probe failed: ${err.message}`);
    }
    setActionLoading(prev => ({ ...prev, [`probe_${ep.id}`]: false }));
  };

  const isDemo = (ep) => ep.name.includes("[demo]");

  const formatTime = (ts) => {
    if (!ts) return "—";
    const d = new Date(ts);
    const secs = Math.round((Date.now() - d.getTime()) / 1000);
    if (secs < 60) return `${secs}s ago`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    return d.toLocaleTimeString();
  };

  if (loading && endpoints.length === 0)
    return <div className="loading">Loading endpoints...</div>;
  if (error) return <div className="error-state">Error: {error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Endpoints</h2>
        <p>All monitored API endpoints — register new ones and control live monitoring</p>
      </div>

      {/* Add Endpoint Button / Form */}
      <div style={{ marginBottom: 20 }}>
        {!showForm ? (
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            + Add Endpoint
          </button>
        ) : (
          <div className="card" style={{ maxWidth: 600 }}>
            <h3 style={{ marginBottom: 16 }}>Register New Endpoint</h3>
            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 4 }}>
                  Name
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. My API Service"
                  required
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontFamily: "inherit",
                    fontSize: "0.875rem",
                  }}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 4 }}>
                  URL
                </label>
                <input
                  type="url"
                  value={formUrl}
                  onChange={(e) => setFormUrl(e.target.value)}
                  placeholder="https://api.example.com/health"
                  required
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontFamily: "inherit",
                    fontSize: "0.875rem",
                  }}
                />
              </div>
              <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 16 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={formMonitor}
                    onChange={(e) => setFormMonitor(e.target.checked)}
                    style={{ accentColor: "var(--accent)" }}
                  />
                  Start live monitoring immediately
                </label>
                {formMonitor && (
                  <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem" }}>
                    every
                    <select
                      value={formInterval}
                      onChange={(e) => setFormInterval(Number(e.target.value))}
                      style={{
                        padding: "4px 8px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border)",
                        background: "var(--bg-secondary)",
                        color: "var(--text-primary)",
                        fontFamily: "inherit",
                      }}
                    >
                      <option value={10}>10s</option>
                      <option value={15}>15s</option>
                      <option value={30}>30s</option>
                      <option value={60}>60s</option>
                      <option value={120}>2min</option>
                      <option value={300}>5min</option>
                    </select>
                  </label>
                )}
              </div>
              <div className="btn-group">
                <button type="submit" className="btn btn-primary">Create</button>
                <button type="button" className="btn" onClick={() => setShowForm(false)}>Cancel</button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Endpoints Table */}
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>URL</th>
              <th>Source</th>
              <th>Monitoring</th>
              <th>Last Check</th>
              <th>Last Status</th>
              <th>Last Latency</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.map((ep) => (
              <tr key={ep.id}>
                <td>{ep.id}</td>
                <td style={{ fontWeight: 600, color: "#e4e6ef" }}>{ep.name}</td>
                <td>
                  <code style={{ color: "#818cf8", fontSize: "0.8rem" }}>{ep.url}</code>
                </td>
                <td>
                  {isDemo(ep) ? (
                    <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#c084fc" }}>demo</span>
                  ) : (
                    <span className="badge" style={{ background: "rgba(34,197,94,0.15)", color: "#4ade80" }}>live</span>
                  )}
                </td>
                <td>
                  {ep.monitoring_enabled ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem" }}>
                      <span className="status-dot healthy" />
                      Active ({ep.monitoring_interval}s)
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Off</span>
                  )}
                </td>
                <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  {formatTime(ep.last_check_at)}
                </td>
                <td>
                  {ep.last_status_code != null ? (
                    <span style={{ color: ep.last_status_code >= 400 || ep.last_status_code === 0 ? "#f87171" : "#4ade80", fontWeight: 600 }}>
                      {ep.last_status_code === 0 ? "ERR" : ep.last_status_code}
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>—</span>
                  )}
                </td>
                <td>
                  {ep.last_response_time != null ? (
                    <span style={{ color: ep.last_response_time > 1000 ? "#fbbf24" : "var(--text-secondary)" }}>
                      {ep.last_response_time.toFixed(0)}ms
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>—</span>
                  )}
                </td>
                <td>
                  <div className="btn-group">
                    {!isDemo(ep) && (
                      <>
                        <button
                          className={`btn btn-sm ${ep.monitoring_enabled ? "" : "btn-primary"}`}
                          onClick={() => handleToggleMonitoring(ep)}
                          disabled={actionLoading[ep.id]}
                        >
                          {actionLoading[ep.id]
                            ? "..."
                            : ep.monitoring_enabled
                            ? "⏹ Stop"
                            : "▶ Start"
                          }
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={() => handleProbe(ep)}
                          disabled={actionLoading[`probe_${ep.id}`]}
                        >
                          {actionLoading[`probe_${ep.id}`] ? "..." : "🔍 Probe"}
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={() => handleDelete(ep.id, ep.name)}
                          style={{ color: "#f87171" }}
                        >
                          ✕
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {endpoints.length === 0 && (
              <tr>
                <td colSpan="9" className="empty-state">No endpoints registered</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
