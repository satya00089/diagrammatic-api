"""Main application file for the Diagrammatic API service."""

from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi import FastAPI

from app.utils.config import get_settings
from app.routers import assessment, problems, auth, diagrams, collaboration
from app.middleware.rate_limiter import RateLimitMiddleware
from app.services.dynamodb_service import dynamodb_service

# Load settings
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Application lifespan events.
    """
    # Startup
    print("🚀 Diagrammatic API starting up...")
    try:
        # Test DynamoDB connection
        dynamodb_service.get_all_problems()
        print("✅ DynamoDB connected successfully (lifespan)")
    except Exception as e:
        print(f"❌ Failed to connect to DynamoDB at startup: {e}")

    yield

    # Shutdown (might not run on some serverless platforms)
    print("👋 Diagrammatic API shutting down...")


app = FastAPI(
    title="Diagrammatic API",
    description="AI-powered assessment service for system design solutions",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(
    RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

# Include routers
app.include_router(assessment.router, prefix="/api/v1", tags=["assessment"])
app.include_router(problems.router, prefix="/api/v1", tags=["problems"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(diagrams.router, prefix="/api/v1", tags=["diagrams"])
app.include_router(collaboration.router, prefix="/api/v1", tags=["collaboration"])


@app.get("/")
async def root():
    """Root endpoint providing basic info about the API."""
    return {
        "message": "System Design Assessor API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test DynamoDB connection by fetching problems
        problems = dynamodb_service.get_all_problems()
        healthy = problems is not None
    except Exception:
        healthy = False
    return {"status": "healthy" if healthy else "degraded", "database": "dynamodb"}
