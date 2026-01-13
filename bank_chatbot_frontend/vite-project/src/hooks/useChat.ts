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
        sources: msg.sources || undefined, // Restore sources if available
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
          sources: msg.sources, // Save sources too
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
    let sources: string[] = [];

    try {
      // Stream response
      for await (const chunk of chatAPI.streamMessage({
        query,
        session_id: sessionId || undefined,
      })) {
        // Check if chunk contains sources marker - handle both formats
        // Backend sends: __SOURCES__{json}__SOURCES__ (double underscores)
        // But sometimes appears as: _SOURCES_{json}_SOURCES_ (single underscores)
        const sourcesPatterns = [
          /__SOURCES__([\s\S]*?)__SOURCES__/,  // Double underscores (standard)
          /_SOURCES_\{([\s\S]*?)\}_SOURCES_/,  // Single underscores (alternative)
        ];
        
        let sourcesFound = false;
        let cleanedChunk = chunk;
        
        for (const pattern of sourcesPatterns) {
          const sourcesMatch = cleanedChunk.match(pattern);
          if (sourcesMatch) {
            sourcesFound = true;
            try {
              let sourcesJson = sourcesMatch[1].trim();
              // If pattern 2 matched, we already have the JSON (between {})
              // If pattern 1 matched, sourcesJson is the JSON string
              const sourcesData = JSON.parse(sourcesJson);
              if (sourcesData.type === 'sources' && Array.isArray(sourcesData.sources)) {
                sources = sourcesData.sources;
                console.log('[SOURCES] Parsed sources from chunk:', sources);
              }
            } catch (e) {
              console.warn('[SOURCES] Failed to parse sources:', e, 'Chunk:', chunk.substring(0, 100));
            }
            // Remove the sources marker from chunk
            cleanedChunk = cleanedChunk.replace(pattern, '').trim();
            break; // Found and processed, no need to check other patterns
          }
        }
        
        // Add cleaned chunk to fullResponse (sources markers removed)
        if (cleanedChunk) {
          fullResponse += cleanedChunk;
        } else if (!sourcesFound) {
          // Only add original chunk if we didn't find sources (to preserve content)
          fullResponse += chunk;
        }

        // Clean up any remaining sources markers from fullResponse before displaying
        // Use more aggressive cleanup to catch all variations
        let displayContent = fullResponse
          .replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '')
          .replace(/_SOURCES_\{[\s\S]*?\}_SOURCES_/g, '')
          .replace(/__SOURCES__/g, '')
          .replace(/_SOURCES_/g, '')
          .replace(/\{[\s\S]*?"type"[\s\S]*?"sources"[\s\S]*?\}/g, '') // Remove any JSON objects that look like sources
          .trim();

        setMessages(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];

          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            // Update existing streaming message
            return updated.map((msg, idx) =>
              idx === updated.length - 1
                ? { ...msg, content: displayContent, sources: sources.length > 0 ? sources : msg.sources }
                : msg
            );
          } else {
            // Add new streaming message
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

      // Mark streaming as complete and ensure sources are set
      // Also check if sources marker is in the final response (clean up any remaining markers)
      const finalSourcesMatch = fullResponse.match(/__SOURCES__([\s\S]*?)__SOURCES__/);
      if (finalSourcesMatch) {
        try {
          const sourcesJson = finalSourcesMatch[1].trim();
          const sourcesData = JSON.parse(sourcesJson);
          if (sourcesData.type === 'sources' && Array.isArray(sourcesData.sources)) {
            sources = sourcesData.sources;
            console.log('[SOURCES] Parsed sources from final response:', sources);
          }
        } catch (e) {
          console.warn('[SOURCES] Failed to parse sources from final response:', e);
        }
        // Remove ALL sources markers from the final response
        fullResponse = fullResponse.replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '').trim();
      }
      
      // Final cleanup: remove any remaining sources markers (safety net)
      // Try multiple patterns to ensure complete removal
      fullResponse = fullResponse
        .replace(/__SOURCES__[\s\S]*?__SOURCES__/g, '')
        .replace(/_SOURCES_\{[\s\S]*?\}_SOURCES_/g, '')
        .replace(/__SOURCES__/g, '')
        .replace(/_SOURCES_/g, '')
        .trim();
      
      // Ensure sources are properly set and content is clean
      setMessages(prev =>
        prev.map(msg =>
          msg.isStreaming
            ? { 
                ...msg, 
                isStreaming: false, 
                content: fullResponse, 
                sources: sources.length > 0 ? sources : undefined 
              }
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

