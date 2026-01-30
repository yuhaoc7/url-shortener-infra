from fastapi import FastAPI
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .api.v1 import links

from .redis import redis_client

from .services.cleanup import delete_expired_links
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await redis_client.connect()
    task = asyncio.create_task(delete_expired_links())
    yield
    # Shutdown logic
    task.cancel()
    await redis_client.close()

from .middleware import IdempotencyMiddleware
from .observability import PrometheusMiddleware, metrics_endpoint
from .logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="URL Shortener",
    description="A distributed URL shortener service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(PrometheusMiddleware)
app.add_middleware(IdempotencyMiddleware)

app.add_route("/metrics", metrics_endpoint)

app.include_router(links.router, prefix="/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/{short_code}")
async def redirect_to_url(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    from .crud import get_link_by_short_code, update_link_click_count
    from .redis import redis_client
    from .services.rate_limiter import check_rate_limit
    import json
    
    tenant_id = None
    target_url = None

    # 1. Check Redis (Hot path)
    cached_data = await redis_client.get(f"short:{short_code}")
    if cached_data:
        try:
            data = json.loads(cached_data)
            target_url = data.get("long_url")
            tenant_id = data.get("tenant_id")
        except json.JSONDecodeError:
            # Fallback for old string format (if any legacy data)
            target_url = cached_data
    
    if target_url and tenant_id:
        # Rate Limit check for redirect (Loose: e.g. 100/min)
        await check_rate_limit(tenant_id, 100, 60, "redirect")
        return RedirectResponse(url=target_url)

    # 2. DB Fallback
    link = await get_link_by_short_code(db, short_code)
    
    if link:
        if link.expires_at and link.expires_at < datetime.now(timezone.utc):
             raise HTTPException(status_code=404, detail="Link expired")
        if link.status != "active":
             raise HTTPException(status_code=404, detail="Link disabled")
        
        tenant_id = link.tenant_id
        target_url = link.long_url

        # Rate Limit check (after DB fetch, but better than nothing)
        await check_rate_limit(tenant_id, 100, 60, "redirect")

        # 3. Populate Redis
        ttl = 86400
        if link.expires_at:
             delta = link.expires_at - datetime.now(timezone.utc)
             ttl = int(delta.total_seconds())
        
        if ttl > 0:
            cache_val = json.dumps({"long_url": target_url, "tenant_id": tenant_id})
            await redis_client.set(f"short:{short_code}", cache_val, ex=ttl)

        # Update stats
        await update_link_click_count(db, short_code)
        return RedirectResponse(url=target_url)

    raise HTTPException(status_code=404, detail="Link not found")
