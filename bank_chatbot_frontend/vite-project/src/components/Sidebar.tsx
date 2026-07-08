import React, { useState, useRef, useEffect } from 'react';
import './Sidebar.css';
import type { ChatSessionItem } from '../types';
import type { UseChatSessionsReturn } from '../hooks/useChatSessions';

interface SidebarProps {
  chatSessions: UseChatSessionsReturn;
  isOpen: boolean;
  isCollapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
}

// ---- Time helpers ----
function formatRelativeTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function getDayGroup(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400_000);
  const weekAgo = new Date(today.getTime() - 7 * 86400_000);
  const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  if (itemDay.getTime() === today.getTime()) return 'Today';
  if (itemDay.getTime() === yesterday.getTime()) return 'Yesterday';
  if (itemDay >= weekAgo) return 'Previous 7 Days';
  return 'Older';
}

function groupSessions(sessions: ChatSessionItem[]) {
  const order = ['Today', 'Yesterday', 'Previous 7 Days', 'Older'];
  const map = new Map<string, ChatSessionItem[]>();
  order.forEach(g => map.set(g, []));
  sessions.forEach(s => {
    const g = getDayGroup(s.updated_at);
    map.get(g)?.push(s);
  });
  return order.filter(g => (map.get(g)?.length ?? 0) > 0).map(g => ({ label: g, items: map.get(g)! }));
}

// ---- Per-item component ----
interface HistoryItemProps {
  session: ChatSessionItem;
  isActive: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onArchive: () => void;
  onDelete: () => void;
}

function HistoryItem({ session, isActive, onSelect, onRename, onArchive, onDelete }: HistoryItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(session.title);
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
  }, [renaming]);

  const handleRenameSubmit = () => {
    if (renameValue.trim() && renameValue.trim() !== session.title) onRename(renameValue.trim());
    setRenaming(false);
  };

  return (
    <div
      className={`history-item${isActive ? ' active' : ''}`}
      onClick={() => { if (!renaming) onSelect(); }}
    >
      <div className="history-item-body">
        {renaming ? (
          <input
            ref={inputRef}
            className="history-item-title"
            value={renameValue}
            onChange={e => setRenameValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={e => {
              if (e.key === 'Enter') handleRenameSubmit();
              if (e.key === 'Escape') { setRenaming(false); setRenameValue(session.title); }
            }}
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <div className="history-item-title">{session.title}</div>
        )}
        {session.preview && !renaming && (
          <div className="history-item-preview">{session.preview}</div>
        )}
      </div>
      <span className="history-item-time">{formatRelativeTime(session.updated_at)}</span>

      <button
        className="item-menu-btn"
        onClick={e => { e.stopPropagation(); setMenuOpen(v => !v); }}
        aria-label="More options"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <circle cx="2" cy="7" r="1.2" fill="currentColor"/>
          <circle cx="7" cy="7" r="1.2" fill="currentColor"/>
          <circle cx="12" cy="7" r="1.2" fill="currentColor"/>
        </svg>
      </button>

      {menuOpen && (
        <div className="item-dropdown" ref={menuRef} onClick={e => e.stopPropagation()}>
          <button onClick={() => { setMenuOpen(false); setRenaming(true); setRenameValue(session.title); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Rename
          </button>
          <button onClick={() => { setMenuOpen(false); onArchive(); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>
            Archive
          </button>
          <button className="danger" onClick={() => { setMenuOpen(false); onDelete(); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ---- Chevron SVGs ----
const ChevronLeft = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);
const ChevronRight = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);
const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);

// ---- Main Sidebar ----
export default function Sidebar({ chatSessions, isOpen, isCollapsed, onClose, onToggleCollapse }: SidebarProps) {
  const {
    sessions,
    activeSessionId,
    searchQuery,
    setSearchQuery,
    selectSession,
    newChat,
    renameSession,
    archiveSession,
    deleteSession,
  } = chatSessions;

  const groups = groupSessions(sessions);

  return (
    <aside className={`sidebar${isOpen ? ' open' : ''}${isCollapsed ? ' collapsed' : ''}`}>

      {/* ================================================================
          ICON RAIL — shown by CSS only on desktop when collapsed.
          Always rendered so resize from desktop→tablet still works.
          ================================================================ */}
      <div className="sidebar-icon-rail">
        <div className="sidebar-logo-mark" title="EBL DIA 2.0">EBL</div>
        <button
          className="new-chat-icon-btn"
          onClick={() => newChat()}
          title="New Chat"
          aria-label="New Chat"
        >
          <PlusIcon />
        </button>
        <div className="rail-spacer" />
        <button
          className="sidebar-expand-btn"
          onClick={onToggleCollapse}
          title="Expand sidebar"
          aria-label="Expand sidebar"
        >
          <ChevronRight />
        </button>
      </div>

      {/* ================================================================
          FULL CONTENT — always rendered; hidden by CSS when desktop-collapsed.
          On tablet/mobile it always shows regardless of isCollapsed prop.
          ================================================================ */}
      <div className="sidebar-full-content">
        {/* Header */}
        <div className="sidebar-header">
          <div className="sidebar-logo-mark">EBL</div>
          <div className="sidebar-title-text">
            <h2>EBL DIA 2.0</h2>
            <span>Chat History</span>
          </div>
          {/* Desktop collapse button */}
          <button
            className="sidebar-collapse-btn-desktop"
            onClick={onToggleCollapse}
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft />
          </button>
          {/* Mobile / tablet close button */}
          <button className="sidebar-close-btn" onClick={onClose} aria-label="Close sidebar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* New Chat */}
        <button className="new-chat-btn" onClick={() => { newChat(); onClose(); }}>
          <PlusIcon />
          New Chat
        </button>

        {/* Search */}
        <div className="sidebar-search-wrap">
          <input
            className="sidebar-search"
            type="text"
            placeholder="Search conversations…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>

        {/* History */}
        <div className="sidebar-history">
          {groups.length === 0 && (
            <div className="sidebar-empty">
              {searchQuery ? 'No results found.' : 'No conversations yet.\nStart a new chat!'}
            </div>
          )}
          {groups.map(group => (
            <div key={group.label}>
              <div className="history-group-label">{group.label}</div>
              {group.items.map(session => (
                <HistoryItem
                  key={session.id}
                  session={session}
                  isActive={activeSessionId === session.id}
                  onSelect={() => { selectSession(session.id); onClose(); }}
                  onRename={title => renameSession(session.id, title)}
                  onArchive={() => archiveSession(session.id)}
                  onDelete={() => deleteSession(session.id)}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
