from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from .models import Link, IdempotencyKey
from typing import Optional, List
import uuid
from datetime import datetime

# Link CRUD
async def create_link(db: AsyncSession, link: Link) -> Link:
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link

async def get_link_by_short_code(db: AsyncSession, short_code: str) -> Optional[Link]:
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    return result.scalar_one_or_none()

async def get_link_by_id(db: AsyncSession, link_id: uuid.UUID) -> Optional[Link]:
    result = await db.execute(select(Link).where(Link.id == link_id))
    return result.scalar_one_or_none()

async def update_link_click_count(db: AsyncSession, short_code: str):
    await db.execute(
        update(Link)
        .where(Link.short_code == short_code)
        .values(click_count=Link.click_count + 1)
    )
    await db.commit()

async def soft_delete_link(db: AsyncSession, short_code: str, tenant_id: str) -> bool:
    result = await db.execute(
        update(Link)
        .where(Link.short_code == short_code, Link.tenant_id == tenant_id)
        .values(status="disabled")
    )
    await db.commit()
    return result.rowcount > 0

# Idempotency CRUD
async def get_idempotency_key(db: AsyncSession, tenant_id: str, key: str) -> Optional[IdempotencyKey]:
    result = await db.execute(
        select(IdempotencyKey).where(IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.key == key)
    )
    return result.scalar_one_or_none()

async def create_idempotency_key(db: AsyncSession, idempotency_key: IdempotencyKey) -> IdempotencyKey:
    db.add(idempotency_key)
    await db.commit()
    await db.refresh(idempotency_key)
    return idempotency_key
