import { useState, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ChatInterface } from './components/ChatInterface';
import { LoginPage } from './components/LoginPage';
import Sidebar from './components/Sidebar';
import { useChatSessions } from './hooks/useChatSessions';
import './index.css';
import './components/Sidebar.css';

// Read/write only the sidebar collapsed UI preference — no user or chat data
function readCollapsedPref(): boolean {
  try {
    return localStorage.getItem('ebl-sidebar-collapsed') === 'true';
  } catch {
    return false;
  }
}

function writeCollapsedPref(value: boolean) {
  try {
    localStorage.setItem('ebl-sidebar-collapsed', String(value));
  } catch { /* storage unavailable — ignore */ }
}

function AppContent() {
  const { authEnabled, loading, isAuthenticated } = useAuth();

  // Mobile/tablet drawer open state
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Desktop collapse/expand preference — persisted as UI-only setting
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(readCollapsedPref);

  const handleToggleCollapse = useCallback(() => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      writeCollapsedPref(next);
      return next;
    });
  }, []);

  const chatSessions = useChatSessions(isAuthenticated);

  if (loading) {
    return (
      <div className="page-bg">
        <div style={{ color: '#fff', fontSize: '1rem' }}>Loading…</div>
      </div>
    );
  }

  if (authEnabled && !isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className={`app-layout${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      {/* Mobile / tablet sidebar overlay */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Left sidebar */}
      <Sidebar
        chatSessions={chatSessions}
        isOpen={sidebarOpen}
        isCollapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={handleToggleCollapse}
      />

      {/* Main chat area */}
      <div className="app-main">
        <ChatInterface
          chatSessions={chatSessions}
          onToggleSidebar={() => setSidebarOpen(v => !v)}
        />
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
