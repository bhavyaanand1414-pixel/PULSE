import { useState } from "react";
import Dashboard from "./components/Dashboard";
import Endpoints from "./components/Endpoints";
import Metrics from "./components/Metrics";
import Anomalies from "./components/Anomalies";
import Incidents from "./components/Incidents";
import SystemHealth from "./components/SystemHealth";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "endpoints", label: "Endpoints", icon: "🔗" },
  { id: "metrics", label: "Metrics", icon: "📈" },
  { id: "anomalies", label: "Anomalies", icon: "⚠️" },
  { id: "incidents", label: "Incidents", icon: "🚨" },
  { id: "health", label: "System Health", icon: "💚" },
];

export default function App() {
  const [currentPage, setCurrentPage] = useState("dashboard");

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard": return <Dashboard />;
      case "endpoints": return <Endpoints />;
      case "metrics": return <Metrics />;
      case "anomalies": return <Anomalies />;
      case "incidents": return <Incidents />;
      case "health": return <SystemHealth />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>PULSE</h1>
          <span>API Monitoring Platform</span>
        </div>
        <ul className="nav-items">
          {NAV_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                className={currentPage === item.id ? "active" : ""}
                onClick={() => setCurrentPage(item.id)}
              >
                <span>{item.icon}</span>
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}
