import { useState, useCallback, useRef } from 'react';
import { chatAPI } from '../services/api';
import type { Message } from '../types';

function generateSessionRef(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

export const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // sessionRef is the backend session_reference_no (also used as session_id by orchestrator)
  const sessionRefRef = useRef<string | null>(null);
  const [sessionRef, setSessionRefState] = useState<string | null>(null);

  /**
   * Called by ChatInterface when a sidebar session is selected, or
   * when "New Chat" resets the session.
   */
  const setSessionRef = useCallback((ref: string | null, initialMessages: Message[]) => {
    sessionRefRef.current = ref;
    setSessionRefState(ref);
    setMessages(initialMessages);
    setError(null);
  }, []);

  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // Lazily create a session ref if none exists (new chat, first message)
    if (!sessionRefRef.current) {
      const newRef = generateSessionRef();
      sessionRefRef.current = newRef;
      setSessionRefState(newRef);
    }
    const currentRef = sessionRefRef.current!;

    const userMessage: Message = {
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    let fullResponse = '';
    let sources: string[] = [];

    try {
      for await (const chunk of chatAPI.streamMessage({
        query,
        session_id: currentRef,
      })) {
        const sourcesPatterns = [
          /__SOURCES__([\s\S]*?)__SOURCES__/,
          /_SOURCES_\{([\s\S]*?)\}_SOURCES_/,
        ];

        let sourcesFound = false;
        let cleanedChunk = chunk;

        for (const pattern of sourcesPatterns) {
          const sourcesMatch = cleanedChunk.match(pattern);
          if (sourcesMatch) {
            sourcesFound = true;
            try {
              const sourcesData = JSON.parse(sourcesMatch[1].trim());
              if (sourcesData.type === 'sources' && Array.isArray(sourcesData.sources)) {
                sources = sourcesData.sources;
              }
            } catch {
              // ignore parse error
            }
            cleanedChunk = cleanedChunk.replace(pattern, '').trim();
            break;
          }
        }

        if (cleanedChunk) {
          fullResponse += cleanedChunk;
        } else if (!sourcesFound) {
          fullResponse += chunk;
        }

        let displayContent = fullResponse
          .replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '')
          .replace(/_SOURCES_\{[\s\S]*?\}_SOURCES_/g, '')
          .replace(/__SOURCES__/g, '')
          .replace(/_SOURCES_/g, '')
          .trim();

        setMessages(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            return updated.map((msg, idx) =>
              idx === updated.length - 1
                ? { ...msg, content: displayContent, sources: sources.length > 0 ? sources : msg.sources }
                : msg
            );
          } else {
            return [
              ...updated,
              {
                role: 'assistant' as const,
                content: displayContent,
                timestamp: new Date(),
                isStreaming: true,
                sources: sources.length > 0 ? sources : undefined,
              },
            ];
          }
        });
      }

      // Final cleanup
      const finalSourcesMatch = fullResponse.match(/__SOURCES__([\s\S]*?)__SOURCES__/);
      if (finalSourcesMatch) {
        try {
          const sourcesData = JSON.parse(finalSourcesMatch[1].trim());
          if (sourcesData.type === 'sources' && Array.isArray(sourcesData.sources)) {
            sources = sourcesData.sources;
          }
        } catch { /* ignore */ }
        fullResponse = fullResponse.replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '').trim();
      }

      fullResponse = fullResponse
        .replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '')
        .replace(/_SOURCES_\{[\s\S]*?\}_SOURCES_/g, '')
        .replace(/__SOURCES__/g, '')
        .replace(/_SOURCES_/g, '')
        .trim();

      setMessages(prev =>
        prev.map(msg =>
          msg.isStreaming
            ? { ...msg, isStreaming: false, content: fullResponse, sources: sources.length > 0 ? sources : undefined }
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
  }, [isLoading]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    sessionRefRef.current = null;
    setSessionRefState(null);
  }, []);

  /** Always returns the current session reference (no stale-closure issue). */
  const getSessionRef = useCallback(() => sessionRefRef.current, []);

  return {
    messages,
    sendMessage,
    isLoading,
    error,
    clearMessages,
    sessionRef,
    setSessionRef,
    getSessionRef,
  };
};
