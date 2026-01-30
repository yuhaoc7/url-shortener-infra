# Distributed URL Shortener

A production-oriented, distributed URL Shortener service built with **FastAPI**, **PostgreSQL**, and **Redis**.

## Architecture

```mermaid
graph LR
    Client([Client]) --> LB[Load Balancer]
    LB --> API[API Service\n(FastAPI)]
    API --> Redis[(Redis)]
    API --> DB[(PostgreSQL)]
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
