"""Authentication related Pydantic models."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Request model for user signup."""

    email: EmailStr
    password: str = Field(..., min_length=6)
    name: Optional[str] = None


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Request model for Google OAuth authentication."""

    credential: str


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    createdAt: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class AuthResponse(BaseModel):
    """Response model for authentication (login/signup)."""

    user: UserResponse
    token: str


class User(BaseModel):
    """Internal user model."""

    id: str
    email: str
    passwordHash: Optional[str] = None  # Optional for Google users
    name: Optional[str] = None
    picture: Optional[str] = None
    googleId: Optional[str] = None
    createdAt: str
    updatedAt: str
