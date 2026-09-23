import { useState, useEffect } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { getSystemHealth, getMetricsByEndpoint, getEndpoints, getAnomalies, getIncidents } from "../api";

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [endpoints, setEndpoints] = useState([]);
  const [latencyData, setLatencyData] = useState([]);
  const [errorData, setErrorData] = useState([]);
  const [trafficData, setTrafficData] = useState([]);
  const [recentAnomalies, setRecentAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [healthRes, endpointsRes, anomaliesRes, incidentsRes] = await Promise.all([
          getSystemHealth(),
          getEndpoints(),
          getAnomalies(),
          getIncidents(),
        ]);
        setHealth(healthRes);
        setEndpoints(endpointsRes);
        setRecentAnomalies(anomaliesRes.slice(0, 10));

        // Fetch metrics for first demo endpoint for charts
        const demoEndpoint = endpointsRes.find(e => e.name.includes("[demo]"));
        if (demoEndpoint) {
          const metrics = await getMetricsByEndpoint(demoEndpoint.id);
          // Take last 100 data points, reversed to chronological order
          const recent = metrics.slice(0, 100).reverse();
          
          setLatencyData(recent.map(m => ({
            time: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            latency: Math.round(m.response_time),
          })));
          
          setErrorData(recent.map(m => ({
            time: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            errorRate: m.request_count > 0 ? Math.round((m.error_count / m.request_count) * 100) : 0,
          })));

          setTrafficData(recent.map(m => ({
            time: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            requests: m.request_count,
          })));
        }
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <div className="loading">Loading dashboard...</div>;
  if (error) return <div className="error-state">Error: {error}</div>;

  const stats = health?.stats || {};

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Real-time overview of your API monitoring platform</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="card accent-blue">
          <div className="card-title">Monitored Endpoints</div>
          <div className="card-value">{stats.monitored_endpoints ?? 0}</div>
          <div className="card-subtitle">Active API endpoints</div>
        </div>
        <div className="card accent-green">
          <div className="card-title">Total Metrics</div>
          <div className="card-value">{(stats.total_metrics ?? 0).toLocaleString()}</div>
          <div className="card-subtitle">Data points collected</div>
        </div>
        <div className="card accent-yellow">
          <div className="card-title">Anomalies Detected</div>
          <div className="card-value">{(stats.total_anomalies ?? 0).toLocaleString()}</div>
          <div className="card-subtitle">Z-score + Isolation Forest</div>
        </div>
        <div className="card accent-red">
          <div className="card-title">Open Incidents</div>
          <div className="card-value">{stats.open_incidents ?? 0}</div>
          <div className="card-subtitle">Requiring attention</div>
        </div>
      </div>

      {/* Charts */}
      <div className="chart-grid">
        <div className="chart-card">
          <h3>Response Latency (ms)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={latencyData}>
              <defs>
                <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fill: '#6b6f80', fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6b6f80', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3a', borderRadius: 8 }} />
              <Area type="monotone" dataKey="latency" stroke="#6366f1" fill="url(#latencyGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Request Volume</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={trafficData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fill: '#6b6f80', fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6b6f80', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3a', borderRadius: 8 }} />
              <Bar dataKey="requests" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Error Rate (%)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={errorData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fill: '#6b6f80', fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#6b6f80', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3a', borderRadius: 8 }} />
              <Line type="monotone" dataKey="errorRate" stroke="#ef4444" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Anomalies */}
      <div className="table-wrapper">
        <div className="table-header">
          <h3>Recent Anomalies</h3>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Metric</th>
                <th>Severity</th>
                <th>Method</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {recentAnomalies.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.timestamp).toLocaleString()}</td>
                  <td>{a.metric_type}</td>
                  <td><span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span></td>
                  <td>{a.detection_method}</td>
                  <td style={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description}</td>
                </tr>
              ))}
              {recentAnomalies.length === 0 && (
                <tr><td colSpan="5" style={{ textAlign: 'center', padding: 40, color: '#6b6f80' }}>No anomalies detected yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
