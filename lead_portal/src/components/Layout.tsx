import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLeadPermissions } from '../hooks/useLeadPermissions';

export function Layout() {
  const { user, logout } = useAuth();
  const perms = useLeadPermissions();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h2>Lead Portal</h2>
          <p>Eastern Bank PLC</p>
        </div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/leads">All Leads</NavLink>
          <NavLink to="/my-leads">My Submitted</NavLink>
          {perms.view_assigned_queue && (
            <NavLink to="/assigned">Assigned to Me</NavLink>
          )}
          {perms.manage_roles && (
            <NavLink to="/users">Register team</NavLink>
          )}
        </nav>
        <div className="sidebar-user">
          <div>{user?.full_name || user?.username}</div>
          {user?.employee_id && <div>ID: {user.employee_id}</div>}
          <button type="button" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
