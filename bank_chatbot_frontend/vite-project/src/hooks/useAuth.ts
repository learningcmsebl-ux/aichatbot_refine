import { useCallback, useEffect, useState } from 'react';
import type { AuthConfigResponse, EmployeeUser, LoginRequest } from '../types';
import {
  clearAuthSession,
  getAuthHeaders,
  getAuthToken,
  getAuthUser,
  isAuthTokenValid,
  setAuthSession,
} from '../utils/authStorage';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function fetchCurrentUser(): Promise<EmployeeUser | null> {
  const token = getAuthToken();
  if (!token) return null;

  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    clearAuthSession();
    return null;
  }
  const data = await response.json();
  return data.user as EmployeeUser;
}

export function useAuth() {
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [user, setUser] = useState<EmployeeUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadConfig() {
      try {
        const response = await fetch(`${API_BASE}/auth/config`);
        if (!response.ok) {
          throw new Error('Failed to load auth configuration');
        }
        const config: AuthConfigResponse = await response.json();
        if (cancelled) return;

        setAuthEnabled(config.auth_enabled);

        if (!config.auth_enabled) {
          setUser(null);
          clearAuthSession();
          return;
        }

        const token = getAuthToken();
        if (!token || !isAuthTokenValid(token)) {
          clearAuthSession();
          setUser(null);
          return;
        }

        const storedUser = getAuthUser();
        if (storedUser) {
          setUser(storedUser);
        }

        const verifiedUser = await fetchCurrentUser();
        if (!cancelled && verifiedUser) {
          setAuthSession(getAuthToken()!, verifiedUser);
          setUser(verifiedUser);
        } else if (!cancelled) {
          setUser(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Auth configuration error');
          setAuthEnabled(false);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    setError(null);
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      let message = 'Invalid username or password';
      try {
        const body = await response.json();
        if (body?.detail) {
          message = typeof body.detail === 'string' ? body.detail : message;
        }
      } catch {
        // ignore parse errors
      }
      setError(message);
      throw new Error(message);
    }

    const data = await response.json();
    setAuthSession(data.access_token, data.user);
    setUser(data.user);
    return data.user as EmployeeUser;
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setUser(null);
    setError(null);
  }, []);

  const isAuthenticated = !authEnabled || Boolean(getAuthToken() && user);

  return {
    authEnabled,
    user,
    loading,
    error,
    login,
    logout,
    isAuthenticated,
    setError,
  };
}
