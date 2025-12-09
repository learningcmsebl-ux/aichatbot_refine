import { useState, useCallback, useEffect } from 'react';
import { chatAPI } from '../services/api';
import { useSession } from './useSession';
import { storage } from '../utils/storage';
import type { Message } from '../types';

export const useChat = () => {
  const { sessionId } = useSession();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load messages from localStorage on mount
  useEffect(() => {
    const savedMessages = storage.loadMessages();
    if (savedMessages.length > 0) {
      setMessages(savedMessages.map((msg: any) => ({
        ...msg,
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      })));
    }
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      const messagesToSave = messages
        .filter(msg => !msg.isStreaming)
        .map(msg => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp?.toISOString(),
        }));
      storage.saveMessages(messagesToSave);
    }
  }, [messages]);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    let fullResponse = '';

    try {
      // Stream response
      for await (const chunk of chatAPI.streamMessage({
        query,
        session_id: sessionId || undefined,
      })) {
        fullResponse += chunk;

        setMessages(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];

          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            // Update existing streaming message
            return updated.map((msg, idx) =>
              idx === updated.length - 1
                ? { ...msg, content: fullResponse }
                : msg
            );
          } else {
            // Add new streaming message
            return [
              ...updated,
              {
                role: 'assistant' as const,
                content: fullResponse,
                timestamp: new Date(),
                isStreaming: true,
              },
            ];
          }
        });
      }

      // Mark streaming as complete
      setMessages(prev =>
        prev.map(msg =>
          msg.isStreaming
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date(),
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, isLoading]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    storage.clear();
  }, []);

  return {
    messages,
    sendMessage,
    isLoading,
    error,
    clearMessages,
  };
};

