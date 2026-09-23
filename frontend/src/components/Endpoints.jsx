import { useState, useEffect } from "react";
import { getEndpoints } from "../api";

export default function Endpoints() {
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getEndpoints()
      .then(setEndpoints)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading endpoints...</div>;
  if (error) return <div className="error-state">Error: {error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Endpoints</h2>
        <p>All monitored API endpoints</p>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>URL</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.map((ep) => (
              <tr key={ep.id}>
                <td>{ep.id}</td>
                <td style={{ fontWeight: 600, color: '#e4e6ef' }}>{ep.name}</td>
                <td><code style={{ color: '#818cf8', fontSize: '0.8rem' }}>{ep.url}</code></td>
                <td>{new Date(ep.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {endpoints.length === 0 && (
              <tr><td colSpan="4" className="empty-state">No endpoints registered</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
