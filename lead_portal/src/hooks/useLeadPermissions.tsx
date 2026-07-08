import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { LeadMyRolesResponse, LeadPermissions } from '../types';
import { LeadsAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DEFAULT: LeadPermissions = {
  view_all: false,
  assign: false,
  export: false,
  manage_roles: false,
  update_status: false,
  view_assigned_queue: false,
};

const LeadRolesContext = createContext<LeadPermissions>(DEFAULT);

export function LeadRolesProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [permissions, setPermissions] = useState<LeadPermissions>(DEFAULT);

  useEffect(() => {
    if (!isAuthenticated) {
      setPermissions(DEFAULT);
      return;
    }
    LeadsAPI.myRoles()
      .then((r: LeadMyRolesResponse) => setPermissions(r.permissions))
      .catch(() => setPermissions(DEFAULT));
  }, [isAuthenticated]);

  return (
    <LeadRolesContext.Provider value={permissions}>{children}</LeadRolesContext.Provider>
  );
}

export function useLeadPermissions(): LeadPermissions {
  return useContext(LeadRolesContext);
}
