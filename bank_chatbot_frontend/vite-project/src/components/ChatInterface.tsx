import React, { useCallback, useEffect, useRef } from 'react';
import { Header } from './Header';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useChat } from '../hooks/useChat';
import type { UseChatSessionsReturn } from '../hooks/useChatSessions';
import './ChatInterface.css';

interface ChatInterfaceProps {
  chatSessions: UseChatSessionsReturn;
  onToggleSidebar: () => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ chatSessions, onToggleSidebar }) => {
  const {
    activeSessionId,
    activeMessages,
    onTurnComplete,
  } = chatSessions;

  const { messages, sendMessage, isLoading, error, setSessionRef, getSessionRef } = useChat();

  // Track whether the current activeSessionId was set by a sidebar click vs onTurnComplete.
  // We only want to reload messages when the user explicitly selects a session.
  const prevSidebarSessionId = useRef<string | null>(null);

  useEffect(() => {
    if (activeSessionId && activeSessionId !== prevSidebarSessionId.current) {
      prevSidebarSessionId.current = activeSessionId;
      const sess = chatSessions.sessions.find(s => s.id === activeSessionId);
      if (sess && activeMessages.length > 0) {
        const mapped = activeMessages.map(m => ({
          role: m.role as 'user' | 'assistant',
          content: m.message,
          timestamp: new Date(m.created_at),
          sources: undefined,
          isStreaming: false,
        }));
        setSessionRef(sess.session_reference_no, mapped);
      } else if (sess && activeMessages.length === 0) {
        setSessionRef(sess.session_reference_no, []);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, activeMessages]);

  // When "New Chat" is clicked (activeSessionId goes null), clear the chat window
  const prevActiveIdRef = useRef(activeSessionId);
  useEffect(() => {
    if (prevActiveIdRef.current !== null && activeSessionId === null) {
      setSessionRef(null, []);
      prevSidebarSessionId.current = null;
    }
    prevActiveIdRef.current = activeSessionId;
  }, [activeSessionId, setSessionRef]);

  const handleSend = useCallback(async (query: string) => {
    await sendMessage(query);
    const currentRef = getSessionRef();
    if (currentRef) {
      await onTurnComplete(currentRef);
    }
  }, [sendMessage, getSessionRef, onTurnComplete]);

  return (
    <div className="chat-shell">
      {/* Header includes the hamburger (mobile) and the DIA avatar */}
      <Header onToggleSidebar={onToggleSidebar} />

      <main className="chat-main">
        {/* Scrollable messages area */}
        <div className="messages-container">
          <MessageList messages={messages} isLoading={isLoading} />
        </div>

        {/* Error strip — above input bar, outside scroll area */}
        {error && (
          <div className="chat-error-strip">
            {error}
          </div>
        )}

        {/* Sticky input bar */}
        <footer className="chat-input-bar">
          <div className="input-viewport">
            <InputArea onSend={handleSend} disabled={isLoading} />
          </div>
        </footer>
      </main>
    </div>
  );
};
