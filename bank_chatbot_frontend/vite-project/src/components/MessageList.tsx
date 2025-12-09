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

  // Smooth scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      const timer = setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'end',
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [messages, isLoading]);

  // Auto-scroll during streaming
  useEffect(() => {
    if (isLoading && containerRef.current) {
      const container = containerRef.current;
      const shouldScroll =
        container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      
      if (shouldScroll) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [messages, isLoading]);

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto p-5 rounded-lg mb-2.5 flex flex-col gap-4 min-h-0 scroll-smooth"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '10px 20px 20px 20px',
        backgroundColor: '#f9fafb',
        borderRadius: '10px',
        marginBottom: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '15px',
        minHeight: 0,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        color: '#1f2937',
        lineHeight: 1.55,
        fontSize: '16px',
        letterSpacing: '0.1px',
        scrollBehavior: 'smooth',
      }}
    >
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <div className="text-center">
            <div
              className="text-4xl mb-4 animate-bounce"
              style={{ animation: 'bounce 2s infinite' }}
            >
              👋
            </div>
            <p className="text-lg mb-2 font-medium">Welcome to EBL DIA 2.0!</p>
            <p className="text-sm text-gray-400">
              Start a conversation by typing a message below.
            </p>
          </div>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <MessageBubble key={`${message.role}-${index}-${message.timestamp?.getTime()}`} message={message} />
          ))}
          {isLoading && (
            <div className="message-enter self-start">
              <div
                className="bg-[#f3f4f6] text-[#111827] self-start rounded-2xl px-4 py-4 my-3 whitespace-pre-line relative"
                style={{
                  backgroundColor: '#f3f4f6',
                  color: '#111827',
                  alignSelf: 'flex-start',
                  whiteSpace: 'pre-line',
                  padding: '16px 18px 16px 88px',
                  borderRadius: '14px',
                  margin: '12px 0',
                  borderLeft: '3px solid #003366',
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                }}
              >
                <div
                  className="absolute left-4 top-4 rounded-xl bg-cover bg-center border-2 border-gray-200 shadow-sm"
                  style={{
                    left: '18px',
                    top: '18px',
                    width: '52px',
                    height: '52px',
                    borderRadius: '12px',
                    backgroundImage: 'url(/dia-avatar.png)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center 20%',
                    backgroundRepeat: 'no-repeat',
                    border: '2px solid #e5e7eb',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                  }}
                />
                <div className="flex items-center gap-1.5 py-2">
                  <div className="thinking-dot"></div>
                  <div className="thinking-dot"></div>
                  <div className="thinking-dot"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} style={{ height: '1px' }} />
        </>
      )}
    </div>
  );
};
