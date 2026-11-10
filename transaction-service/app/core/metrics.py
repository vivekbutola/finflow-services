from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

registry = CollectorRegistry()

# --- Generic HTTP metrics (driven by PrometheusMiddleware) -----------------

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    registry=registry,
)

# --- Transaction domain metrics ---------------------------------------------

transaction_transfer_total = Counter(
    "transaction_transfer_total",
    "Total number of wallet-to-wallet transfer attempts, labeled by outcome",
    ["outcome"],
    registry=registry,
)

transaction_reversal_total = Counter(
    "transaction_reversal_total",
    "Total number of transaction reversal attempts, labeled by outcome",
    ["outcome"],
    registry=registry,
)

wallet_service_call_total = Counter(
    "wallet_service_call_total",
    "Total number of outbound calls to wallet-service, labeled by operation and outcome",
    ["operation", "outcome"],
    registry=registry,
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
