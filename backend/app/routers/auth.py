from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_current_user
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    LogoutResponse,
)
from backend.app.services.auth_service import register_user, authenticate_user

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
)
def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """Registers a new user account, stores password hash securely via bcrypt, and issues a JWT token."""
    user, token = register_user(db, req)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login with email and password",
)
def login(
    req: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticates credentials against secure bcrypt hash and returns a signed JWT access token."""
    user, token = authenticate_user(db, email=req.email, password=req.password)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@auth_router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="User logout",
)
def logout():
    """Concludes client session. Frontend clears stored tokens and device session data."""
    return LogoutResponse(status="success", message="Logged out successfully")


@auth_router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Returns the profile of the currently authenticated user. Never exposes password hash."""
    return UserResponse.model_validate(current_user)
