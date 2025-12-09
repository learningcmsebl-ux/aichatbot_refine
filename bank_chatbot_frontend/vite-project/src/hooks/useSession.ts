import { useState, useEffect } from 'react';
import { storage } from '../utils/storage';

export const useSession = () => {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const saved = storage.loadSession();
    if (saved) {
      setSessionId(saved);
    } else {
      const newSessionId = generateSessionId();
      setSessionId(newSessionId);
      storage.saveSession(newSessionId);
    }
  }, []);

  const createSession = () => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    storage.saveSession(newSessionId);
    return newSessionId;
  };

  return { sessionId, createSession };
};

function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

