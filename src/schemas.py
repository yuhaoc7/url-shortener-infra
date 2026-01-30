from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime

class LinkCreate(BaseModel):
    long_url: HttpUrl
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=20, pattern="^[a-zA-Z0-9_-]+$")
    ttl_seconds: Optional[int] = Field(None, gt=0)
    tenant_id: Optional[str] = None # Can be from header or body

class LinkResponse(BaseModel):
    short_code: str
    short_url: HttpUrl
    long_url: HttpUrl
    expires_at: Optional[datetime]
    created_at: datetime
    status: str

class LinkMetadata(LinkResponse):
    click_count: int
    tenant_id: str
