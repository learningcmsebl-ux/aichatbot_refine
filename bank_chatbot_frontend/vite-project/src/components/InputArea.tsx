import React, { useState, KeyboardEvent, useEffect, useRef } from 'react';

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

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
      setShowButton(false);
      // Keep focus on input after sending
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="mt-5">
      <div className="relative flex">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message here..."
          disabled={disabled}
          className="flex-1 px-4 py-3 pr-12 bg-white border border-gray-300 rounded-xl text-base outline-none transition-all text-gray-800 shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
          style={{
            padding: '12px 50px 12px 16px',
            backgroundColor: '#ffffff',
            border: '1px solid #d1d5db',
            borderRadius: '12px',
            fontSize: '16px',
            outline: 'none',
            transition: 'all 0.3s ease',
            color: '#1f2937',
            lineHeight: 1.55,
            letterSpacing: '0.1px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
          }}
          onFocus={(e) => {
            e.target.style.borderColor = '#003366';
            e.target.style.boxShadow = '0 0 0 3px rgba(0, 51, 102, 0.1)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = '#d1d5db';
            e.target.style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)';
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
            right: '6px',
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
        id="input-help"
        className="text-xs text-gray-500 text-center pt-2"
        style={{
          fontSize: '13px',
          color: '#6b7280',
          paddingTop: '8px',
          textAlign: 'center',
        }}
      >
        EBL DIA can make mistakes. Please check important information.
      </div>
      <div
        className="text-xs text-gray-700 text-left pt-1 italic"
        style={{
          fontSize: '11px',
          color: '#1f2937',
          textAlign: 'left',
          fontStyle: 'italic',
        }}
      >
        Powered by EBL ICT Division
      </div>
    </div>
  );
};
