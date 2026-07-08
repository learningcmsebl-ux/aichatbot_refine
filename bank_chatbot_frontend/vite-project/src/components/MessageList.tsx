import React, { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import type { Message } from '../types';

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isLoading }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastMessageCountRef = useRef<number>(0);

  const isNearBottom = () => {
    if (!containerRef.current) return true;
    const c = containerRef.current;
    return c.scrollHeight - c.scrollTop - c.clientHeight < 150;
  };

  const scrollToBottom = (smooth = false) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: smooth ? 'smooth' : 'auto',
      block: 'end',
    });
  };

  // Smooth scroll on new message
  useEffect(() => {
    const count = messages.length;
    if (count > lastMessageCountRef.current) {
      scrollToBottom(true);
    }
    lastMessageCountRef.current = count;
  }, [messages.length]);

  // Throttled instant scroll during streaming
  useEffect(() => {
    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);

    const lastMsg = messages[messages.length - 1];
    const streaming = lastMsg?.isStreaming || isLoading;

    if (streaming && isNearBottom()) {
      scrollTimeoutRef.current = setTimeout(() => {
        requestAnimationFrame(() => scrollToBottom(false));
      }, 33);
    }

    return () => {
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    };
  }, [messages, isLoading]);

  return (
    /* Full-width scrollable area — containerRef used for scroll detection */
    <div ref={containerRef} className="msg-scroll-area">
      {/* Max-width centered content */}
      <div className="message-viewport">
        {messages.length === 0 ? (
          <div className="welcome-state">
            <div className="welcome-card">
              <span className="welcome-icon">👋</span>
              <h2>Welcome to EBL DIA 2.0!</h2>
              <p>Your AI-powered banking assistant is ready.<br />Type a message below to get started.</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message, index) => (
              <MessageBubble
                key={`${message.role}-${index}-${message.timestamp?.getTime()}`}
                message={message}
              />
            ))}

            {/* Typing indicator — only when no streaming message exists */}
            {isLoading && !messages.some(m => m.isStreaming) && (
              <div className="msg-loading-row message-enter">
                <div className="msg-bot-avatar-wrap">
                  <div className="msg-bot-avatar">
                    <img src="/dia-avatar.png" alt="DIA" />
                  </div>
                </div>
                <div className="msg-loading-bubble">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '2px 0' }}>
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} style={{ height: '1px' }} />
          </>
        )}
      </div>
    </div>
  );
};
