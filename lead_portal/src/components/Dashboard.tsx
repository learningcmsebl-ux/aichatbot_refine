import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LeadsAPI } from '../services/api';
import type { LeadDashboardStats, LeadSummary } from '../types';

export function Dashboard() {
  const [stats, setStats] = useState<LeadDashboardStats | null>(null);
  const [recent, setRecent] = useState<LeadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([LeadsAPI.stats(), LeadsAPI.list({ limit: 10 })])
      .then(([s, list]) => {
        setStats(s);
        setRecent(list.items);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty">Loading dashboard…</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!stats) return null;

  const counts = stats.by_status;

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Lead pipeline overview (scoped to your access)</p>
      </div>
      <div className="stats-grid">
        <div className="stat-card"><div className="value">{stats.total}</div><div className="label">Total</div></div>
        <div className="stat-card"><div className="value">{counts.submitted || 0}</div><div className="label">Submitted</div></div>
        <div className="stat-card"><div className="value">{counts.assigned || 0}</div><div className="label">Assigned</div></div>
        <div className="stat-card"><div className="value">{counts.contacted || 0}</div><div className="label">Contacted</div></div>
        <div className="stat-card"><div className="value">{counts.interested || 0}</div><div className="label">Interested</div></div>
        <div className="stat-card"><div className="value">{counts.converted || 0}</div><div className="label">Converted</div></div>
        <div className="stat-card"><div className="value">{stats.pending_assigned}</div><div className="label">Pending follow-up</div></div>
      </div>
      {Object.keys(stats.by_product).length > 0 && (
        <div className="panel">
          <h3>By product</h3>
          <ul>
            {Object.entries(stats.by_product).map(([label, count]) => (
              <li key={label}>{label}: {count}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="panel">
        <h3>Recent leads</h3>
        {recent.length === 0 ? (
          <p className="empty">No leads yet.</p>
        ) : (
          <table className="leads-table">
            <thead>
              <tr>
                <th>Lead ID</th>
                <th>Customer</th>
                <th>Product</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((l) => (
                <tr key={l.lead_reference_no}>
                  <td><Link to={`/leads/${l.lead_reference_no}`}>{l.lead_reference_no}</Link></td>
                  <td>{l.customer_name}</td>
                  <td>{l.product_type_label}</td>
                  <td><span className={`badge ${l.status}`}>{l.status_label}</span></td>
                  <td>{new Date(l.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
