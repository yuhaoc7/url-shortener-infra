from fastapi import APIRouter, Depends, HTTPException, Header, Request, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import datetime, timedelta, timezone

from ...database import get_db
from ...schemas import LinkCreate, LinkResponse, LinkMetadata
from ...models import Link
from ...crud import create_link, get_link_by_short_code, soft_delete_link, get_link_by_id
from ...utils import generate_random_code
from ...config import settings

from ...services.rate_limiter import RateLimiter

router = APIRouter()

@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RateLimiter(requests=5, window=60))])
async def shorten_link(
    link_in: LinkCreate,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    db: AsyncSession = Depends(get_db)
):
    tenant_id = x_tenant_id or link_in.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID is required (header or body)")

    # 1. Generate short_code
    if link_in.custom_alias:
        short_code = link_in.custom_alias
        # Check collision for custom alias immediately
        existing = await get_link_by_short_code(db, short_code)
        if existing:
            raise HTTPException(status_code=409, detail="Alias already in use")
    else:
        # Retry loop for random collision
        for _ in range(5):
            short_code = generate_random_code()
            if not await get_link_by_short_code(db, short_code):
                break
        else:
            raise HTTPException(status_code=500, detail="Could not generate unique code")

    # 2. Calculate expiry
    expires_at = None
    if link_in.ttl_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=link_in.ttl_seconds)

    # 3. Save to DB
    new_link = Link(
        tenant_id=tenant_id,
        short_code=short_code,
        long_url=str(link_in.long_url),
        expires_at=expires_at,
        status="active"
    )

    try:
        created_link = await create_link(db, new_link)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Alias already in use")
    
    # 4. Construct response
    # For now, base URL is hardcoded or from env. Ideally invalid in prod without proper domain.
    base_url = "http://localhost:8000" 
    short_url = f"{base_url}/{short_code}"

    return LinkResponse(
        short_code=created_link.short_code,
        short_url=short_url,
        long_url=created_link.long_url,
        expires_at=created_link.expires_at,
        created_at=created_link.created_at,
        status=created_link.status
    )

@router.get("/links/{short_code}", response_model=LinkMetadata)
async def get_link_metadata(
    short_code: str,
    db: AsyncSession = Depends(get_db)
):
    link = await get_link_by_short_code(db, short_code)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    base_url = "http://localhost:8000"
    short_url = f"{base_url}/{short_code}"

    return LinkMetadata(
        short_code=link.short_code,
        short_url=short_url,
        long_url=link.long_url,
        expires_at=link.expires_at,
        created_at=link.created_at,
        status=link.status,
        click_count=link.click_count,
        tenant_id=link.tenant_id
    )

@router.delete("/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    db: AsyncSession = Depends(get_db)
):
    from ...redis import redis_client

    if not x_tenant_id:
         raise HTTPException(status_code=400, detail="Tenant ID is required for deletion")

    success = await soft_delete_link(db, short_code, x_tenant_id)
    if not success:
        # Could be 404 or just not owned by tenant. 
        # For security, we might want to be vague, but 404 is standard.
        raise HTTPException(status_code=404, detail="Link not found or not authorized")
    
    # Invalidate Cache
    await redis_client.delete(f"short:{short_code}")

    return None
