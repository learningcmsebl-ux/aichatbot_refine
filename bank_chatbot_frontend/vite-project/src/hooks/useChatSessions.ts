import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatSessionItem, ChatSessionWithMessages, ChatMessageItem } from '../types';
import { sessionsAPI } from '../services/api';

export interface UseChatSessionsReturn {
  sessions: ChatSessionItem[];
  activeSessionId: string | null;
  activeMessages: ChatMessageItem[];
  loading: boolean;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  selectSession: (id: string) => Promise<void>;
  newChat: () => void;
  renameSession: (id: string, title: string) => Promise<void>;
  archiveSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  updateActiveMessages: (msgs: ChatMessageItem[]) => void;
  appendActiveMessage: (msg: ChatMessageItem) => void;
  /** Call when a chat turn completes so the sidebar title updates */
  onTurnComplete: (sessionRefNo: string) => Promise<void>;
}

export function useChatSessions(isAuthenticated: boolean): UseChatSessionsReturn {
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessages, setActiveMessages] = useState<ChatMessageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSessions = useCallback(async (q?: string) => {
    if (!isAuthenticated) { setSessions([]); return; }
    try {
      const data = q ? await sessionsAPI.search(q) : await sessionsAPI.list();
      setSessions(data);
    } catch (e) {
      console.warn('Failed to load sessions', e);
    }
  }, [isAuthenticated]);

  // Initial load
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Debounced search
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      loadSessions(searchQuery || undefined);
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [searchQuery, loadSessions]);

  const selectSession = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const data: ChatSessionWithMessages = await sessionsAPI.get(id);
      setActiveSessionId(id);
      setActiveMessages(data.messages);
    } catch (e) {
      console.warn('Failed to load session', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const newChat = useCallback(() => {
    setActiveSessionId(null);
    setActiveMessages([]);
  }, []);

  const renameSession = useCallback(async (id: string, title: string) => {
    await sessionsAPI.rename(id, title);
    await loadSessions(searchQuery || undefined);
  }, [loadSessions, searchQuery]);

  const archiveSession = useCallback(async (id: string) => {
    await sessionsAPI.archive(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setActiveMessages([]);
    }
    await loadSessions(searchQuery || undefined);
  }, [activeSessionId, loadSessions, searchQuery]);

  const deleteSession = useCallback(async (id: string) => {
    await sessionsAPI.delete(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setActiveMessages([]);
    }
    await loadSessions(searchQuery || undefined);
  }, [activeSessionId, loadSessions, searchQuery]);

  const refreshSessions = useCallback(() => loadSessions(searchQuery || undefined), [loadSessions, searchQuery]);

  const updateActiveMessages = useCallback((msgs: ChatMessageItem[]) => {
    setActiveMessages(msgs);
  }, []);

  const appendActiveMessage = useCallback((msg: ChatMessageItem) => {
    setActiveMessages(prev => [...prev, msg]);
  }, []);

  /**
   * After a chat turn completes: refresh the sidebar so the new title + preview appear.
   * Does NOT set activeSessionId — that would trigger ChatInterface to reload messages
   * from the server (which would be empty mid-stream) and wipe the live chat.
   */
  const onTurnComplete = useCallback(async (_sessionRefNo: string) => {
    await loadSessions(searchQuery || undefined);
  }, [loadSessions, searchQuery]);

  return {
    sessions,
    activeSessionId,
    activeMessages,
    loading,
    searchQuery,
    setSearchQuery,
    selectSession,
    newChat,
    renameSession,
    archiveSession,
    deleteSession,
    refreshSessions,
    updateActiveMessages,
    appendActiveMessage,
    onTurnComplete,
  };
}
