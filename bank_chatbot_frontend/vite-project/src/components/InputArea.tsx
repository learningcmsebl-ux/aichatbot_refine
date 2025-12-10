import React, { useState, KeyboardEvent, useEffect, useRef } from 'react';
import './ChatInterface.css';

interface InputAreaProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSend, disabled }) => {
  const [input, setInput] = useState('');
  const [showButton, setShowButton] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setShowButton(input.trim().length >= 2);
  }, [input]);

  // Refocus input when it becomes enabled again (after loading completes)
  useEffect(() => {
    if (!disabled && inputRef.current) {
      // Use multiple timing strategies to ensure focus works
      const focusInput = () => {
        if (inputRef.current && !inputRef.current.disabled) {
          inputRef.current.focus();
        }
      };
      
      // Try immediately
      focusInput();
      
      // Try after a short delay
      setTimeout(focusInput, 50);
      
      // Try after DOM update
      requestAnimationFrame(() => {
        setTimeout(focusInput, 10);
      });
    }
  }, [disabled]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      const message = input.trim();
      onSend(message);
      setInput('');
      setShowButton(false);
      // Keep focus on input after sending - use multiple attempts to ensure it works
      setTimeout(() => {
        inputRef.current?.focus();
        // Try again after a short delay in case the first attempt didn't work
        setTimeout(() => inputRef.current?.focus(), 50);
      }, 50);
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-container" style={{ width: '100%' }}>
      <div className="input-box relative flex">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message here..."
          disabled={disabled}
          className="flex-1 pr-12 text-base outline-none transition-all text-gray-800 disabled:opacity-60 disabled:cursor-not-allowed"
          style={{
            padding: '0',
            backgroundColor: 'transparent',
            border: 'none',
            fontSize: '16px',
            outline: 'none',
            transition: 'all 0.3s ease',
            color: '#1f2937',
            lineHeight: 1.55,
            letterSpacing: '0.1px',
            boxShadow: 'none',
          }}
          aria-label="Chat input"
          aria-describedby="input-help"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className={`absolute right-1.5 top-1/2 -translate-y-1/2 p-0 w-8 h-8 rounded-full flex items-center justify-center transition-all flex-shrink-0 shadow-md ${
            showButton && !disabled && input.trim()
              ? 'opacity-100 scale-100'
              : 'opacity-0 scale-90 pointer-events-none'
          }`}
          style={{
            right: '18px',
            top: '50%',
            transform: 'translateY(-50%)',
            padding: 0,
            width: '32px',
            height: '32px',
            background: 'linear-gradient(135deg, #003366 0%, #004080 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '50%',
            cursor: disabled || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            flexShrink: 0,
            boxShadow: '0 2px 8px rgba(0, 51, 102, 0.2)',
          }}
          onMouseEnter={(e) => {
            if (!disabled && input.trim()) {
              e.currentTarget.style.transform = 'translateY(-50%) translateY(-2px) scale(1.05)';
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 51, 102, 0.4)';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(-50%)';
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 51, 102, 0.2)';
          }}
          onMouseDown={(e) => {
            if (!disabled && input.trim()) {
              e.currentTarget.style.transform = 'translateY(-50%) scale(0.95)';
            }
          }}
          onMouseUp={(e) => {
            if (!disabled && input.trim()) {
              e.currentTarget.style.transform = 'translateY(-50%) translateY(-2px) scale(1.05)';
            }
          }}
          aria-label="Send message"
        >
          <svg
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            className="w-5 h-5 fill-white"
            style={{ width: '20px', height: '20px', fill: 'white' }}
          >
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </div>
      <div
        style={{
          fontSize: '12px',
          color: '#6b7280',
          textAlign: 'center',
          marginTop: '7px',
          userSelect: 'none',
          WebkitUserSelect: 'none',
          MozUserSelect: 'none',
          msUserSelect: 'none',
          pointerEvents: 'none',
        }}
      >
        EBL DIA 2.0 may make mistakes. Please verify important information.
      </div>
    </div>
  );
};
