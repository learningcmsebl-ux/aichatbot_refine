"""Employee authentication routes (Active Directory login)."""



from fastapi import APIRouter, Depends



from app.core.config import settings

from app.core.security import get_current_user

from app.models.auth import (

    AuthConfigResponse,

    LoginRequest,

    LoginResponse,

    MeResponse,

)

from app.models.portal_user import ChangePasswordRequest, ChangePasswordResponse

from app.services.auth_service import get_auth_service



auth_router = APIRouter()





@auth_router.get("/auth/config", response_model=AuthConfigResponse)

async def auth_config() -> AuthConfigResponse:

    """Tell the frontend whether employee login is required."""

    hint = None

    if settings.LDAP_PROVISION_ENABLED:

        hint = (

            f"New sales agents use temporary password "

            f"{settings.LDAP_DEFAULT_USER_PASSWORD} and must change it on first login."

        )

    return AuthConfigResponse(auth_enabled=settings.AUTH_ENABLED, default_password_hint=hint)





@auth_router.post("/auth/login", response_model=LoginResponse)

async def login(request: LoginRequest) -> LoginResponse:

    """Authenticate employee with Active Directory credentials."""

    return get_auth_service().login(request.username, request.password)





@auth_router.get("/auth/me", response_model=MeResponse)

async def me(current_user=Depends(get_current_user)) -> MeResponse:

    """Return the currently authenticated employee (refreshed from phonebook/AD)."""

    auth = get_auth_service()

    user = auth.refresh_user_profile(current_user.username)

    must_change = auth.must_change_password_for_user(user.username)

    return MeResponse(user=user, must_change_password=must_change)





@auth_router.post("/auth/change-password", response_model=ChangePasswordResponse)

async def change_password(

    body: ChangePasswordRequest,

    current_user=Depends(get_current_user),

) -> ChangePasswordResponse:

    """Change AD password (required after first login with default password)."""

    get_auth_service().change_password(

        current_user,

        body.current_password,

        body.new_password,

    )

    return ChangePasswordResponse()


