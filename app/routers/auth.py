"""Authentication router for signup, login, and Google OAuth."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.auth_models import (
    SignupRequest,
    LoginRequest,
    GoogleAuthRequest,
    AuthResponse,
    UserResponse,
)
from app.services.auth_service import auth_service
from app.services.dynamodb_service import dynamodb_service

router = APIRouter()
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Dependency to get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = auth_service.decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return payload


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """Register a new user with email and password."""
    # Check if user already exists
    existing_user = dynamodb_service.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    password_hash = auth_service.hash_password(request.password)

    # Create user
    user = dynamodb_service.create_user(
        email=request.email, password_hash=password_hash, name=request.name
    )

    # Create JWT token
    token = auth_service.create_access_token(
        data={"user_id": user.id, "email": user.email}
    )

    return AuthResponse(
        user=UserResponse(
            id=user.id, email=user.email, name=user.name, createdAt=user.createdAt
        ),
        token=token,
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Authenticate user and get JWT token."""
    # Get user by email
    user = dynamodb_service.get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not user.passwordHash or not auth_service.verify_password(
        request.password, user.passwordHash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create JWT token
    token = auth_service.create_access_token(
        data={"user_id": user.id, "email": user.email}
    )

    return AuthResponse(
        user=UserResponse(
            id=user.id, email=user.email, name=user.name, createdAt=user.createdAt
        ),
        token=token,
    )


@router.post("/auth/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest):
    """Authenticate user with Google Sign-In credential."""
    # Verify Google credential
    google_info = auth_service.verify_google_token(request.credential)

    # Check if user exists by Google ID
    user = dynamodb_service.get_user_by_google_id(google_info["google_id"])

    if not user:
        # Check if user exists by email
        user = dynamodb_service.get_user_by_email(google_info["email"])

        if user:
            # User exists by email but no Google ID - update the existing user
            updated_user = dynamodb_service.update_user_google_id(user.id, google_info["google_id"])
            if updated_user:
                user = updated_user
        else:
            # Create new user (auto-registration)
            user = dynamodb_service.create_user(
                email=google_info["email"],
                name=google_info["name"],
                google_id=google_info["google_id"],
            )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create or retrieve user",
        )

    # Create JWT token
    token = auth_service.create_access_token(
        data={"user_id": user.id, "email": user.email}
    )

    return AuthResponse(
        user=UserResponse(
            id=user.id, email=user.email, name=user.name, createdAt=user.createdAt
        ),
        token=token,
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user info (requires authentication)."""
    user = dynamodb_service.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=user.id, email=user.email, name=user.name, createdAt=user.createdAt
    )
