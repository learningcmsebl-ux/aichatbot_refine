import type { EmployeeUser } from '../types';

/** Strip org-unit prefixes like "HO/ICT - Name" from AD display strings. */
export function cleanDisplayName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return trimmed;

  const sep = ' - ';
  if (trimmed.includes(sep)) {
    const idx = trimmed.indexOf(sep);
    const left = trimmed.slice(0, idx);
    const right = trimmed.slice(idx + sep.length).trim();
    if (right && (left.includes('/') || left.length <= 24)) {
      return right;
    }
  }
  return trimmed;
}

/** Name shown in the header — never the Windows login id when a real name exists. */
export function getUserHeaderLabel(user: EmployeeUser): string {
  const fullName = user.full_name?.trim();
  if (fullName) {
    return cleanDisplayName(fullName);
  }
  return user.username?.trim() || 'Employee';
}
