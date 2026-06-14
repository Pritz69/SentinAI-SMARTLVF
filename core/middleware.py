import time
import asyncio
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from config.settings import settings

class RedisTokenBucketRateLimiter:
    """Redis-backed atomic token bucket rate limiter using Lua script."""
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        # Lua script to atomically refill and consume tokens
        self.lua_script = """
        local key_tokens = KEYS[1]
        local key_last_refill = KEYS[2]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local consume_amount = tonumber(ARGV[4] or 1)
        
        local last_refill = tonumber(redis.call('get', key_last_refill) or now)
        local current_tokens = tonumber(redis.call('get', key_tokens) or capacity)
        
        local time_passed = math.max(0, now - last_refill)
        local refilled_tokens = math.min(capacity, current_tokens + time_passed * refill_rate)
        
        if refilled_tokens >= consume_amount then
            refilled_tokens = refilled_tokens - consume_amount
            redis.call('set', key_tokens, refilled_tokens)
            redis.call('set', key_last_refill, now)
            return {1, math.floor(refilled_tokens)}
        else
            redis.call('set', key_tokens, refilled_tokens)
            redis.call('set', key_last_refill, now)
            return {0, math.floor(refilled_tokens)}
        end
        """

    async def consume(self, key_prefix: str = "global", tokens: int = 1) -> tuple[bool, int]:
        """
        Consumes tokens from the token bucket.
        Returns:
            (success: bool, tokens_remaining: int)
        """
        key_tokens = f"rate_limit:{key_prefix}:tokens"
        key_last_refill = f"rate_limit:{key_prefix}:last_refill"
        now = time.time()
        
        from core.redis import redis_client
        res = await redis_client.eval(
            self.lua_script,
            2,
            key_tokens,
            key_last_refill,
            self.capacity,
            self.refill_rate,
            now,
            tokens
        )
        return bool(res[0]), int(res[1])

# Global rate limiter instance
limiter = RedisTokenBucketRateLimiter(
    capacity=settings.RATE_LIMIT_TOKENS, 
    refill_rate=settings.RATE_LIMIT_REFILL_RATE
)

class SecurityTelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject security telemetry headers, track global site visits, 
    and enforce global rate-limiting across the SentinAI framework using Redis.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. Rate Limiting Check
        allowed, tokens_remaining = await limiter.consume("global", 1)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Token bucket depleted."}
            )
            
        # 2. Process Request & Track Telemetry
        start_time = time.time()
        
        # Track site visits in Redis
        from core.redis import redis_client
        try:
            await redis_client.incr("site_visits")
        except Exception:
            pass
        
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
        response.headers["X-SentinAI-Tokens-Remaining"] = str(tokens_remaining)
        
        return response