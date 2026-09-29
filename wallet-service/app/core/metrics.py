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

# --- Wallet domain metrics ---------------------------------------------------

wallet_credit_total = Counter(
    "wallet_credit_total",
    "Total number of successful wallet credit operations",
    registry=registry,
)

wallet_debit_total = Counter(
    "wallet_debit_total",
    "Total number of successful wallet debit operations",
    registry=registry,
)

wallet_balance_operations_total = Counter(
    "wallet_balance_operations_total",
    "Total number of balance-affecting operations, labeled by outcome",
    ["operation", "outcome"],
    registry=registry,
)

wallet_freeze_total = Counter(
    "wallet_freeze_total",
    "Total number of wallet freeze operations",
    registry=registry,
)

wallet_unfreeze_total = Counter(
    "wallet_unfreeze_total",
    "Total number of wallet unfreeze operations",
    registry=registry,
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
