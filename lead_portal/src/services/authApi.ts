import type { ChangePasswordRequest } from '../types';
import { getAuthHeaders } from '../utils/authStorage';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const AuthAPI = {
  async changePassword(body: ChangePasswordRequest): Promise<void> {
    const res = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail = 'Password change failed';
      try {
        const data = await res.json();
        if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
  },
};

export type { ChangePasswordRequest };
