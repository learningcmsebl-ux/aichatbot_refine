import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LeadsAPI, type LeadSummary } from '../services/api';
import { LEAD_STATUSES, PRODUCT_TYPES } from '../types';
import { useLeadPermissions } from '../hooks/useLeadPermissions';
import { getAuthHeaders } from '../utils/authStorage';

type ListMode = 'all' | 'my' | 'assigned';

interface Props {
  mode: ListMode;
  title: string;
  subtitle: string;
}

export function LeadListPage({ mode, title, subtitle }: Props) {
  const perms = useLeadPermissions();
  const [leads, setLeads] = useState<LeadSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState('');
  const [product, setProduct] = useState('');
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let res;
      if (mode === 'my') {
        res = await LeadsAPI.mySubmitted();
      } else if (mode === 'assigned') {
        res = await LeadsAPI.assigned();
      } else if (search.trim()) {
        res = await LeadsAPI.search(search.trim());
      } else {
        res = await LeadsAPI.list({
          status: status || undefined,
          product_type: product || undefined,
        });
      }
      setLeads(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [mode, status, product, search]);

  useEffect(() => { load(); }, [load]);

  const handleExport = () => {
    const url = LeadsAPI.exportCsv({ status: status || undefined, product_type: product || undefined });
    fetch(url, { headers: getAuthHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error('Export not permitted');
        return r.text();
      })
      .then((csv) => {
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'leads_export.csv';
        a.click();
      })
      .catch((e) => setError(e.message));
  };

  return (
    <>
      <div className="page-header">
        <h1>{title}</h1>
        <p>{subtitle} ({total} total)</p>
      </div>

      {mode === 'all' && (
        <div className="filters">
          <div>
            <label>Search</label>
            <input
              placeholder="Name, mobile, LD-…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
            />
          </div>
          <div>
            <label>Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {LEAD_STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <div>
            <label>Product</label>
            <select value={product} onChange={(e) => setProduct(e.target.value)}>
              <option value="">All</option>
              {PRODUCT_TYPES.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <button type="button" onClick={load}>Apply</button>
          {perms.export && (
            <button type="button" className="secondary" onClick={handleExport}>Export CSV</button>
          )}
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
      {loading ? (
        <div className="empty">Loading…</div>
      ) : leads.length === 0 ? (
        <div className="empty">No leads found.</div>
      ) : (
        <div className="panel" style={{ padding: 0, overflow: 'auto' }}>
          <table className="leads-table">
            <thead>
              <tr>
                <th>Lead ID</th>
                <th>Customer</th>
                <th>Mobile</th>
                <th>Product</th>
                <th>Branch</th>
                <th>Status</th>
                <th>Assigned</th>
                <th>Referrer</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.lead_reference_no}>
                  <td><Link to={`/leads/${l.lead_reference_no}`}>{l.lead_reference_no}</Link></td>
                  <td>{l.customer_name}</td>
                  <td>{l.customer_mobile || '—'}</td>
                  <td>{l.product_type_label}</td>
                  <td>{l.preferred_branch || '—'}</td>
                  <td><span className={`badge ${l.status}`}>{l.status_label}</span></td>
                  <td>{l.assigned_to_user_id || '—'}</td>
                  <td>{l.created_by_name || l.created_by_employee_id}</td>
                  <td>{new Date(l.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
