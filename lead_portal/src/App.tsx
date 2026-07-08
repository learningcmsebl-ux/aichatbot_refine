import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LeadRolesProvider } from './hooks/useLeadPermissions';
import { LoginPage } from './components/LoginPage';
import { ChangePasswordPage } from './components/ChangePasswordPage';
import { Layout } from './components/Layout';
import { Dashboard } from './components/Dashboard';
import { LeadListPage } from './components/LeadListPage';
import { LeadDetailPage } from './components/LeadDetailPage';
import { UserManagementPage } from './components/UserManagementPage';

function AppRoutes() {
  const { loading, isAuthenticated, mustChangePassword } = useAuth();

  if (loading) {
    return <div className="app-loading">Loading…</div>;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  if (mustChangePassword) {
    return <ChangePasswordPage />;
  }

  return (
    <LeadRolesProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="leads" element={<LeadListPage mode="all" title="All Leads" subtitle="Leads visible to your role" />} />
          <Route path="my-leads" element={<LeadListPage mode="my" title="My Submitted Leads" subtitle="Leads you referred" />} />
          <Route path="assigned" element={<LeadListPage mode="assigned" title="Assigned to Me" subtitle="Leads assigned to you" />} />
          <Route path="users" element={<UserManagementPage />} />
          <Route path="leads/:ref" element={<LeadDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </LeadRolesProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
