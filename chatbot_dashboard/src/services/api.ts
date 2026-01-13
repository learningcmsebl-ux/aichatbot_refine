import axios from 'axios';
import type { PerformanceMetrics, Question, Conversation, HealthStatus } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // Increased timeout to 60 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add retry interceptor for connection errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    
    // Retry on network errors or connection resets
    if (
      (!config || !config.__isRetryRequest) &&
      (error.code === 'ECONNRESET' || 
       error.code === 'ECONNABORTED' ||
       error.message?.includes('timeout') ||
       error.message?.includes('Network Error'))
    ) {
      config.__isRetryRequest = true;
      config.__retryCount = config.__retryCount || 0;
      
      if (config.__retryCount < 2) { // Retry up to 2 times
        config.__retryCount += 1;
        console.log(`Retrying request (${config.__retryCount}/2):`, config.url);
        
        // Wait before retrying (exponential backoff)
        await new Promise(resolve => setTimeout(resolve, 1000 * config.__retryCount));
        
        return api(config);
      }
    }
    
    return Promise.reject(error);
  }
);

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
    console.log(`[API] Fetching conversation history (sessionId: ${sessionId || 'all'}, limit: ${limit})`);
    try {
      const response = await api.get<{ conversations: Conversation[] }>('/analytics/history', {
        params: { session_id: sessionId, limit },
      });
      console.log(`[API] Received ${response.data.conversations.length} conversations`);
      return response.data.conversations;
    } catch (error: any) {
      console.error('[API] Error fetching conversation history:', error);
      console.error('[API] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });
      throw error;
    }
  },

  async getHealthStatus(): Promise<HealthStatus> {
    const response = await api.get<HealthStatus>('/health/detailed');
    return response.data;
  },
};

export default api;

