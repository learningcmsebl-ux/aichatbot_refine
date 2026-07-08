import React, { useState, KeyboardEvent, useEffect, useRef, useCallback } from 'react';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { MicPermissionHelp } from './MicPermissionHelp';
import './ChatInterface.css';

interface InputAreaProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSend, disabled }) => {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const preVoiceInputRef = useRef('');
  const hasContent = input.trim().length >= 1;

  const {
    isSupported,
    isListening,
    error: voiceError,
    startListening,
    stopListening,
    clearError,
  } = useSpeechRecognition();

  // Refocus when loading finishes
  useEffect(() => {
    if (!disabled) {
      const focus = () => { if (inputRef.current && !inputRef.current.disabled) inputRef.current.focus(); };
      focus();
      setTimeout(focus, 50);
      requestAnimationFrame(() => setTimeout(focus, 10));
    }
  }, [disabled]);

  useEffect(() => {
    if (disabled && isListening) {
      stopListening();
    }
  }, [disabled, isListening, stopListening]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      if (isListening) stopListening();
      onSend(input.trim());
      setInput('');
      setTimeout(() => { inputRef.current?.focus(); setTimeout(() => inputRef.current?.focus(), 50); }, 50);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleVoiceToggle = useCallback(() => {
    if (disabled) return;

    if (isListening) {
      stopListening();
      return;
    }

    preVoiceInputRef.current = input;
    void startListening((transcript, isFinal) => {
      const prefix = preVoiceInputRef.current.trim();
      const combined = prefix ? `${prefix} ${transcript}`.trim() : transcript;
      setInput(combined);
      if (isFinal) {
        preVoiceInputRef.current = combined;
      }
    });
  }, [disabled, input, isListening, startListening, stopListening]);

  const handleVoiceRetry = useCallback(() => {
    clearError();
    handleVoiceToggle();
  }, [clearError, handleVoiceToggle]);

  return (
    <div style={{ width: '100%' }}>
      <div className={`input-box${isListening ? ' input-box--listening' : ''}`}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? 'Listening… speak your question' : 'Type your message here…'}
          disabled={disabled}
          aria-label="Chat input"
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            fontSize: '15px',
            color: '#1a2332',
            lineHeight: 1.55,
            padding: 0,
            fontFamily: 'inherit',
            opacity: disabled ? 0.6 : 1,
            cursor: disabled ? 'not-allowed' : 'text',
            minWidth: 0,
            width: '100%',
          }}
        />

        {isSupported && (
          <button
            type="button"
            onClick={handleVoiceToggle}
            disabled={disabled}
            aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
            className={`input-voice-btn${isListening ? ' input-voice-btn--active' : ''}`}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              {isListening ? (
                <path d="M6 6h12v12H6z" />
              ) : (
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
              )}
            </svg>
          </button>
        )}

        <button
          onClick={handleSend}
          disabled={disabled || !hasContent}
          aria-label="Send message"
          className="input-send-btn"
          style={{
            background: hasContent && !disabled
              ? 'linear-gradient(135deg, #003d7a 0%, #0057a6 100%)'
              : '#d0dae8',
            cursor: hasContent && !disabled ? 'pointer' : 'not-allowed',
            boxShadow: hasContent && !disabled ? '0 2px 8px rgba(0,61,122,0.28)' : 'none',
            opacity: hasContent && !disabled ? 1 : 0.45,
          }}
        >
          <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: '#fff' }}>
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </div>

      {voiceError && (
        <MicPermissionHelp
          error={voiceError}
          onRetry={handleVoiceRetry}
          onDismiss={clearError}
        />
      )}

      {isListening && !voiceError && (
        <p className="input-voice-hint" aria-live="polite">
          Listening… click the mic again to stop.
        </p>
      )}

      {/* Disclaimer */}
      <p style={{ fontSize: '11.5px', color: '#8a9ab8', textAlign: 'center', marginTop: '7px', userSelect: 'none', pointerEvents: 'none' }}>
        EBL DIA 2.0 may make mistakes. Please verify important information.
      </p>
    </div>
  );
};
