"""Authentication DTOs."""

from pydantic import BaseModel, Field
from typing import List, Optional


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Windows ID or email address")
    password: str = Field(..., min_length=1)


class EmployeeUser(BaseModel):
    username: str
    employee_id: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    # Stable Active Directory identifier (objectGUID). Preferred key for per-user
    # chat history because — unlike username/UPN/email — it never changes.
    ad_object_id: Optional[str] = None
    # userPrincipalName, stored as metadata only (may change over time).
    upn: Optional[str] = None

    @property
    def stable_user_id(self) -> str:
        """
        The identity used to own and scope chat history.

        Prefer the immutable AD objectGUID. Fall back to the Windows login
        (sAMAccountName) only when the directory did not return a GUID — this
        preserves the pre-existing behaviour and existing history rows.

        IMPORTANT: this is derived from the AD-authenticated token/session on the
        backend. It must never be taken from a client-supplied field.
        """
        return (self.ad_object_id or "").strip() or self.username

    @property
    def legacy_identity_keys(self) -> List[str]:
        """
        Older identity values a user's history may have been stored under before
        the stable AD id was available (username, employee_id). Used to reconcile
        ownership so a user keeps access to their prior conversations.
        """
        keys: List[str] = []
        stable = self.stable_user_id
        for candidate in (self.username, self.employee_id):
            value = (candidate or "").strip()
            if value and value != stable and value not in keys:
                keys.append(value)
        return keys


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: EmployeeUser
    must_change_password: bool = False


class AuthConfigResponse(BaseModel):
    auth_enabled: bool
    default_password_hint: Optional[str] = None


class MeResponse(BaseModel):
    user: EmployeeUser
    must_change_password: bool = False
