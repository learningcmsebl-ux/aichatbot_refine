export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  isStreaming?: boolean;
  error?: boolean;
  sources?: string[];
}

export interface ChatRequest {
  query: string;
  session_id?: string;
  knowledge_base?: string;
  stream?: boolean;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  sources?: string[];
}

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

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: EmployeeUser;
}

export interface AuthConfigResponse {
  auth_enabled: boolean;
}

// ---- Chat Sessions ----
export interface ChatSessionItem {
  id: string;
  session_reference_no: string;
  title: string;
  preview?: string;
  created_at: string;
  updated_at: string;
  archived_at?: string;
}

export interface ChatMessageItem {
  id: number;
  role: 'user' | 'assistant' | 'system';
  message: string;
  source_module?: string;
  created_at: string;
}

export interface ChatSessionWithMessages extends ChatSessionItem {
  messages: ChatMessageItem[];
}

