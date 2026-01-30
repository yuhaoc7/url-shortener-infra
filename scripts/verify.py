import httpx
import asyncio
import sys
import json

BASE_URL = "http://localhost:8000"

async def run_verification():
    print(f"🚀  Starting Verification against {BASE_URL}...\n")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Health Check
        print("1. [Health] Checking /health...")
        try:
            resp = await client.get("/health")
            if resp.status_code == 200 and resp.json() == {"status": "ok"}:
                print("   ✅  Health Check Passed")
            else:
                print(f"   ❌  Health Check Failed: {resp.text}")
                return
        except Exception as e:
            print(f"   ❌  Connection Error: {e}")
            return

        # 2. Create Link
        print("\n2. [API] Creating Short Link...")
        long_url = "https://www.example.com"
        alias = "verify-test"
        tenant_id = "verifier"
        payload = {
            "long_url": long_url,
            "custom_alias": alias,
            "tenant_id": tenant_id
        }
        headers = {"X-Tenant-Id": tenant_id}
        
        # Cleanup first if exists
        await client.delete(f"/v1/links/{alias}", headers=headers)

        resp = await client.post("/v1/links", json=payload, headers=headers)
        if resp.status_code == 201:
            data = resp.json()
            print(f"   ✅  Created: {data['short_url']}")
        else:
            print(f"   ❌  Create Failed: {resp.status_code} {resp.text}")
            return

        # 3. Verify Redirect
        print("\n3. [API] Verifying Redirect...")
        resp = await client.get(f"/{alias}", follow_redirects=False)
        if resp.status_code == 307 and resp.headers.get("location") == f"{long_url}/":
            print(f"   ✅  Redirect Location matches: {resp.headers['location']}")
        elif resp.status_code == 307 and resp.headers.get("location") == long_url:
            # Handle trailing slash diff
            print(f"   ✅  Redirect Location matches: {resp.headers['location']}")
        else:
            print(f"   ❌  Redirect Failed: {resp.status_code} {resp.headers.get('location')}")

        # 4. Verify Metadata
        print("\n4. [API] Verifying Metadata...")
        resp = await client.get(f"/v1/links/{alias}")
        if resp.status_code == 200:
            data = resp.json()
            if data["click_count"] > 0:
                 print(f"   ✅  Click Count updated: {data['click_count']}")
            else:
                 print(f"   ⚠️  Click Count not updated (Background task might be slow): {data['click_count']}")
        else:
             print(f"   ❌  Metadata Failed: {resp.status_code}")

        # 5. Idempotency
        print("\n5. [API] Verifying Idempotency...")
        idem_key = "idem-verify-1"
        headers["Idempotency-Key"] = idem_key
        
        resp1 = await client.post("/v1/links", json={"long_url": "https://p.com"}, headers=headers)
        resp2 = await client.post("/v1/links", json={"long_url": "https://p.com"}, headers=headers)
        
        if resp1.status_code == resp2.status_code and resp1.json().get("short_code") == resp2.json().get("short_code"):
             print("   ✅  Idempotency Passed (Same Response)")
        else:
             print("   ❌  Idempotency Failed")

        # 6. Rate Limiting
        print("\n6. [API] Verifying Rate Limiting...")
        spam_header = {"X-Tenant-Id": "spammer"}
        limit_hit = False
        for i in range(10):
            resp = await client.post("/v1/links", json={"long_url": "https://s.com"}, headers=spam_header)
            if resp.status_code == 429:
                limit_hit = True
                print(f"   ✅  Rate Limit Hit at request #{i+1}")
                break
        
        if not limit_hit:
            print("   ❌  Rate Limit NOT Hit (Limit might be too high or Redis down)")

        # 7. Metrics
        print("\n7. [Observability] Verifying Metrics...")
        resp = await client.get("/metrics")
        if resp.status_code == 200 and "http_requests_total" in resp.text:
            print("   ✅  Metrics Endpoint Exposed")
        else:
            print(f"   ❌  Metrics Failed: {resp.status_code}")

    print("\n✨ Verification Complete!")

if __name__ == "__main__":
    asyncio.run(run_verification())
