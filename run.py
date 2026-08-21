"""Run the FastAPI application with uvicorn."""

import uvicorn
import sys

from app.utils.config import get_settings


if __name__ == "__main__":
    try:
        settings = get_settings()
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="debug" if settings.debug else "info",
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped gracefully")
        sys.exit(0)
