import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { getEndpoints, getMetricsByEndpoint } from "../api";

export default function Metrics() {
  const [endpoints, setEndpoints] = useState([]);
  const [selectedEp, setSelectedEp] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [sourceFilter, setSourceFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getEndpoints()
      .then((eps) => {
        setEndpoints(eps);
        // Prefer first live-monitored endpoint, fallback to demo
        const live = eps.find(e => e.monitoring_enabled);
        const demo = eps.find(e => e.name.includes("[demo]"));
        if (live) setSelectedEp(live.id);
        else if (demo) setSelectedEp(demo.id);
        else if (eps.length > 0) setSelectedEp(eps[0].id);
        setLoading(false);
      })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!selectedEp) return;
    setLoading(true);
    getMetricsByEndpoint(selectedEp)
      .then((data) => { setMetrics(data.slice(0, 200).reverse()); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [selectedEp]);

  // Auto-refresh when viewing a live endpoint
  useEffect(() => {
    if (!selectedEp) return;
    const ep = endpoints.find(e => e.id === selectedEp);
    if (!ep || !ep.monitoring_enabled) return;

    const timer = setInterval(() => {
      getMetricsByEndpoint(selectedEp)
        .then((data) => setMetrics(data.slice(0, 200).reverse()))
        .catch(() => {});
    }, 10000);

    return () => clearInterval(timer);
  }, [selectedEp, endpoints]);

  if (error) return <div className="error-state">Error: {error}</div>;

  const filteredMetrics = sourceFilter
    ? metrics.filter(m => (m.source || "demo") === sourceFilter)
    : metrics;

  const chartData = filteredMetrics.map(m => ({
    time: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    latency: Math.round(m.response_time),
    requests: m.request_count,
    errors: m.error_count,
    source: m.source || "demo",
  }));

  const currentEp = endpoints.find(e => e.id === selectedEp);
  const hasLiveData = metrics.some(m => (m.source || "demo") === "live");

  return (
    <div>
      <div className="page-header">
        <h2>Metrics</h2>
        <p>API performance metrics over time</p>
      </div>

      <div className="filter-bar">
        <select value={selectedEp || ""} onChange={(e) => setSelectedEp(Number(e.target.value))}>
          {endpoints.map(ep => (
            <option key={ep.id} value={ep.id}>
              {ep.name} {ep.monitoring_enabled ? "🟢" : ""}
            </option>
          ))}
        </select>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
          <option value="">All Sources</option>
          <option value="live">🟢 Live Only</option>
          <option value="demo">🟣 Demo Only</option>
        </select>
        {currentEp?.monitoring_enabled && (
          <span style={{ fontSize: "0.8rem", color: "var(--success)", display: "flex", alignItems: "center", gap: 6 }}>
            <span className="status-dot healthy" />
            Live monitoring active — auto-refreshing
          </span>
        )}
      </div>

      {loading ? <div className="loading">Loading metrics...</div> : (
        <>
          <div className="chart-grid">
            <div className="chart-card">
              <h3>Response Time (ms) {hasLiveData && sourceFilter !== "demo" && <span style={{ fontSize: "0.7rem", color: "var(--success)", fontWeight: 400 }}>● includes live data</span>}</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                  <XAxis dataKey="time" tick={{ fill: '#6b6f80', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: '#6b6f80', fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3a', borderRadius: 8 }} />
                  <Line type="monotone" dataKey="latency" stroke="#6366f1" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-card">
              <h3>Request Count {sourceFilter === "live" && <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 400 }}>1 = one probe</span>}</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                  <XAxis dataKey="time" tick={{ fill: '#6b6f80', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: '#6b6f80', fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3a', borderRadius: 8 }} />
                  <Line type="monotone" dataKey="requests" stroke="#22c55e" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="table-wrapper">
            <div className="table-header">
              <h3>Raw Metrics ({filteredMetrics.length} records)</h3>
            </div>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Source</th>
                    <th>Latency (ms)</th>
                    <th>Status</th>
                    <th>Requests</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMetrics.slice(-50).reverse().map((m) => (
                    <tr key={m.id}>
                      <td>{new Date(m.timestamp).toLocaleString()}</td>
                      <td>
                        {(m.source || "demo") === "live" ? (
                          <span className="badge" style={{ background: "rgba(34,197,94,0.15)", color: "#4ade80" }}>live</span>
                        ) : (
                          <span className="badge" style={{ background: "rgba(168,85,247,0.15)", color: "#c084fc" }}>demo</span>
                        )}
                      </td>
                      <td>{m.response_time.toFixed(1)}</td>
                      <td>
                        <span style={{ color: m.is_error ? '#f87171' : '#4ade80' }}>
                          {m.status_code === 0 ? "ERR" : m.status_code}
                        </span>
                      </td>
                      <td>{m.request_count}</td>
                      <td style={{ color: m.error_count > 0 ? '#f87171' : 'inherit' }}>{m.error_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
