import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export function LoginPage() {
  const { login, error, setError } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [passwordHint, setPasswordHint] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/auth/config`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.default_password_hint) setPasswordHint(data.default_password_hint);
      })
      .catch(() => undefined);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ username: username.trim(), password });
    } catch {
      /* handled in hook */
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Sales Lead Portal</h1>
        <p className="sub">Eastern Bank PLC — employee sign-in</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="username">Email or Windows ID</label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={submitting}
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            required
          />
          {error && <div className="login-error">{error}</div>}
          {passwordHint && <p className="login-hint">{passwordHint}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
