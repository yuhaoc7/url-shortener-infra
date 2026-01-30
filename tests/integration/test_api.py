import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_create_short_link(client: AsyncClient):
    payload = {
        "long_url": "https://www.example.com",
        "custom_alias": "pytest-alias",
        "tenant_id": "test-tenant"
    }
    headers = {"X-Tenant-Id": "test-tenant"}
    
    # Create
    response = await client.post("/v1/links", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["short_code"] == "pytest-alias"
    assert data["long_url"] == "https://www.example.com/"

    # Verify Metadata
    response = await client.get("/v1/links/pytest-alias")
    assert response.status_code == 200
    assert response.json()["click_count"] == 0

@pytest.mark.asyncio
async def test_redirect(client: AsyncClient):
    # Setup
    payload = {"long_url": "https://www.google.com", "custom_alias": "go-google"}
    headers = {"X-Tenant-Id": "t1"}
    await client.post("/v1/links", json=payload, headers=headers)

    # Redirect (Note: TestClient doesn't follow redirects by default with allow_redirects=True for 3xx, 
    # but httpx default is False, which is what we want to check 307)
    response = await client.get("/go-google")
    assert response.status_code == 307
    assert response.headers["location"] == "https://www.google.com/"

@pytest.mark.asyncio
async def test_rate_limit(client: AsyncClient):
    # Depending on the state of Redis, this might define strict window.
    # We reuse the same Redis, so previous manual tests might affect this.
    # We should use a unique tenant for this test.
    tenant = "spam-tenant"
    headers = {"X-Tenant-Id": tenant}
    payload = {"long_url": "https://foo.com"}

    # Limit is 5 per minute
    for _ in range(5):
        response = await client.post("/v1/links", json=payload, headers=headers)
        if response.status_code == 429:
             break # Already hit limit
        assert response.status_code == 201

    # Next should fail
    response = await client.post("/v1/links", json=payload, headers=headers)
    assert response.status_code == 429

@pytest.mark.asyncio
async def test_idempotency(client: AsyncClient):
    tenant = "idem-test"
    headers = {"X-Tenant-Id": tenant, "Idempotency-Key": "key-123"}
    payload = {"long_url": "https://v1.com"}

    # First call
    resp1 = await client.post("/v1/links", json=payload, headers=headers)
    assert resp1.status_code == 201
    data1 = resp1.json()

    # Second call (same key)
    resp2 = await client.post("/v1/links", json=payload, headers=headers)
    assert resp2.status_code == 201
    data2 = resp2.json()

    assert data1["short_code"] == data2["short_code"]
    assert data1["created_at"] == data2["created_at"]
