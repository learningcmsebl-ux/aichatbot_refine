import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AuthAPI } from '../services/authApi';

export function ChangePasswordPage() {
  const { user, logout, completePasswordChange } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      await AuthAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      completePasswordChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Change your password</h1>
        <p className="sub">
          {user?.full_name || user?.username}, you must set a new password before using the Lead Portal.
        </p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="current">Current password</label>
          <input
            id="current"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            disabled={submitting}
            required
          />
          <label htmlFor="new">New password</label>
          <input
            id="new"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={submitting}
            required
            minLength={8}
          />
          <label htmlFor="confirm">Confirm new password</label>
          <input
            id="confirm"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={submitting}
            required
            minLength={8}
          />
          {error && <div className="login-error">{error}</div>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Updating…' : 'Update password'}
          </button>
          <button type="button" className="secondary link-btn" onClick={logout} disabled={submitting}>
            Sign out
          </button>
        </form>
      </div>
    </div>
  );
}
