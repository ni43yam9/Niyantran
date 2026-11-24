import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password, verify_password, create_access_token
from backend.app.models.user import User
from backend.app.schemas.auth import UserRegisterRequest


def register_user(db: Session, req: UserRegisterRequest) -> Tuple[User, str]:
    """
    Registers a new user account with hashed password and generates an initial JWT token.
    Enforces email uniqueness.
    """
    email_clean = req.email.strip().lower()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{email_clean}' already exists.",
        )

    user_id = str(uuid.uuid4())
    user_uuid = str(uuid.uuid4())
    hashed_pwd = hash_password(req.password)

    user = User(
        id=user_id,
        uuid=user_uuid,
        name=req.name.strip(),
        email=email_clean,
        password_hash=hashed_pwd,
        is_active=True,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, email=user.email)
    return user, token


def authenticate_user(db: Session, email: str, password: str) -> Tuple[User, str]:
    """
    Authenticates user by email and password, returning user model and new JWT token.
    Raises 401 on incorrect credentials.
    """
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or suspended.",
        )

    token = create_access_token(subject=user.id, email=user.email)
    return user, token


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Retrieves user by internal ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieves user by email address."""
    return db.query(User).filter(User.email == email.strip().lower()).first()
