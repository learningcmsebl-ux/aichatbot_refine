import React, { useState } from 'react';
import type { Message } from '../types';

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;
  const hasError = message.error;
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (isUser) {
    return (
      <div
        className="message-enter max-w-full group"
        style={{ animation: 'fadeIn 0.3s' }}
      >
        <div
          className="bg-[#d1e8ff] text-[#111827] self-end rounded-2xl px-4 py-3 my-2 whitespace-pre-line relative hover:shadow-md transition-shadow"
          style={{
            backgroundColor: '#d1e8ff',
            color: '#111827',
            alignSelf: 'flex-end',
            borderBottomRightRadius: '4px',
            whiteSpace: 'pre-line',
            padding: '12px 16px',
            borderRadius: '14px',
            margin: '8px 0',
            maxWidth: '85%',
            wordWrap: 'break-word',
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
            transition: 'box-shadow 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
          }}
        >
          {message.content}
          {message.timestamp && (
            <div
              className="text-xs mt-1.5 opacity-70 text-right"
              style={{ fontSize: '11px', color: '#6b7280' }}
            >
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className="message-enter max-w-full relative group"
      style={{ animation: 'fadeIn 0.3s' }}
    >
      <div
        className={`${
          hasError
            ? 'bg-red-50 text-red-800 border border-red-200'
            : 'bg-[#f3f4f6] text-[#111827]'
        } self-start rounded-2xl px-4 py-4 my-3 whitespace-pre-line relative hover:shadow-md transition-all`}
        style={{
          backgroundColor: hasError ? '#fef2f2' : '#f3f4f6',
          color: hasError ? '#991b1b' : '#111827',
          alignSelf: 'flex-start',
          whiteSpace: 'pre-line',
          padding: '16px 18px 16px 88px',
          borderRadius: '14px',
          margin: '12px 0',
          maxWidth: '85%',
          wordWrap: 'break-word',
          borderLeft: isStreaming ? '3px solid #003366' : undefined,
          boxShadow: hasError
            ? '0 1px 3px rgba(239, 68, 68, 0.1)'
            : '0 1px 2px rgba(0, 0, 0, 0.05)',
          transition: 'box-shadow 0.2s ease, transform 0.2s ease',
        }}
        onMouseEnter={(e) => {
          if (!hasError) {
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = hasError
            ? '0 1px 3px rgba(239, 68, 68, 0.1)'
            : '0 1px 2px rgba(0, 0, 0, 0.05)';
        }}
      >
        {/* Avatar for assistant messages */}
        {!hasError && (
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
        )}
        <div className="whitespace-pre-wrap break-words">
          {message.content}
          {isStreaming && (
            <span
              className="inline-block w-2 h-4 bg-[#003366] ml-1.5 rounded-sm animate-pulse"
              style={{
                verticalAlign: 'middle',
                animation: 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
              }}
            />
          )}
        </div>
        {message.timestamp && (
          <div
            className="text-xs mt-2 opacity-70"
            style={{ fontSize: '11px', color: '#6b7280' }}
          >
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        )}
        {/* Copy button - appears on hover */}
        {!isStreaming && !hasError && message.content && (
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md hover:bg-gray-200 active:bg-gray-300"
            style={{
              transition: 'opacity 0.2s ease, background-color 0.2s ease',
            }}
            title="Copy message"
            aria-label="Copy message"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-gray-600"
            >
              {copied ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                />
              ) : (
                <>
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </>
              )}
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};
