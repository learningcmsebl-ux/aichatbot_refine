import { useCallback, useEffect, useState } from 'react';
import type { AuthConfigResponse, EmployeeUser, LoginRequest } from '../types';
import {
  clearAuthSession,
  getAuthHeaders,
  getAuthToken,
  getAuthUser,
  getMustChangePassword,
  isAuthTokenValid,
  setAuthSession,
  setMustChangePassword,
} from '../utils/authStorage';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function fetchCurrentUser(): Promise<{ user: EmployeeUser; mustChange: boolean } | null> {
  const token = getAuthToken();
  if (!token) return null;
  const response = await fetch(`${API_BASE}/auth/me`, { headers: getAuthHeaders() });
  if (!response.ok) {
    clearAuthSession();
    return null;
  }
  const data = await response.json();
  return {
    user: data.user as EmployeeUser,
    mustChange: Boolean(data.must_change_password),
  };
}

export function useAuthState() {
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [user, setUser] = useState<EmployeeUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mustChangePassword, setMustChangePasswordState] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/auth/config`);
        if (!res.ok) throw new Error('Failed to load auth config');
        const config: AuthConfigResponse = await res.json();
        if (cancelled) return;
        setAuthEnabled(config.auth_enabled);
        if (!config.auth_enabled) {
          setUser(null);
          return;
        }
        const token = getAuthToken();
        if (!token || !isAuthTokenValid(token)) {
          clearAuthSession();
          setUser(null);
          return;
        }
        const stored = getAuthUser();
        if (stored) setUser(stored);
        const verified = await fetchCurrentUser();
        if (!cancelled && verified) {
          setAuthSession(getAuthToken()!, verified.user, verified.mustChange);
          setUser(verified.user);
          setMustChangePasswordState(verified.mustChange);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Auth error');
          setAuthEnabled(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    setError(null);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });
    if (!res.ok) {
      let message = 'Invalid username or password';
      try {
        const body = await res.json();
        if (body?.detail) message = typeof body.detail === 'string' ? body.detail : message;
      } catch { /* ignore */ }
      setError(message);
      throw new Error(message);
    }
    const data = await res.json();
    const mustChange = Boolean(data.must_change_password);
    setAuthSession(data.access_token, data.user, mustChange);
    setUser(data.user);
    setMustChangePasswordState(mustChange);
    return data.user as EmployeeUser;
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setError(null);
    setMustChangePasswordState(false);
  }, []);

  const completePasswordChange = useCallback(() => {
    setMustChangePassword(false);
    setMustChangePasswordState(false);
  }, []);

  return {
    authEnabled,
    user,
    loading,
    error,
    login,
    logout,
    mustChangePassword: mustChangePassword || getMustChangePassword(),
    completePasswordChange,
    isAuthenticated: !authEnabled || Boolean(getAuthToken() && user),
    setError,
  };
}
