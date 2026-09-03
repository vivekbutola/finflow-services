from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

registry = CollectorRegistry()

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

user_profile_updates_total = Counter(
    "user_profile_updates_total",
    "Total number of user profile update operations",
    registry=registry,
)

kyc_submissions_total = Counter(
    "kyc_submissions_total",
    "Total number of KYC profile submissions",
    ["status"],
    registry=registry,
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
