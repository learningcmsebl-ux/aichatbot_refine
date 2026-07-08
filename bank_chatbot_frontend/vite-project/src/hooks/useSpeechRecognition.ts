import { useCallback, useEffect, useRef, useState } from 'react';
import {
  buildPermissionDeniedError,
  buildVoiceError,
  queryMicPermissionState,
  requestMicrophoneAccess,
  type VoiceErrorInfo,
  type VoiceErrorKind,
} from '../utils/micPermissionHelp';

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance;

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

interface SpeechRecognitionResultEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

function setVoiceError(kind: VoiceErrorKind, setter: (e: VoiceErrorInfo | null) => void) {
  setter(buildVoiceError(kind));
}

export function useSpeechRecognition() {
  const [isSupported] = useState(() => getSpeechRecognitionCtor() !== null);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<VoiceErrorInfo | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startRecognition = useCallback(
    (onTranscript: (text: string, isFinal: boolean) => void) => {
      const Ctor = getSpeechRecognitionCtor();
      if (!Ctor) {
        setVoiceError('unsupported', setError);
        return;
      }

      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }

      const recognition = new Ctor();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = navigator.language || 'en-US';

      recognition.onresult = (event: SpeechRecognitionResultEvent) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          transcript += event.results[i][0].transcript;
        }
        const isFinal = event.results[event.results.length - 1]?.isFinal ?? false;
        onTranscript(transcript.trim(), isFinal);
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        if (event.error === 'aborted') return;
        if (event.error === 'not-allowed') {
          setError(buildPermissionDeniedError());
        } else if (event.error === 'no-speech') {
          setVoiceError('no_speech', setError);
        } else {
          setVoiceError('generic', setError);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;

      try {
        recognition.start();
        setIsListening(true);
      } catch {
        setVoiceError('generic', setError);
        setIsListening(false);
      }
    },
    [],
  );

  const startListening = useCallback(
    async (onTranscript: (text: string, isFinal: boolean) => void) => {
      setError(null);

      const Ctor = getSpeechRecognitionCtor();
      if (!Ctor) {
        setVoiceError('unsupported', setError);
        return;
      }

      const permissionState = await queryMicPermissionState();
      if (permissionState === 'denied') {
        setError(buildPermissionDeniedError());
        return;
      }

      const micAccess = await requestMicrophoneAccess();
      if (micAccess === 'denied') {
        setError(buildPermissionDeniedError());
        return;
      }

      startRecognition(onTranscript);
    },
    [startRecognition],
  );

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return {
    isSupported,
    isListening,
    error,
    startListening,
    stopListening,
    clearError: () => setError(null),
  };
};
