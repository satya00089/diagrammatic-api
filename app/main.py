"""Main application file for the Diagrammatic API service."""

from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi import FastAPI

from app.utils.config import Settings
from app.routers import assessment, problems
from app.middleware.rate_limiter import RateLimitMiddleware
from app.services.problem_service import problem_service

# Load settings
settings = Settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Application lifespan events.
    """
    # Startup
    print("🚀 Diagrammatic API starting up...")
    try:
        await problem_service.connect()
        print("✅ MongoDB connected successfully")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")

    yield

    # Shutdown
    print("👋 Diagrammatic API shutting down...")
    await problem_service.disconnect()


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
    return {"status": "healthy"}
