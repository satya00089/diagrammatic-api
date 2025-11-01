"""Run the FastAPI application with uvicorn."""

import uvicorn
import sys


if __name__ == "__main__":
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped gracefully")
        sys.exit(0)
