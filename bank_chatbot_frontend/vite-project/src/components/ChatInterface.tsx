import React from 'react';
import { Header } from './Header';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useChat } from '../hooks/useChat';

export const ChatInterface: React.FC = () => {
  const { messages, sendMessage, isLoading, error } = useChat();

  return (
    <div
      className="bg-white rounded-3xl shadow-2xl w-full h-full flex flex-col overflow-hidden"
      style={{
        backgroundColor: 'white',
        borderRadius: '20px',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
        width: '100%',
        maxWidth: '900px',
        height: '90vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Header />
      <div
        className="flex-1 flex flex-col p-5 overflow-hidden min-h-0"
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '20px',
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        <MessageList messages={messages} isLoading={isLoading} />
        {error && (
          <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-3 mb-2">
            <p className="text-sm">{error}</p>
          </div>
        )}
        <InputArea onSend={sendMessage} disabled={isLoading} />
      </div>
    </div>
  );
};
