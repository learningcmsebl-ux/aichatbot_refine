import axios from 'axios';
import type { PerformanceMetrics, Question, Conversation, HealthStatus } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const analyticsAPI = {
  async getPerformanceMetrics(days: number = 30): Promise<PerformanceMetrics> {
    const response = await api.get<PerformanceMetrics>('/analytics/performance', {
      params: { days },
    });
    return response.data;
  },

  async getMostAskedQuestions(limit: number = 20): Promise<Question[]> {
    const response = await api.get<{ questions: Question[] }>('/analytics/most-asked', {
      params: { limit },
    });
    return response.data.questions;
  },

  async getUnansweredQuestions(limit: number = 50): Promise<Question[]> {
    const response = await api.get<{ questions: Question[] }>('/analytics/unanswered', {
      params: { limit },
    });
    return response.data.questions;
  },

  async getConversationHistory(sessionId?: string, limit: number = 100): Promise<Conversation[]> {
    const response = await api.get<{ conversations: Conversation[] }>('/analytics/history', {
      params: { session_id: sessionId, limit },
    });
    return response.data.conversations;
  },

  async getHealthStatus(): Promise<HealthStatus> {
    const response = await api.get<HealthStatus>('/health/detailed');
    return response.data;
  },
};

export default api;

