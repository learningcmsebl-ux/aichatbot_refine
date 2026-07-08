export interface EmployeeUser {
  username: string;
  employee_id?: string;
  full_name?: string;
  email?: string;
  department?: string;
  designation?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AuthConfigResponse {
  auth_enabled: boolean;
  default_password_hint?: string;
}

export interface LoginResponse {
  access_token: string;
  expires_in: number;
  user: EmployeeUser;
  must_change_password?: boolean;
}

export interface MeResponse {
  user: EmployeeUser;
  must_change_password?: boolean;
}

export interface PortalUserSummary {
  username: string;
  employee_id?: string;
  full_name?: string;
  email?: string;
  lead_role: string;
  must_change_password: boolean;
  provisioned_by: string;
  provisioned_at: string;
}

export interface PortalUserListResponse {
  items: PortalUserSummary[];
  total: number;
}

export interface ProvisionPortalUserRequest {
  employee_id: string;
  lead_role?: string;
}

export interface DirectoryUserPreview {
  username: string;
  employee_id: string;
  full_name?: string;
  email?: string;
  department?: string;
  designation?: string;
  source: string;
  already_registered: boolean;
}

export interface ProvisionPortalUserResponse {
  user: PortalUserSummary;
  message: string;
  temporary_password_hint: string;
}

export interface LeadSummary {
  lead_reference_no: string;
  customer_name: string;
  customer_mobile?: string;
  customer_email?: string;
  product_type: string;
  product_type_label: string;
  status: string;
  status_label: string;
  preferred_branch?: string;
  assigned_to_user_id?: string;
  created_by_employee_id: string;
  created_by_name?: string;
  created_at: string;
  updated_at: string;
}

export interface LeadDetail extends LeadSummary {
  preferred_contact_time?: string;
  customer_location?: string;
  remarks?: string;
  created_by_department?: string;
  created_by_branch?: string;
  created_by_email?: string;
  closed_at?: string;
  chat_session_id?: string;
  permissions?: LeadDetailPermissions;
}

export interface LeadListResponse {
  items: LeadSummary[];
  total: number;
}

export interface LeadPermissions {
  view_all: boolean;
  assign: boolean;
  export: boolean;
  manage_roles: boolean;
  update_status: boolean;
  view_assigned_queue: boolean;
}

export interface LeadMyRolesResponse {
  roles: string[];
  permissions: LeadPermissions;
}

export interface LeadDetailPermissions {
  can_view: boolean;
  can_update_status: boolean;
  can_assign: boolean;
  can_add_feedback: boolean;
  can_delete: boolean;
}

export interface LeadDashboardStats {
  total: number;
  by_status: Record<string, number>;
  by_product: Record<string, number>;
  pending_assigned: number;
}

export interface LeadStatusHistory {
  old_status?: string;
  new_status: string;
  changed_by: string;
  changed_at: string;
  note?: string;
}

export interface LeadFeedback {
  id: number;
  feedback_text: string;
  feedback_by: string;
  feedback_to_employee_id: string;
  created_at: string;
}

export const LEAD_STATUSES = [
  'submitted',
  'assigned',
  'contacted',
  'interested',
  'follow_up_required',
  'converted',
  'not_interested',
  'rejected',
  'closed',
] as const;

export const PRODUCT_TYPES = [
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'personal_loan', label: 'Personal Loan' },
  { value: 'home_loan', label: 'Home Loan' },
  { value: 'auto_loan', label: 'Auto Loan' },
  { value: 'sme_loan', label: 'SME Loan' },
  { value: 'deposit_account', label: 'Deposit Account' },
  { value: 'dps', label: 'DPS' },
  { value: 'fdr', label: 'FDR' },
  { value: 'debit_card', label: 'Debit Card' },
  { value: 'payroll_banking', label: 'Payroll Banking' },
  { value: 'other', label: 'Other' },
];
