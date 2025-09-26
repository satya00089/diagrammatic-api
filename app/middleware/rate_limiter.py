"""Rate limiting middleware for FastAPI applications."""

import time
from collections import defaultdict, deque
from typing import Dict, Deque
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware that tracks requests per IP address.
    """

    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # Store request timestamps per IP
        self.request_history: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit for this IP
        if not self._is_allowed(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute allowed.",
            )

        # Record this request
        self._record_request(client_ip)

        # Continue with the request
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers or connection."""
        # Check for forwarded headers first (common in production behind proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection IP
        return request.client.host if request.client else "unknown"

    def _is_allowed(self, client_ip: str) -> bool:
        """Check if the client IP is within rate limit."""
        current_time = time.time()
        minute_ago = current_time - 60  # 60 seconds ago

        # Get request history for this IP
        ip_requests = self.request_history[client_ip]

        # Remove requests older than 1 minute
        while ip_requests and ip_requests[0] < minute_ago:
            ip_requests.popleft()

        # Check if within limit
        return len(ip_requests) < self.requests_per_minute

    def _record_request(self, client_ip: str):
        """Record a request for the given IP."""
        current_time = time.time()
        self.request_history[client_ip].append(current_time)

        # Clean up old entries to prevent memory bloat
        self._cleanup_old_entries()

    def _cleanup_old_entries(self):
        """Clean up old IP entries that haven't made requests recently."""
        current_time = time.time()
        five_minutes_ago = current_time - 300  # 5 minutes ago

        # Remove IPs that haven't made requests in the last 5 minutes
        ips_to_remove = []
        for ip, requests in self.request_history.items():
            if not requests or requests[-1] < five_minutes_ago:
                ips_to_remove.append(ip)

        for ip in ips_to_remove:
            del self.request_history[ip]
