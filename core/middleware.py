import time
import asyncio
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config.settings import settings

class TokenBucketRateLimiter:
    """In-memory Token Bucket for rate-limiting API requests."""
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

# Global rate limiter instance
limiter = TokenBucketRateLimiter(
    capacity=settings.RATE_LIMIT_TOKENS, 
    refill_rate=settings.RATE_LIMIT_REFILL_RATE
)

class SecurityTelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject security telemetry headers and enforce 
    global rate-limiting across the SentinAI framework.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Rate Limiting Check
        if not await limiter.consume(1):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Token bucket depleted."}
            )
            
        # 2. Process Request & Track Telemetry
        start_time = time.time()
        
        try:
            response = await call_next(request)
        except Exception as e:
            # Catch unhandled exceptions for telemetry
            return JSONResponse(
                status_code=500,
                content={"error": "Internal Orchestration Error", "details": str(e)}
            )
            
        process_time = time.time() - start_time
        
        # 3. Inject Telemetry Headers
        response.headers["X-SentinAI-Process-Time"] = str(round(process_time, 4))
        response.headers["X-SentinAI-Tokens-Remaining"] = str(int(limiter.tokens))
        
        return response