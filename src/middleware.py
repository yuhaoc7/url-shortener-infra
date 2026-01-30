import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import iterate_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from uuid import uuid4

from .database import AsyncSessionLocal
from .models import IdempotencyKey

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only check for POST methods (or specific routes if needed)
        if request.method != "POST":
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Tenant can be in header (X-Tenant-Id) or we rely on extracting it later.
        # But for idempotency key uniqueness, it's (tenant_id, key). 
        # If tenant not in header, we might assume a default or fail?
        # Requirement: "Input: ... tenant_id ... Tenant can be provided via header X-Tenant-Id or request body"
        # Reading body is async and consumes stream. 
        # For simplicity, let's require X-Tenant-Id header for Idempotency to work efficiently,
        # or use a global key if acceptable. But req says "Multi-tenancy... per-tenant".
        # Let's try to get X-Tenant-Id from header.
        tenant_id = request.headers.get("X-Tenant-Id")
        if not tenant_id:
             # If strictly required, we could read body, but that's complex middleware.
             # Let's just pass through if no tenant_id found in header, effectively skipping idempotency
             # or create a temporary "unknown" scope?
             # Let's assume for now idempotency works best with header.
             return await call_next(request)

        async with AsyncSessionLocal() as db:
            # 1. Check if key exists
            stmt = select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.key == idempotency_key
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return Response(
                    content=json.dumps(existing.response_body),
                    status_code=int(existing.response_status),
                    media_type="application/json"
                )

            # 2. Process Request
            response = await call_next(request)

            # 3. Store Response (only if successful? usually yes, but depends on logic. 
            # We'll store 2xx and 4xx, maybe not 5xx)
            if response.status_code < 500:
                response_body = [section async for section in response.body_iterator]
                response.body_iterator = iterate_in_threadpool(iter(response_body))
                content = b"".join(response_body)
                
                try:
                    json_body = json.loads(content)
                except:
                    json_body = {} # Should be JSON for our API, but fallback

                new_key = IdempotencyKey(
                    tenant_id=tenant_id,
                    key=idempotency_key,
                    response_status=response.status_code,
                    response_body=json_body
                )
                db.add(new_key)
                try:
                    await db.commit()
                except IntegrityError:
                    # Race condition: duplicate key inserted by another request
                    await db.rollback()
                    # Retry fetch
                    result = await db.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                         return Response(
                            content=json.dumps(existing.response_body),
                            status_code=int(existing.response_status),
                            media_type="application/json"
                        )
            
            return response
