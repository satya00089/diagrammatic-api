"""Run the FastAPI application with uvicorn."""

import uvicorn
import sys

from app.utils.config import get_settings


if __name__ == "__main__":
    try:
        settings = get_settings()
        uvicorn.run(
            "app.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=True,
            log_level="debug" if settings.debug else "info",
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped gracefully")
        sys.exit(0)
