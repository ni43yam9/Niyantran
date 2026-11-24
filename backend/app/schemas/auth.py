from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="User's full name or display name")
    email: EmailStr = Field(..., description="Unique email address for the user account")
    password: str = Field(..., min_length=6, max_length=128, description="Secure user password (minimum 6 characters)")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's registered email address")
    password: str = Field(..., min_length=1, description="User password")


class UserResponse(BaseModel):
    id: str
    uuid: str
    name: str
    email: str
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LogoutResponse(BaseModel):
    status: str = "success"
    message: str = "Logged out successfully"
