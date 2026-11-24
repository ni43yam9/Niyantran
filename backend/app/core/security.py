import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.models.user import User

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing & Verification
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """
    Hashes a password using bcrypt with random salt.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hash in constant time.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT Token Operations
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generates a signed JWT access token for an authenticated user.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": subject,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    Raises HTTPException 401 if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Default User Helper
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = "default_user"

def get_or_create_default_user(db: Session) -> User:
    """
    Ensures the default local user exists in the database for single-user/unauthenticated operation.
    """
    user = db.query(User).filter(User.id == DEFAULT_USER_ID).first()
    if not user:
        user = User(
            id=DEFAULT_USER_ID,
            uuid="00000000-0000-0000-0000-000000000000",
            name="Default User",
            email="default@niyantra.local",
            password_hash=hash_password("niyantra_default_password_local"),
            is_active=True,
            status="active",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == DEFAULT_USER_ID).first()
    return user


# ---------------------------------------------------------------------------
# FastAPI Authentication Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
    db: Session = Depends(get_db),
) -> User:
    """
    Strict dependency: Requires a valid JWT Bearer token.
    Returns the authenticated User or raises 401.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Include 'Authorization: Bearer <token>' header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user account not found or has been deleted.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or suspended.",
        )

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
    db: Session = Depends(get_db),
) -> User:
    """
    Flexible dependency:
    - If a valid JWT Bearer token is provided, returns that authenticated user.
    - If no Bearer token is provided, falls back seamlessly to the default local user ('default_user').
    Preserves 100% backwards compatibility for offline single-user desktop mode and existing tests.
    """
    if credentials and credentials.credentials:
        try:
            return get_current_user(credentials=credentials, db=db)
        except HTTPException:
            # Re-raise explicit token errors (expired or invalid token)
            raise

    return get_or_create_default_user(db)


# ---------------------------------------------------------------------------
# API Key Verification (Preserved from Phase 9)
# ---------------------------------------------------------------------------

def is_auth_required() -> bool:
    """Returns True if an API_KEY has been configured in the environment."""
    return bool(settings.API_KEY and settings.API_KEY.strip())


def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
) -> Optional[str]:
    """
    Validates API key authentication when configured in settings.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not is_auth_required():
        return "local_user"

    expected_key = settings.API_KEY.strip()
    provided_key = header_key or (credentials.credentials if credentials else None)

    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide X-API-Key or Authorization Bearer header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return "authenticated_user"
