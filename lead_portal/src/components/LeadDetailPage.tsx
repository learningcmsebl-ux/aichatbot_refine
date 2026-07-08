import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LeadsAPI } from '../services/api';
import type { LeadDetail, LeadFeedback, LeadStatusHistory } from '../types';
import { LEAD_STATUSES } from '../types';
import { useAuth } from '../context/AuthContext';

export function LeadDetailPage() {
  const { ref } = useParams<{ ref: string }>();
  const { user } = useAuth();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [history, setHistory] = useState<LeadStatusHistory[]>([]);
  const [feedback, setFeedback] = useState<LeadFeedback[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [assignTo, setAssignTo] = useState('');
  const [assignNote, setAssignNote] = useState('');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackTo, setFeedbackTo] = useState('');

  const load = async () => {
    if (!ref) return;
    setError(null);
    try {
      const [d, h, f] = await Promise.all([
        LeadsAPI.get(ref),
        LeadsAPI.statusHistory(ref),
        LeadsAPI.feedbackList(ref),
      ]);
      setLead(d);
      setHistory(h);
      setFeedback(f);
      setNewStatus(d.status);
      setFeedbackTo(d.created_by_employee_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load lead');
    }
  };

  useEffect(() => { load(); }, [ref]);

  const onStatusUpdate = async () => {
    if (!ref || !newStatus) return;
    try {
      const updated = await LeadsAPI.updateStatus(ref, newStatus, statusNote || undefined);
      setLead(updated);
      setSuccess('Status updated.');
      setStatusNote('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed');
    }
  };

  const onAssign = async () => {
    if (!ref || !assignTo.trim()) return;
    try {
      const updated = await LeadsAPI.assign(ref, assignTo.trim(), assignNote || undefined);
      setLead(updated);
      setSuccess('Lead assigned.');
      setAssignNote('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Assign failed');
    }
  };

  const onFeedback = async () => {
    if (!ref || !feedbackText.trim() || !feedbackTo.trim()) return;
    try {
      await LeadsAPI.addFeedback(ref, feedbackText.trim(), feedbackTo.trim());
      setSuccess('Feedback recorded.');
      setFeedbackText('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Feedback failed');
    }
  };

  if (!lead) {
    return error ? <div className="error-banner">{error}</div> : <div className="empty">Loading…</div>;
  }

  return (
    <>
      <div className="page-header">
        <p><Link to="/leads">← Back to leads</Link></p>
        <h1>{lead.lead_reference_no}</h1>
        <p><span className={`badge ${lead.status}`}>{lead.status_label}</span> · {lead.product_type_label}</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {success && <div className="success-banner">{success}</div>}

      <div className="panel">
        <h3>Customer</h3>
        <dl className="detail-grid">
          <div><dt>Name</dt><dd>{lead.customer_name}</dd></div>
          <div><dt>Mobile</dt><dd>{lead.customer_mobile || '—'}</dd></div>
          <div><dt>Email</dt><dd>{lead.customer_email || '—'}</dd></div>
          <div><dt>Location</dt><dd>{lead.customer_location || '—'}</dd></div>
          <div><dt>Preferred branch</dt><dd>{lead.preferred_branch || '—'}</dd></div>
          <div><dt>Contact time</dt><dd>{lead.preferred_contact_time || '—'}</dd></div>
          <div><dt>Remarks</dt><dd>{lead.remarks || '—'}</dd></div>
        </dl>
      </div>

      <div className="panel">
        <h3>Referrer</h3>
        <dl className="detail-grid">
          <div><dt>Employee</dt><dd>{lead.created_by_name || lead.created_by_employee_id}</dd></div>
          <div><dt>Department</dt><dd>{lead.created_by_department || '—'}</dd></div>
          <div><dt>Branch</dt><dd>{lead.created_by_branch || '—'}</dd></div>
          <div><dt>Assigned to</dt><dd>{lead.assigned_to_user_id || 'Unassigned'}</dd></div>
          <div><dt>Created</dt><dd>{new Date(lead.created_at).toLocaleString()}</dd></div>
        </dl>
      </div>

      <div className="panel">
        <h3>Update status</h3>
        {lead.permissions?.can_update_status ? (
          <>
            <div className="form-row">
              <label>Status</label>
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                {LEAD_STATUSES.map((s) => (
                  <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label>Note (optional)</label>
              <input value={statusNote} onChange={(e) => setStatusNote(e.target.value)} />
            </div>
            <button type="button" onClick={onStatusUpdate}>Save status</button>
          </>
        ) : (
          <p className="empty">You do not have permission to update this lead&apos;s status.</p>
        )}
      </div>

      <div className="panel">
        <h3>Assign lead</h3>
        {lead.permissions?.can_assign ? (
          <>
            <div className="form-row">
              <label>Assign to (employee ID)</label>
              <input value={assignTo} onChange={(e) => setAssignTo(e.target.value)} placeholder="e.g. 2872" />
            </div>
            <div className="form-row">
              <label>Note (optional)</label>
              <input value={assignNote} onChange={(e) => setAssignNote(e.target.value)} />
            </div>
            <button type="button" onClick={onAssign}>Assign</button>
          </>
        ) : (
          <p className="empty">Assignment is restricted to sales managers and admins.</p>
        )}
      </div>

      <div className="panel">
        <h3>Feedback to referrer</h3>
        {lead.permissions?.can_add_feedback ? (
          <>
            <div className="form-row">
              <label>To employee ID</label>
              <input value={feedbackTo} onChange={(e) => setFeedbackTo(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Feedback</label>
              <textarea rows={3} value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)} />
            </div>
            <button type="button" onClick={onFeedback}>Submit feedback</button>
          </>
        ) : (
          <p className="empty">You do not have permission to add feedback on this lead.</p>
        )}
      </div>

      <div className="panel">
        <h3>Status history</h3>
        {history.length === 0 ? (
          <p className="empty">No history.</p>
        ) : (
          <ul>
            {history.map((h, i) => (
              <li key={i} style={{ marginBottom: '0.5rem' }}>
                {new Date(h.changed_at).toLocaleString()} — {h.old_status || '—'} → {h.new_status} by {h.changed_by}
                {h.note && ` (${h.note})`}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="panel">
        <h3>Feedback</h3>
        {feedback.length === 0 ? (
          <p className="empty">No feedback yet.</p>
        ) : (
          <ul>
            {feedback.map((f) => (
              <li key={f.id} style={{ marginBottom: '0.75rem' }}>
                <strong>{new Date(f.created_at).toLocaleDateString()}</strong> — to {f.feedback_to_employee_id}
                <br />{f.feedback_text}
              </li>
            ))}
          </ul>
        )}
      </div>

      {user && (
        <p style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
          Signed in as {user.full_name || user.username}
        </p>
      )}
    </>
  );
}
