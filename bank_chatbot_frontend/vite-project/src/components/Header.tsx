import React from 'react';
import './ChatInterface.css';

export const Header: React.FC = () => {
  return (
    <header className="chat-header">
      <div className="chat-header-left">
        <h1>EBL DIA 2.0</h1>
        <p>Digital Intelligent Assistant</p>
      </div>
      <div className="chat-status">
        <span className="status-dot" />
        <span>Connected</span>
      </div>
    </header>
  );
};
