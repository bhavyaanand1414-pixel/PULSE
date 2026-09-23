import { useState, useEffect } from "react";
import { getIncidents, resolveIncident, updateIncident } from "../api";

export default function Incidents() {
  const [incidents, setIncidents] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchIncidents = () => {
    setLoading(true);
    const params = {};
    if (statusFilter) params.status = statusFilter;
    getIncidents(params)
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchIncidents(); }, [statusFilter]);

  const handleResolve = async (id) => {
    try {
      await resolveIncident(id);
      fetchIncidents();
    } catch (err) {
      alert(`Failed to resolve: ${err.message}`);
    }
  };

  const handleStatusChange = async (id, newStatus) => {
    try {
      await updateIncident(id, { status: newStatus });
      fetchIncidents();
    } catch (err) {
      alert(`Failed to update: ${err.message}`);
    }
  };

  if (error) return <div className="error-state">Error: {error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Incidents</h2>
        <p>Track and manage detected issues</p>
      </div>

      <div className="filter-bar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="INVESTIGATING">Investigating</option>
          <option value="RESOLVED">Resolved</option>
        </select>
      </div>

      {loading ? <div className="loading">Loading incidents...</div> : (
        <div className="table-wrapper">
          <div className="table-header">
            <h3>Incidents ({incidents.length})</h3>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Resolved</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id}>
                    <td>#{inc.id}</td>
                    <td style={{ fontWeight: 600, color: '#e4e6ef', maxWidth: 300 }}>{inc.title}</td>
                    <td><span className={`badge badge-${inc.severity.toLowerCase()}`}>{inc.severity}</span></td>
                    <td><span className={`badge badge-${inc.status.toLowerCase()}`}>{inc.status}</span></td>
                    <td>{new Date(inc.created_at).toLocaleString()}</td>
                    <td>{inc.resolved_at ? new Date(inc.resolved_at).toLocaleString() : "—"}</td>
                    <td>
                      {inc.status !== "RESOLVED" && (
                        <div className="btn-group">
                          {inc.status === "OPEN" && (
                            <button className="btn btn-sm" onClick={() => handleStatusChange(inc.id, "INVESTIGATING")}>
                              Investigate
                            </button>
                          )}
                          <button className="btn btn-success btn-sm" onClick={() => handleResolve(inc.id)}>
                            Resolve
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {incidents.length === 0 && (
                  <tr><td colSpan="7" style={{ textAlign: 'center', padding: 40, color: '#6b6f80' }}>No incidents found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
