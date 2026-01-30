from fastapi import Request, HTTPException, Response
from ..redis import redis_client
from ..config import settings
import time
import logging

logger = logging.getLogger("uvicorn")

class RateLimiter:
    def __init__(self, requests: int, window: int, check_header: bool = True):
        self.requests = requests
        self.window = window
        self.check_header = check_header

    async def __call__(self, request: Request, response: Response):
        if not redis_client.client:
             # Graceful degradation: Allow if Redis is down
             return

        tenant_id = None
        if self.check_header:
            tenant_id = request.headers.get("X-Tenant-Id")
        
        # If no tenant ID in header (e.g. redirect), caller might have set it in request state?
        # Or we skip here and handle manually in endpoint?
        # For simplicity, if check_header is True and no header, we skip (or block?).
        # Requirement: "Every request is associated with a tenant."
        if not tenant_id:
             # Try to get from state (set by previous middleware or endpoint logic?)
             # In FastAPI dependencies run before route handler.
             # For Redirect, we don't know tenant yet.
             # So this dependency is suitable for Create/Delete where header is expected.
             # For Redirect, we will call rate limiter logic Explicitly inside the handler.
             return

        key = f"rate:{tenant_id}:{request.url.path}:{request.method}"
        
        try:
            # Simple Fixed Window
            current_window = int(time.time() / self.window)
            redis_key = f"{key}:{current_window}"
            
            count = await redis_client.client.incr(redis_key)
            if count == 1:
                await redis_client.client.expire(redis_key, self.window)
            
            if count > self.requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Rate limiter error: {e}")
            # Graceful degradation -> Allow
            pass

async def check_rate_limit(tenant_id: str, limit: int, window: int, key_prefix: str):
    if not redis_client.client:
        return

    try:
        current_window = int(time.time() / window)
        redis_key = f"rate:{tenant_id}:{key_prefix}:{current_window}"
        
        count = await redis_client.client.incr(redis_key)
        if count == 1:
            await redis_client.client.expire(redis_key, window)
        
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Rate limiter manual check error: {e}")
