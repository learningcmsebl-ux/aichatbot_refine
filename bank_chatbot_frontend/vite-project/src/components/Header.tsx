import React from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserHeaderLabel } from '../utils/userDisplay';
import './ChatInterface.css';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { user, authEnabled, logout } = useAuth();
  const headerLabel = user ? getUserHeaderLabel(user) : '';

  return (
    <header className="chat-header">
      {/* Mobile hamburger — only visible on small screens (controlled via CSS) */}
      {onToggleSidebar && (
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleSidebar}
          aria-label="Open sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
      )}

      {/* Brand + DIA avatar */}
      <div className="chat-header-brand">
        <div className="header-dia-avatar">
          <img src="/dia-avatar.png" alt="EBL DIA" />
        </div>
        <div className="chat-header-left">
          <h1>EBL DIA 2.0</h1>
          <p>Digital Intelligent Assistant</p>
        </div>
      </div>

      {/* Right: user panel + status */}
      <div className="chat-header-right">
        {authEnabled && user && (
          <div className="chat-user-panel">
            <span className="chat-user-name" title={headerLabel}>
              {headerLabel}
            </span>
            <button type="button" className="chat-logout-btn" onClick={logout}>
              Sign out
            </button>
          </div>
        )}
        <div className="chat-status">
          <span className="status-dot" />
          <span>Connected</span>
        </div>
      </div>
    </header>
  );
};
