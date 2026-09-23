import { useState, useEffect } from "react";
import { getAnomalies, getEndpoints, detectAnomalies } from "../api";

export default function Anomalies() {
  const [anomalies, setAnomalies] = useState([]);
  const [endpoints, setEndpoints] = useState([]);
  const [severityFilter, setSeverityFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState(null);

  const fetchAnomalies = () => {
    setLoading(true);
    const params = {};
    if (severityFilter) params.severity = severityFilter;
    if (methodFilter) params.detection_method = methodFilter;
    getAnomalies(params)
      .then(setAnomalies)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    getEndpoints().then(setEndpoints).catch(() => {});
    fetchAnomalies();
  }, [severityFilter, methodFilter]);

  const handleDetect = async (endpointId) => {
    setDetecting(true);
    try {
      const result = await detectAnomalies(endpointId, "hybrid");
      alert(`Detection complete: ${result.total_new_anomalies} new anomalies found`);
      fetchAnomalies();
    } catch (err) {
      alert(`Detection failed: ${err.message}`);
    }
    setDetecting(false);
  };

  if (error) return <div className="error-state">Error: {error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Anomalies</h2>
        <p>Detected anomalies across all monitored endpoints</p>
      </div>

      <div className="filter-bar">
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
          <option value="">All Severities</option>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="CRITICAL">Critical</option>
        </select>
        <select value={methodFilter} onChange={(e) => setMethodFilter(e.target.value)}>
          <option value="">All Methods</option>
          <option value="z_score">Z-Score</option>
          <option value="isolation_forest">Isolation Forest</option>
        </select>
        <div className="btn-group" style={{ marginLeft: 'auto' }}>
          {endpoints.filter(e => e.name.includes("[demo]")).map(ep => (
            <button
              key={ep.id}
              className="btn btn-primary btn-sm"
              onClick={() => handleDetect(ep.id)}
              disabled={detecting}
            >
              {detecting ? "Detecting..." : `Detect: ${ep.name.replace(" [demo]", "")}`}
            </button>
          ))}
        </div>
      </div>

      {loading ? <div className="loading">Loading anomalies...</div> : (
        <div className="table-wrapper">
          <div className="table-header">
            <h3>Anomalies ({anomalies.length})</h3>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Endpoint</th>
                  <th>Metric</th>
                  <th>Observed</th>
                  <th>Expected</th>
                  <th>Score</th>
                  <th>Severity</th>
                  <th>Method</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.slice(0, 100).map((a) => (
                  <tr key={a.id}>
                    <td>{new Date(a.timestamp).toLocaleString()}</td>
                    <td>{a.endpoint_id}</td>
                    <td>{a.metric_type}</td>
                    <td style={{ fontWeight: 600 }}>
                      {a.metric_type === "error_rate" ? `${(a.observed_value * 100).toFixed(1)}%` : a.observed_value.toFixed(1)}
                    </td>
                    <td style={{ color: '#6b6f80' }}>
                      {a.metric_type === "error_rate" ? `${(a.expected_value * 100).toFixed(1)}%` : a.expected_value.toFixed(1)}
                    </td>
                    <td>{a.anomaly_score.toFixed(2)}</td>
                    <td><span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                    <td style={{ fontSize: '0.75rem' }}>{a.detection_method}</td>
                  </tr>
                ))}
                {anomalies.length === 0 && (
                  <tr><td colSpan="8" style={{ textAlign: 'center', padding: 40, color: '#6b6f80' }}>No anomalies found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
