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
        className="message-enter max-w-full group flex justify-end"
        style={{ animation: 'fadeIn 0.3s' }}
      >
        <div
          className="msg-bubble user"
          style={{
            background: 'linear-gradient(135deg, #0057a6 0%, #004080 100%)',  /* Subtle gradient - EBL blue */
            color: '#ffffff',
            whiteSpace: 'pre-line',
            padding: '12px 16px',  /* More padding for bubble feel */
            borderRadius: '12px 12px 4px 12px',  /* Less rounded, more bubble-like with slight tail effect */
            marginBottom: '8px',
            fontSize: '15px',  /* Slightly larger */
            lineHeight: '1.5',
            maxWidth: '75%',  /* Slightly wider */
            marginLeft: 'auto',
            wordWrap: 'break-word',
            boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.15)',  /* Subtle shadow for depth */
            transition: 'all 0.2s ease',
            border: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = '0px 3px 8px rgba(0, 0, 0, 0.2)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = '0px 2px 6px rgba(0, 0, 0, 0.15)';
          }}
        >
          <div style={{ lineHeight: '1.5' }}>
            {message.content}
          </div>
          {message.timestamp && (
            <div
              className="text-xs mt-1.5 opacity-80 text-right"
              style={{ 
                fontSize: '10px',  /* Smaller than main text */
                color: 'rgba(255, 255, 255, 0.65)',  /* Lighter/more transparent */
                marginTop: '4px',
                fontWeight: 400,
                letterSpacing: '0.3px'
              }}
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
        className={`msg-bubble bot ${
          hasError
            ? 'bg-red-50 text-red-800 border border-red-200'
            : ''
        }`}
        style={{
          backgroundColor: hasError ? '#fef2f2' : '#ffffff',
          color: hasError ? '#991b1b' : '#111827',
          whiteSpace: 'pre-line',
          padding: '10px 14px',
          borderRadius: '18px',
          marginBottom: '10px',
          fontSize: '14px',
          lineHeight: '1.5',
          maxWidth: '70%',
          wordWrap: 'break-word',
          boxShadow: hasError
            ? '0 1px 3px rgba(239, 68, 68, 0.1)'
            : '0 2px 6px rgba(15, 23, 42, 0.06)',
          transition: 'all 0.2s ease',
          borderLeft: isStreaming ? '3px solid #10a37f' : undefined,
        }}
        onMouseEnter={(e) => {
          if (!hasError) {
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = hasError
            ? '0 1px 3px rgba(239, 68, 68, 0.1)'
            : '0 2px 6px rgba(15, 23, 42, 0.06)';
        }}
      >
        <div style={{ lineHeight: '1.5' }}>
          {message.content}
        </div>
        {isStreaming && (
          <span
            className="inline-block w-2 h-4 bg-[#10a37f] ml-1.5 rounded-sm animate-pulse"
            style={{
              verticalAlign: 'middle',
              animation: 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
          />
        )}
        {message.timestamp && !isStreaming && (
          <div
            className="text-xs mt-1 opacity-65 text-left font-normal tracking-wide"
            style={{ 
              fontSize: '10px', 
              color: 'rgba(53, 55, 64, 0.65)', 
              marginTop: '4px' 
            }}
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
