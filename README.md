# Distributed URL Shortener

A production-oriented, distributed URL Shortener service built with **FastAPI**, **PostgreSQL**, and **Redis**.

## Architecture

![Architecture](https://mermaid.ink/img/pako:eNpVkM1Kw0AQx19lmJMP4CWEIhSRFGo9iFRPY5u1Q3Y3ZCeWln33Jg0tfQDP8_8bfjODmTEGjWdFxc-Ot44-WD9wY-R6d4-v7zD8hO_v8DwM4_Q0TuM4nZ2nF3EchWkYh_P0Mk6j8OIsupmG82g6im7C8Pzi_CqK03l4fnF2dnZ2Pj2_uLgI0-llmMZxFKaXlyf0s3K8M2K8g_0D7B-gH_nQ8c7x_oHxA_QjH3o-GN5D_wD9yId-4EPHB8f7B8YP0I986Ad-5MN-5EPHB8f7B8YP0I986Ad-5EM_8qHj50_9yIeOD473D4wfoB_50P_wIf8A7Yy8TQ)

*Architecture Diagram Placeholder (ASCII)*

```
[Client] -> [Load Balancer] -> [API Service (FastAPI)]
                                  |      |
                                  v      v
                             [Redis]  [PostgreSQL]
```

### Key Features
- **Public API**: RESTful endpoints for link management.
- **Redirects**: 307 Temporary Redirect (Cached in Redis).
- **Multi-tenancy**: `X-Tenant-Id` header isolation.
- **Rate Limiting**: Redis-based sliding window (Create: 5/min, Redirect: 100/min).
- **Idempotency**: Prevents duplicate creations using `Idempotency-Key` header.
- **Observability**: Prometheus metrics (`/metrics`) and structured JSON logs.
- **Background Cleanup**: Job to expire links.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### Running Locally
1. **Start Infrastructure & App**:
   ```bash
   make up
   ```
   *Services available at `http://localhost:8000`*

2. **Verify Installation**:
   Values populated in `.env` are for local dev.
   Run the verification script to test all endpoints:
   ```bash
   # Install dependencies first if not already
   # pip install .[dev]
   python scripts/verify.py
   ```

### API Examples

**Create Link**:
```bash
curl -X POST "http://localhost:8000/v1/links" \
     -H "Content-Type: application/json" \
     -H "X-Tenant-Id: my-tenant" \
     -d '{"long_url": "https://google.com", "custom_alias": "go"}'
```

**Redirect**:
```bash
curl -v http://localhost:8000/go
```

**Metrics**:
```bash
curl http://localhost:8000/metrics
```

## Design Decisions & Tradeoffs

- **Framework**: Python/FastAPI chosen for speed of development, async capabilities, and strong typing (Pydantic).
- **Database**: PostgreSQL for relational integrity (Tenants, Links).
- **Cache**: Redis for hot-path redirects. JSON storage allows storing metadata (tenant_id) to support rate limiting on redirects without DB hit.
- **Rate Limiting**: Implemented "Graceful Degradation". If Redis is down, we fallback to allowing requests (logging the error).
- **Idempotency**: Enforced via DB unique constraint `(tenant_id, key)` to guarantee consistency even in a distributed setup.

## Future Improvements
- **Horizontal Scaling**: API is stateless. Deploy multiple replicas behind Nginx/ALB.
- **Database Sharding**: Partition `links` table by `tenant_id` for massive scale.
- **Async Events**: Move click counting to a message queue (Kafka/RabbitMQ) to reduce write load on DB during redirects.
- **CDN**: Cache redirects at the edge (Cloudflare/AWS CloudFront) for global low latency.
