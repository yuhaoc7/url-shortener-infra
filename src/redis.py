import redis.asyncio as redis
from .config import settings
from typing import Optional

class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        self.client = redis.from_url(
            settings.REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True
        )
        await self.client.ping()

    async def close(self):
        if self.client:
            await self.client.aclose()

    async def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except redis.RedisError:
            # Fallback behavior or log error
            return None

    async def set(self, key: str, value: str, ex: int = None):
        if not self.client:
            return
        try:
            await self.client.set(key, value, ex=ex)
        except redis.RedisError:
            pass

    async def delete(self, key: str):
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except redis.RedisError:
            pass

redis_client = RedisClient()
