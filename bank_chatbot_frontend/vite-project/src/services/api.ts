import type { ChatRequest, ChatResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001/api';

export class ChatAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...request,
        stream: false,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! status: ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  async *streamMessage(request: ChatRequest): AsyncGenerator<string, void, unknown> {
    const response = await fetch(`${this.baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...request,
        stream: true,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! status: ${response.status}: ${errorText}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported in this browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          if (buffer) {
            yield buffer;
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim()) {
            yield line;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async getHistory(sessionId: string, limit: number = 50) {
    const response = await fetch(`${this.baseUrl}/chat/history/${sessionId}?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Failed to get history: ${response.statusText}`);
    }
    return response.json();
  }

  async clearHistory(sessionId: string) {
    const response = await fetch(`${this.baseUrl}/chat/history/${sessionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Failed to clear history: ${response.statusText}`);
    }
    return response.json();
  }
}

export const chatAPI = new ChatAPI();

