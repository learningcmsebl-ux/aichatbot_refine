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

