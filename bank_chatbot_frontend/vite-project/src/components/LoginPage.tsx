import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

export const LoginPage: React.FC = () => {
  const { login, error, setError } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ username: username.trim(), password });
    } catch {
      // error state handled in useAuth
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src="/dia-avatar.png" alt="EBL DIA" className="login-logo" />
          <h1>EBL DIA 2.0</h1>
          <p>Employee sign-in</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="username">Email or Windows ID</label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            placeholder="e.g. jdoe or jdoe@ebl-bd.com"
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

          <button type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="login-footnote">
          Use your EBL Active Directory credentials. Sign in once — you stay signed in while your session is active (page refresh, new tab). Sign out or session expiry will ask for your password again.
        </p>
      </div>
    </div>
  );
};
