# user-service

Owns user profile, address book, KYC, and preference data for the FinFlow platform. Authentication, token issuance, and password management belong exclusively to `auth-service`; this service only **validates** JWT access tokens issued by it.

---

## Architecture Overview

Clean/layered architecture, identical in shape to `auth-service`:

```
Request → Middleware (request-id, logging, metrics)
        → API layer (FastAPI routers, Pydantic validation)
        → Dependency injection (JWT auth, service factories)
        → Service layer (business rules, orchestration, metrics)
        → Repository layer (SQLAlchemy queries only)
        → PostgreSQL
```

Design principles:

- **Repository pattern** — all SQL lives in `app/repositories/*`; nothing above that layer constructs a query.
- **Service layer** — all business rules (default-address invariants, KYC state machine, auto-provisioning) live in `app/services/*`, independent of HTTP concerns.
- **No token issuance here** — `app/core/security.py` only decodes and validates; there is no `create_*_token` function in this codebase by design.
- **Lazy profile provisioning** — a `users` row is created on first authenticated request if one doesn't exist yet (`UserService.get_or_create_profile`), standing in for the `user.registered` event a full event-driven deployment would consume instead.
- **Database-per-service** — this service owns its own PostgreSQL database. `auth_user_id` is a logical reference to `auth-service`'s `auth_users.id`; there is no physical foreign key across service boundaries.

---

## Folder Structure

```
user-service/
├── alembic/
│   ├── env.py                  # async-aware Alembic environment
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── profile.py
│   │   │   ├── addresses.py
│   │   │   ├── kyc.py
│   │   │   ├── preferences.py
│   │   │   ├── notifications.py
│   │   │   └── health.py
│   │   ├── dependencies.py     # JWT auth + service DI wiring
│   │   └── router.py
│   ├── core/
│   │   ├── config.py           # env-driven Settings
│   │   ├── security.py         # JWT validation only
│   │   ├── exceptions.py       # domain exception taxonomy
│   │   ├── logging.py          # structured JSON logging
│   │   └── metrics.py          # Prometheus metric definitions
│   ├── db/
│   │   ├── base.py             # declarative base + mixins
│   │   ├── session.py          # async engine/session factory
│   │   └── models/              # users, addresses, kyc_profiles, user_preferences, notification_preferences
│   ├── repositories/           # one per aggregate, pure data access
│   ├── services/                # business logic + orchestration
│   ├── schemas/                 # Pydantic request/response DTOs
│   ├── middleware/              # request-id, access logging, Prometheus
│   └── main.py                  # app factory
├── tests/
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── pytest.ini
├── .env.example
└── README.md
```

---

## Database Schema

All tables live in this service's own PostgreSQL database (`user_service_db`). No physical foreign key crosses into `auth-service`'s database.

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | This service's own identifier |
| auth_user_id | UUID, unique | Logical reference to `auth-service.auth_users.id` |
| email | CITEXT | Cached copy for display/search; not authoritative |
| first_name / last_name | VARCHAR(100) | |
| phone_number | VARCHAR(20) | |
| date_of_birth | DATE | |
| profile_photo_url | VARCHAR(1024) | |
| status | ENUM(active, inactive, suspended, deleted) | |
| created_at / updated_at | TIMESTAMPTZ | |

### `addresses`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id (CASCADE) | |
| address_type | ENUM(residential, billing, business, shipping) | |
| line1 / line2 / city / state / postal_code | VARCHAR | |
| country | CHAR(2) | ISO-3166, enforced by CHECK constraint |
| is_default | BOOLEAN | Exactly one default enforced by service-layer logic |
| created_at / updated_at | TIMESTAMPTZ | |

### `kyc_profiles`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id (CASCADE), unique | 1:1 with user |
| kyc_status | ENUM(pending, in_review, verified, rejected) | |
| pan_number | VARCHAR(10) | Should be encrypted at rest in production (pgcrypto/KMS); always masked in API responses |
| aadhaar_last4 | VARCHAR(4), CHECK ~ `^[0-9]{4}$` | |
| verification_date | TIMESTAMPTZ | |
| created_at / updated_at | TIMESTAMPTZ | |

### `user_preferences`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id (CASCADE), unique | |
| language | VARCHAR(10), default `en` | |
| timezone | VARCHAR(50), default `UTC` | |
| currency | CHAR(3), default `USD` | |
| theme | ENUM(light, dark, system) | |
| created_at / updated_at | TIMESTAMPTZ | |

### `notification_preferences`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id (CASCADE), unique | |
| email_enabled / sms_enabled / push_enabled | BOOLEAN, default true | |
| created_at / updated_at | TIMESTAMPTZ | |

---

## API Documentation

All endpoints below (except `/health/*` and `/metrics`) require `Authorization: Bearer <access_token>` and are mounted under `API_V1_PREFIX` (default `/api/v1`).

### Profile
| Method | Path | Description |
|---|---|---|
| GET | `/users/me` | Get (and lazily provision) the current user's profile |
| PUT | `/users/me` | Update profile fields |

### Addresses
| Method | Path | Description |
|---|---|---|
| GET | `/users/me/addresses` | List all saved addresses |
| POST | `/users/me/addresses` | Add an address (first address is always forced default) |
| PUT | `/users/me/addresses/{address_id}` | Update an address |
| DELETE | `/users/me/addresses/{address_id}` | Delete an address (auto-promotes another to default if needed) |

### KYC
| Method | Path | Description |
|---|---|---|
| GET | `/users/me/kyc` | Get KYC status (PAN is always masked) |
| POST | `/users/me/kyc` | Submit KYC for the first time → `in_review` |
| PUT | `/users/me/kyc` | Amend KYC — only while `pending` or `rejected` |

### Preferences
| Method | Path | Description |
|---|---|---|
| GET | `/users/me/preferences` | Get display/locale preferences |
| PUT | `/users/me/preferences` | Update display/locale preferences |

### Notification Preferences
| Method | Path | Description |
|---|---|---|
| GET | `/users/me/notifications` | Get channel opt-ins |
| PUT | `/users/me/notifications` | Update channel opt-ins |

### Platform
| Method | Path | Description |
|---|---|---|
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe (checks DB connectivity) |
| GET | `/metrics` | Prometheus exposition format |

### Error Response Shape

Every error response (via `AppException` subclasses) follows this structure:

```json
{
  "type": "https://errors.finflow.com/kyc_already_submitted",
  "title": "Kyc Already Submitted",
  "status": 409,
  "detail": "A KYC profile already exists for this user; use PUT to amend it",
  "trace_id": "b3f1c2b0-1e2f-4a5b-9c3d-8e7f6a5b4c3d"
}
```

`trace_id` is the same value returned in the `x-request-id` response header.

---

## Local Development Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL and JWT_SECRET_KEY
# JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ISSUER, JWT_AUDIENCE must match auth-service exactly

createdb user_service_db
alembic upgrade head

uvicorn app.main:app --reload --port 8001
```

Interactive API docs: `http://localhost:8001/docs`

---

## Docker Setup

```bash
docker build -t finflow/user-service:latest .

docker run --rm -p 8001:8000 \
  --env-file .env \
  finflow/user-service:latest
```

The image is a non-root multi-stage build (`python:3.12-slim`), runs under `gunicorn` with `uvicorn.workers.UvicornWorker`, and exposes a container `HEALTHCHECK` against `/health/live`.

---

## Testing Instructions

```bash
createdb user_service_test_db
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://user_service:user_service_password@localhost:5432/user_service_db \
JWT_SECRET_KEY=test-secret-key-that-is-at-least-32-chars-long \
pytest -v
```

Test suite covers:
- Profile auto-provisioning, isolation between users, updates
- Address CRUD, default-address invariants, cross-user access denial
- KYC submission, duplicate-submission rejection, immutable-state enforcement, PAN masking
- JWT validation: missing/malformed/expired tokens, wrong issuer/audience, wrong token type
- Health and metrics endpoints, request-id propagation

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `user-service` | Service name, used in logs |
| `APP_ENV` | `development` | Environment label |
| `DEBUG` | `false` | FastAPI debug mode |
| `API_V1_PREFIX` | `/api/v1` | Versioned route prefix |
| `DATABASE_URL` | — (required) | `postgresql+asyncpg://user:pass@host:port/db` |
| `DB_POOL_SIZE` | `10` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | `20` | SQLAlchemy pool overflow |
| `DB_POOL_TIMEOUT` | `30` | Pool checkout timeout (seconds) |
| `DB_ECHO` | `false` | Log all SQL statements |
| `JWT_SECRET_KEY` | — (required, ≥32 chars) | Must match auth-service's signing key |
| `JWT_ALGORITHM` | `HS256` | Must match auth-service |
| `JWT_ISSUER` | `auth-service` | Must match auth-service's `iss` claim |
| `JWT_AUDIENCE` | `fintech-platform` | Must match auth-service's `aud` claim |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed origins |
| `LOG_LEVEL` | `INFO` | Root log level |

---

## Production Deployment Notes

- **Secrets**: `JWT_SECRET_KEY` and `DATABASE_URL` must come from a secrets manager (AWS Secrets Manager, GCP Secret Manager, Vault), never baked into the image.
- **PAN encryption at rest**: `kyc_profiles.pan_number` should be encrypted at the column level (pgcrypto or application-side KMS envelope encryption) before this service handles real PII at scale; this repo stores it in plaintext at the DB layer and masks only at the API boundary.
- **Migrations**: run `alembic upgrade head` as a separate release step/job before rolling out new application pods — never on container start in a multi-replica deployment (risk of concurrent migration races).
- **Connection pooling**: with multiple replicas, size `DB_POOL_SIZE` × replica count against PostgreSQL's `max_connections`, or front the database with PgBouncer in transaction-pooling mode.
- **Horizontal scaling**: the service is stateless (no in-memory session state); scale `gunicorn` workers and pod replica count independently based on `http_request_duration_seconds` and CPU.
- **Observability**: JSON logs are Loki-ready as-is; scrape `/metrics` with a Prometheus `ServiceMonitor` (or equivalent) on the container port.
- **Rate limiting / WAF**: apply at the API gateway/ingress layer, not in-service, to keep this service focused on domain logic.

---

## Future Kubernetes Deployment Notes

Not included in this repository by design (application code only), but the eventual manifests should account for:

- **Liveness probe** → `GET /health/live`, **readiness probe** → `GET /health/ready`, matching the container `HEALTHCHECK`.
- **HorizontalPodAutoscaler** driven by CPU and/or the `http_request_duration_seconds` Prometheus metric via a custom metrics adapter.
- **PodDisruptionBudget** to keep at least one replica available during node drains, given this is a synchronous, user-facing read path.
- **NetworkPolicy** restricting egress to only the PostgreSQL service/port and restricting ingress to the API gateway/mesh sidecar.
- **ConfigMap** for non-secret settings (`APP_ENV`, `LOG_LEVEL`, `CORS_ORIGINS`) and a **Secret** for `JWT_SECRET_KEY`/`DATABASE_URL`, mounted as environment variables matching this README's variable table.
- A separate **Job** or **initContainer**-free release hook to run `alembic upgrade head` prior to deployment rollout.
