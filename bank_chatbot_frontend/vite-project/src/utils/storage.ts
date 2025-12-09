const STORAGE_KEY_MESSAGES = 'bank_chatbot_messages';
const STORAGE_KEY_SESSION = 'bank_chatbot_session';

export const storage = {
  saveMessages: (messages: any[]) => {
    try {
      localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages));
    } catch (error) {
      console.error('Error saving messages:', error);
    }
  },

  loadMessages: (): any[] => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_MESSAGES);
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Error loading messages:', error);
      return [];
    }
  },

  saveSession: (sessionId: string) => {
    try {
      localStorage.setItem(STORAGE_KEY_SESSION, sessionId);
    } catch (error) {
      console.error('Error saving session:', error);
    }
  },

  loadSession: (): string | null => {
    try {
      return localStorage.getItem(STORAGE_KEY_SESSION);
    } catch (error) {
      console.error('Error loading session:', error);
      return null;
    }
  },

  clear: () => {
    localStorage.removeItem(STORAGE_KEY_MESSAGES);
    localStorage.removeItem(STORAGE_KEY_SESSION);
  }
};

