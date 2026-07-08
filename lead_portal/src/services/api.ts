import type {
  LeadDetail,
  LeadFeedback,
  LeadListResponse,
  LeadMyRolesResponse,
  LeadDashboardStats,
  LeadStatusHistory,
  LeadSummary,
  PortalUserListResponse,
  ProvisionPortalUserRequest,
  ProvisionPortalUserResponse,
  DirectoryUserPreview,
} from '../types';
import { getAuthHeaders } from '../utils/authStorage';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch { /* ignore */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface LeadFilters {
  status?: string;
  product_type?: string;
  branch?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const LeadsAPI = {
  list(filters: LeadFilters = {}): Promise<LeadListResponse> {
    return request(`/leads${qs(filters as Record<string, string | number | undefined>)}`);
  },
  mySubmitted(limit = 100): Promise<LeadListResponse> {
    return request(`/leads/my-submitted?limit=${limit}`);
  },
  assigned(limit = 100): Promise<LeadListResponse> {
    return request(`/leads/assigned?limit=${limit}`);
  },
  search(q: string): Promise<LeadListResponse> {
    return request(`/leads/search?q=${encodeURIComponent(q)}`);
  },
  get(ref: string): Promise<LeadDetail> {
    return request(`/leads/${encodeURIComponent(ref)}`);
  },
  myRoles(): Promise<LeadMyRolesResponse> {
    return request('/leads/me/roles');
  },
  stats(): Promise<LeadDashboardStats> {
    return request('/leads/stats');
  },
  updateStatus(ref: string, status: string, note?: string): Promise<LeadDetail> {
    return request(`/leads/${encodeURIComponent(ref)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note }),
    });
  },
  assign(ref: string, assigned_to_user_id: string, note?: string): Promise<LeadDetail> {
    return request(`/leads/${encodeURIComponent(ref)}/assign`, {
      method: 'PATCH',
      body: JSON.stringify({ assigned_to_user_id, note }),
    });
  },
  addFeedback(ref: string, feedback_text: string, feedback_to_employee_id: string): Promise<LeadFeedback> {
    return request(`/leads/${encodeURIComponent(ref)}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback_text, feedback_to_employee_id }),
    });
  },
  statusHistory(ref: string): Promise<LeadStatusHistory[]> {
    return request(`/leads/${encodeURIComponent(ref)}/status-history`);
  },
  feedbackList(ref: string): Promise<LeadFeedback[]> {
    return request(`/leads/${encodeURIComponent(ref)}/feedback`);
  },
  exportCsv(filters: LeadFilters = {}): string {
    const params = qs(filters as Record<string, string | number | undefined>);
    return `${API_BASE}/leads/export.csv${params}`;
  },
};

export const PortalUsersAPI = {
  list(limit = 200): Promise<PortalUserListResponse> {
    return request(`/portal-users?limit=${limit}`);
  },
  lookup(employeeId: string): Promise<DirectoryUserPreview> {
    return request(`/portal-users/lookup?employee_id=${encodeURIComponent(employeeId)}`);
  },
  register(body: ProvisionPortalUserRequest): Promise<ProvisionPortalUserResponse> {
    return request('/portal-users', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },
};

export type { LeadSummary };
