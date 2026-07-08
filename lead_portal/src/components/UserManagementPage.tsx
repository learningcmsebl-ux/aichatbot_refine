import { useCallback, useEffect, useState } from 'react';
import type { DirectoryUserPreview, PortalUserSummary } from '../types';
import { PortalUsersAPI } from '../services/api';

const ROLE_OPTIONS = [
  { value: 'sales_user', label: 'Sales user' },
  { value: 'sales_manager', label: 'Sales manager' },
];

export function UserManagementPage() {
  const [users, setUsers] = useState<PortalUserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [employeeId, setEmployeeId] = useState('');
  const [leadRole, setLeadRole] = useState('sales_user');
  const [preview, setPreview] = useState<DirectoryUserPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await PortalUsersAPI.list();
      setUsers(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onLookup = async () => {
    const id = employeeId.trim();
    if (!id) return;
    setError(null);
    setSuccess(null);
    setPreview(null);
    setLookupLoading(true);
    try {
      const result = await PortalUsersAPI.lookup(id);
      setPreview(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Employee not found');
    } finally {
      setLookupLoading(false);
    }
  };

  const onRegister = async () => {
    if (!preview || preview.already_registered) return;
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const res = await PortalUsersAPI.register({
        employee_id: preview.employee_id,
        lead_role: leadRole,
      });
      setSuccess(res.message);
      setEmployeeId('');
      setPreview(null);
      setLeadRole('sales_user');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to register user');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Sales team users</h1>
        <p className="sub">
          Enter an employee ID to fetch their profile from Active Directory, then add them to the lead system.
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {success && <div className="success-banner">{success}</div>}

      <section className="panel">
        <h2>Add user by employee ID</h2>
        <div className="form-grid">
          <div>
            <label htmlFor="employeeId">Employee ID</label>
            <input
              id="employeeId"
              value={employeeId}
              onChange={(e) => {
                setEmployeeId(e.target.value);
                setPreview(null);
              }}
              placeholder="e.g. 2699"
              disabled={lookupLoading || submitting}
            />
          </div>
          <div className="form-actions lookup-row">
            <button type="button" onClick={onLookup} disabled={lookupLoading || !employeeId.trim()}>
              {lookupLoading ? 'Looking up…' : 'Fetch from AD'}
            </button>
          </div>
        </div>

        {preview && (
          <div className="preview-card">
            <h3>Employee preview</h3>
            <dl className="detail-grid">
              <div><dt>Employee ID</dt><dd>{preview.employee_id}</dd></div>
              <div><dt>Windows login</dt><dd>{preview.username}</dd></div>
              <div><dt>Name</dt><dd>{preview.full_name || '—'}</dd></div>
              <div><dt>Email</dt><dd>{preview.email || '—'}</dd></div>
              <div><dt>Department</dt><dd>{preview.department || '—'}</dd></div>
            </dl>
            {preview.already_registered ? (
              <p className="info-banner">This employee is already registered in the lead portal.</p>
            ) : (
              <div className="register-row">
                <div>
                  <label htmlFor="leadRole">Portal role</label>
                  <select
                    id="leadRole"
                    value={leadRole}
                    onChange={(e) => setLeadRole(e.target.value)}
                    disabled={submitting}
                  >
                    {ROLE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <button type="button" onClick={onRegister} disabled={submitting}>
                  {submitting ? 'Adding…' : 'Add to lead system'}
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Registered users</h2>
        {loading ? (
          <p className="empty">Loading…</p>
        ) : users.length === 0 ? (
          <p className="empty">No users registered yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Login</th>
                  <th>Employee ID</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Registered</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.username}>
                    <td>{u.username}</td>
                    <td>{u.employee_id || '—'}</td>
                    <td>{u.full_name || '—'}</td>
                    <td>{u.lead_role}</td>
                    <td>{new Date(u.provisioned_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
