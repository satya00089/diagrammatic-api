"""Authentication related Pydantic models."""

from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


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
    preferences: Optional[dict] = None
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
    preferences: Optional[dict] = None
    createdAt: str
    updatedAt: str


class UserPreferences(BaseModel):
    """User preference fields used for personalization (optional)."""

    role: Optional[str] = None
    experience_level: Optional[str] = None
    primary_interest: Optional[List[str]] = None
    preferred_cloud: Optional[str] = None
    learning_goals: Optional[str] = None
    preferred_content_type: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("primary_interest", mode="before")
    def _coerce_primary_interest(cls, v: Any):
        """Accept a string, comma-separated string, dict or list and coerce to list[str].

        - None or empty string -> None (field omitted on update)
        - list -> convert all items to str
        - string -> split on commas if present, otherwise wrap in single-item list
        - dict -> try common keys (`value`, `label`, `id`, `name`) then stringify
        """
        if v is None:
            return None
        # Already a list -> ensure string items
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]

        # Empty string -> treat as None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if "," in s:
                return [p.strip() for p in s.split(",") if p.strip()]
            return [s]

        # If dict-like (e.g., option objects), try common keys
        if isinstance(v, dict):
            for key in ("value", "label", "id", "name"):
                val = v.get(key)
                if isinstance(val, str) and val.strip():
                    return [val.strip()]
            try:
                return [str(v)]
            except Exception:
                return None

        # Fallback: stringify into single-item list
        try:
            return [str(v)]
        except Exception:
            return None
