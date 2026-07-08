import type { EmployeeUser } from '../types';

const TOKEN_KEY = 'bank_chatbot_auth_token';
const USER_KEY = 'bank_chatbot_auth_user';

/**
 * Persist login in localStorage for the JWT lifetime (ChatGPT-style):
 * - refresh / new tab in same browser → stay signed in
 * - sign out or expired token → sign in again
 */
function storage(): Storage {
  return localStorage;
}

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
  const token = storage().getItem(TOKEN_KEY);
  if (!isAuthTokenValid(token)) {
    if (token) {
      clearAuthSession();
    }
    return null;
  }
  return token;
}

export function getAuthUser(): EmployeeUser | null {
  const raw = storage().getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as EmployeeUser;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: EmployeeUser): void {
  storage().setItem(TOKEN_KEY, token);
  storage().setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  storage().removeItem(TOKEN_KEY);
  storage().removeItem(USER_KEY);
}

export function getAuthHeaders(): HeadersInit {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
