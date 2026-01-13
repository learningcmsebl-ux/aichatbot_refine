export interface PerformanceMetrics {
  period_days: number;
  overall: {
    total_conversations: number;
    total_answered: number;
    total_unanswered: number;
    overall_answer_rate: number;
    avg_response_time_ms: number;
  };
  daily_metrics: Array<{
    date: string;
    total_conversations: number;
    answered_count: number;
    unanswered_count: number;
    avg_response_time_ms: number | null;
    answer_rate: number;
  }>;
}

export interface Question {
  question: string;
  normalized: string;
  total_asked: number;
  answered_count: number;
  unanswered_count: number;
  answer_rate: number;
  last_asked: string;
}

export interface Conversation {
  id: number;
  session_id: string;
  user_message: string;
  assistant_response: string;
  is_answered: boolean;
  knowledge_base: string | null;
  response_time_ms: number | null;
  client_ip: string | null;
  created_at: string;
  sources?: string[];
}

export interface HealthStatus {
  status: string;
  service: string;
  components?: {
    lightrag?: {
      status: string;
      details?: any;
    };
    redis?: {
      status: string;
    };
    postgresql?: {
      status: string;
    };
  };
}

