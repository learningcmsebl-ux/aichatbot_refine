import React, { useState } from 'react';
import type { Message } from '../types';
import { renderMessageContent } from '../utils/linkifyContent';
interface MessageBubbleProps {
  message: Message;
}

/**
 * Strips decorative separator lines (===, ---, ~~~, ***) that sometimes appear
 * in raw LLM output. Also collapses 3+ blank lines to 2.
 */
function cleanBotContent(content: string): string {
  return content
    .split('\n')
    .filter(line => !/^[=\-~*_]{3,}\s*$/.test(line.trim()))
    .filter(line => !/^\s*Profile:\s*/i.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
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
    } catch {
      /* ignore */
    }
  };

  const formattedTime = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  /* ------------------------------------------------------------------ */
  /*  User message                                                        */
  /* ------------------------------------------------------------------ */
  if (isUser) {
    return (
      <div className="msg-row msg-row--user">
        <div
          className="msg-bubble user"
          style={{ whiteSpace: 'pre-wrap' }}
        >
          {message.content}
          {formattedTime && (
            <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.55)', marginTop: '5px', textAlign: 'right', fontWeight: 400 }}>
              {formattedTime}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Assistant message                                                   */
  /* ------------------------------------------------------------------ */
  const displayContent = cleanBotContent(message.content);

  return (
    <div className="msg-row msg-row--assistant">
      {/* Avatar */}
      <div className="msg-bot-avatar-wrap">
        <div className="msg-bot-avatar">
          <img src="/dia-avatar.png" alt="DIA" />
        </div>
      </div>

      {/* Bubble */}
      <div
        className={`msg-bubble bot group${hasError ? ' msg-bubble--error' : ''}`}
        style={{
          backgroundColor: hasError ? '#fef2f2' : undefined,
          color: hasError ? '#991b1b' : undefined,
          borderLeft: isStreaming ? '3px solid #0057a6' : undefined,
          whiteSpace: 'pre-wrap',
        }}
      >
        {renderMessageContent(displayContent)}

        {/* Streaming cursor */}
        {isStreaming && (
          <span
            style={{
              display: 'inline-block',
              width: '7px',
              height: '15px',
              background: '#0057a6',
              borderRadius: '2px',
              marginLeft: '5px',
              verticalAlign: 'middle',
              animation: 'pulse 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
          />
        )}

        {/* Timestamp */}
        {formattedTime && !isStreaming && (
          <div style={{ fontSize: '10px', color: 'rgba(26,35,50,0.45)', marginTop: '5px', fontWeight: 400 }}>
            {formattedTime}
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && !isStreaming && (
          <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid rgba(0,60,120,0.1)' }}>
            <div style={{ fontSize: '11px', color: '#5a6a84', marginBottom: '6px', fontWeight: 600, letterSpacing: '0.2px' }}>
              Source{message.sources.length > 1 ? 's' : ''}:
            </div>
            {message.sources.map((src, i) => (
              <div key={i} style={{ fontSize: '11px', color: '#4b5a72', lineHeight: 1.5, display: 'flex', gap: '6px' }}>
                <span style={{ color: '#0057a6', flexShrink: 0 }}>▪</span>
                <span style={{ wordBreak: 'break-word' }}>{src}</span>
              </div>
            ))}
          </div>
        )}

        {/* Copy button (hover) */}
        {!isStreaming && !hasError && message.content && (
          <button
            onClick={handleCopy}
            title="Copy message"
            aria-label="Copy message"
            style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              opacity: 0,
              background: 'transparent',
              border: 'none',
              borderRadius: '6px',
              padding: '5px',
              cursor: 'pointer',
              color: '#6b7fa0',
              transition: 'opacity 0.2s, background 0.2s',
            }}
            className="copy-btn"
            onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = '#f0f4f9'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.background = 'transparent'; }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {copied ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
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
