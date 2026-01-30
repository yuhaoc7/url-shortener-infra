from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time

# Metrics definitions
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

CACHE_HITS = Counter("cache_hits_total", "Total cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Total cache misses")
REDIRECT_TOTAL = Counter("redirect_total", "Total redirects")
REDIRECT_404_TOTAL = Counter("redirect_404_total", "Total failed redirects (404)")
RATE_LIMITED_TOTAL = Counter("rate_limited_total", "Total rate limited requests")


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # Normalize path for high cardinality
        # Simple heuristic: if path starts with /v1/links/ and has more, group it?
        # But we want to track short codes specifically? No, that's too high cardinality.
        # We should use router.path_format if possible, but middleware sees raw path.
        # Let's keep it simple for now, maybe replace UUIDs or random strings.
        
        response = await call_next(request)
        
        process_time = time.perf_counter() - start_time
        
        status_code = str(response.status_code)
        method = request.method
        path = request.url.path # Caveat: high cardinality if many short codes.
        
        # Simplify path for metrics
        if path.startswith("/v1/links/"):
             metric_path = "/v1/links/{code}"
        elif path == "/v1/links":
             metric_path = "/v1/links"
        elif path == "/metrics":
             metric_path = "/metrics"
        elif path == "/health":
             metric_path = "/health"
        elif len(path) > 1 and "/" not in path[1:]: # Root redirect /{code}
             metric_path = "/{code}"
        else:
             metric_path = path

        HTTP_REQUESTS_TOTAL.labels(method=method, path=metric_path, status=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=metric_path).observe(process_time)
        
        return response

def metrics_endpoint(request: Request):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
