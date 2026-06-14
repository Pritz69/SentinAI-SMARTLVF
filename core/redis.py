import json
import time
import sys
import logging
from typing import Optional, Any
import redis.asyncio as aioredis
from config.settings import settings

logger = logging.getLogger("sentinai.redis")

class MockRedis:
    """An in-memory mock Redis client supporting key-value, expiry, increments, keys, and eval (Lua script)."""
    def __init__(self):
        self.store = {}
        self.ttls = {}
        logger.info("Initialized MockRedis in-memory store for tests")

    def _check_ttl(self, key: str):
        if key in self.ttls:
            expire_at = self.ttls[key]
            if time.time() > expire_at:
                del self.store[key]
                del self.ttls[key]

    async def get(self, key: str) -> Optional[str]:
        self._check_ttl(key)
        return self.store.get(key)

    async def set(self, key: str, value: Any) -> bool:
        self.store[key] = str(value)
        if key in self.ttls:
            del self.ttls[key]
        return True

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        self.store[key] = str(value)
        self.ttls[key] = time.time() + seconds
        return True

    async def delete(self, key: str) -> int:
        count = 0
        if key in self.store:
            del self.store[key]
            count = 1
        if key in self.ttls:
            del self.ttls[key]
        return count

    async def incr(self, key: str) -> int:
        self._check_ttl(key)
        val = int(self.store.get(key, 0)) + 1
        self.store[key] = str(val)
        return val

    async def keys(self, pattern: str = "*") -> list:
        import fnmatch
        keys_to_return = []
        for k in list(self.store.keys()):
            self._check_ttl(k)
            if k in self.store and fnmatch.fnmatch(k, pattern):
                keys_to_return.append(k)
        return keys_to_return

    async def eval(self, script: str, numkeys: int, *args) -> list:
        # Emulates the rate limiter token bucket Lua script
        keys = args[:numkeys]
        argv = args[numkeys:]
        
        key_tokens = keys[0]
        key_last_refill = keys[1]
        
        capacity = float(argv[0])
        refill_rate = float(argv[1])
        now = float(argv[2])
        consume_amount = float(argv[3]) if len(argv) > 3 else 1.0
        
        self._check_ttl(key_tokens)
        self._check_ttl(key_last_refill)
        
        last_refill = float(self.store.get(key_last_refill, now))
        current_tokens = float(self.store.get(key_tokens, capacity))
        
        time_passed = max(0.0, now - last_refill)
        refilled_tokens = min(capacity, current_tokens + time_passed * refill_rate)
        
        if refilled_tokens >= consume_amount:
            refilled_tokens -= consume_amount
            self.store[key_tokens] = str(refilled_tokens)
            self.store[key_last_refill] = str(now)
            return [1, int(refilled_tokens)]
        else:
            self.store[key_tokens] = str(refilled_tokens)
            self.store[key_last_refill] = str(now)
            return [0, int(refilled_tokens)]

    async def ping(self) -> bool:
        return True


# Global Redis Client instance
# In testing environments, we check if a real Redis server is running at settings.REDIS_URL.
# If a connection can be established, we use it; otherwise, we fall back to MockRedis
# so that unit tests can run successfully in offline environments.
is_test = (
    settings.ENV == "test" or 
    "unittest" in sys.modules or 
    "pytest" in sys.modules or
    any("test" in arg for arg in sys.argv)
)

redis_client = None
if is_test:
    import redis
    try:
        # Check if real Redis is available on port 6379 with a fast timeout (0.2s)
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.2)
        r.ping()
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("Tests: Real Redis server detected on port 6379. Running tests with real Redis.")
    except Exception:
        redis_client = MockRedis()
        logger.info("Tests: Real Redis server not detected. Falling back to MockRedis for tests.")
else:
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# Session Helper Functions
async def save_session(token: str, user_id: str, username: str, role: str, expire_minutes: int) -> None:
    """Store the user session configuration in Redis, whitelisting the JWT access token."""
    session_data = {
        "id": user_id,
        "username": username,
        "role": role,
        "login_time": time.time()
    }
    key = f"session:{token}"
    await redis_client.setex(key, expire_minutes * 60, json.dumps(session_data))

async def get_session(token: str) -> Optional[dict]:
    """Retrieve and decode the user session from Redis. Returns None if invalid or expired."""
    key = f"session:{token}"
    data = await redis_client.get(key)
    if data:
        try:
            return json.loads(data)
        except Exception:
            return None
    return None

async def delete_session(token: str) -> None:
    """Invalidate a user session by deleting the whitelist key in Redis."""
    key = f"session:{token}"
    await redis_client.delete(key)
