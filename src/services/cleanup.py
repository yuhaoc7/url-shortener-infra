import asyncio
import logging
from sqlalchemy import update
from datetime import datetime, timezone
from ..database import AsyncSessionLocal
from ..models import Link

logger = logging.getLogger(__name__)

async def delete_expired_links():
    while True:
        try:
            logger.info("Running background cleanup job...")
            async with AsyncSessionLocal() as db:
                # Mark as expired
                stmt = (
                    update(Link)
                    .where(Link.expires_at < datetime.now(timezone.utc))
                    .where(Link.status == "active")
                    .values(status="expired")
                )
                result = await db.execute(stmt)
                await db.commit()
                if result.rowcount > 0:
                    logger.info(f"Expired {result.rowcount} links.")
        except Exception as e:
            logger.error(f"Error in cleanup job: {e}")
        
        # Run every hour
        await asyncio.sleep(3600)
