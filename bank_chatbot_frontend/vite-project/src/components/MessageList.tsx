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

  // Check if user is near bottom (within 150px)
  const isNearBottom = () => {
    if (!containerRef.current) return true;
    const container = containerRef.current;
    const threshold = 150;
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
  };

  // Scroll to bottom - use instant scroll during streaming, smooth for new messages
  const scrollToBottom = (smooth: boolean = false) => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'end',
      });
    }
  };

  // Handle new message added (not streaming update)
  useEffect(() => {
    const currentMessageCount = messages.length;
    const isNewMessage = currentMessageCount > lastMessageCountRef.current;
    lastMessageCountRef.current = currentMessageCount;

    if (isNewMessage) {
      // New message added - use smooth scroll
      scrollToBottom(true);
    }
  }, [messages.length]);

  // Auto-scroll during streaming (instant, no smooth animation)
  // Throttled to prevent excessive scrolling on every chunk
  useEffect(() => {
    // Clear any pending scroll
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // Only auto-scroll if user is near bottom and content is streaming
    const lastMessage = messages[messages.length - 1];
    const isStreaming = lastMessage?.isStreaming || isLoading;
    
    if (isStreaming) {
      // Check if near bottom
      const nearBottom = isNearBottom();
      
      if (nearBottom) {
        // Throttle scroll updates to ~30fps during streaming (every 33ms)
        scrollTimeoutRef.current = setTimeout(() => {
          requestAnimationFrame(() => {
            scrollToBottom(false); // Instant scroll during streaming
          });
        }, 33);
      }
    }

    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, [messages, isLoading]);

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto rounded-lg mb-2.5 flex flex-col min-h-0 scroll-smooth"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        backgroundColor: '#ffffff',
        borderRadius: '10px',
        marginBottom: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '0px',
        minHeight: 0,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        color: '#353740',
        lineHeight: 1.5,
        fontSize: '15px',
        letterSpacing: '0',
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
          {/* Only show loading indicator if there's no streaming message already */}
          {isLoading && !messages.some(msg => msg.isStreaming) && (
            <div className="message-enter flex items-start gap-3">
              {/* Avatar on the left side */}
              <div
                className="flex-shrink-0 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #0d9375 0%, #0a7a5f 100%)',
                  boxShadow: '0 2px 8px rgba(13, 147, 117, 0.3)',
                  flexShrink: 0,
                  marginTop: '4px',
                }}
              >
                <div
                  className="rounded-full bg-cover bg-center"
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    backgroundImage: 'url(/dia-avatar.png)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center 20%',
                    backgroundRepeat: 'no-repeat',
                    border: '2px solid rgba(255, 255, 255, 0.3)',
                  }}
                />
              </div>
              <div
                className="bg-[#f7f7f8] text-[#353740] rounded-2xl px-4 py-3 my-1 whitespace-pre-line relative flex-1"
                style={{
                  backgroundColor: '#f7f7f8',
                  color: '#353740',
                  whiteSpace: 'pre-line',
                  padding: '12px 16px',
                  borderRadius: '18px',
                  margin: '4px 0',
                  maxWidth: 'calc(85% - 44px)',
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                  borderLeft: '3px solid #10a37f',
                }}
              >
                <div className="flex items-center gap-1.5 py-1">
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

