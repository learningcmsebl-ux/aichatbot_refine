import type { EmployeeUser } from '../types';

const TOKEN_KEY = 'lead_portal_auth_token';
const USER_KEY = 'lead_portal_auth_user';
const MUST_CHANGE_KEY = 'lead_portal_must_change_password';

export function isAuthTokenValid(token: string | null): boolean {
  if (!token) return false;
  try {
    const payloadPart = token.split('.')[1];
    if (!payloadPart) return false;
    const payload = JSON.parse(atob(payloadPart.replace(/-/g, '+').replace(/_/g, '/')));
    if (!payload.exp) return true;
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getAuthToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!isAuthTokenValid(token)) {
    if (token) clearAuthSession();
    return null;
  }
  return token;
}

export function getAuthUser(): EmployeeUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as EmployeeUser;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: EmployeeUser, mustChangePassword = false): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem(MUST_CHANGE_KEY, mustChangePassword ? '1' : '0');
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(MUST_CHANGE_KEY);
}

export function getMustChangePassword(): boolean {
  return localStorage.getItem(MUST_CHANGE_KEY) === '1';
}

export function setMustChangePassword(value: boolean): void {
  localStorage.setItem(MUST_CHANGE_KEY, value ? '1' : '0');
}

export function getAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
