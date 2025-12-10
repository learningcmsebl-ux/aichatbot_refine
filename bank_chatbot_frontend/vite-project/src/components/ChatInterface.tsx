import React from 'react';
import { Header } from './Header';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useChat } from '../hooks/useChat';
import './ChatInterface.css';

export const ChatInterface: React.FC = () => {
  const { messages, sendMessage, isLoading, error } = useChat();

  return (
    <div className="chat-shell">
      <Header />
      
      <div className="dia-avatar-wrapper">
        <img src="/dia-avatar.png" alt="EBL DIA avatar" className="dia-avatar" />
      </div>

      <main className="chat-main">
        <div className="messages-container">
          <MessageList messages={messages} isLoading={isLoading} />
          {error && (
            <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-3 mb-2">
              <p className="text-sm">{error}</p>
            </div>
          )}
        </div>
        <footer className="chat-input-bar">
          <InputArea onSend={sendMessage} disabled={isLoading} />
        </footer>
      </main>
    </div>
  );
};
