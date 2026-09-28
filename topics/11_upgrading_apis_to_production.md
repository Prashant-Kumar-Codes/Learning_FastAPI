# Module 11: Production-Grade API Architecture (Upgrading from Basic to Pro)

A comprehensive guide on taking an API from a single-file hackathon prototype to an enterprise-grade, maintainable, and observable production backend.

---

## 23. Upgrading APIs: From Prototype to Production

### Why Prototype Code Fails in Production
Beginner tutorials typically dump all models, endpoints, and database connections into a single `main.py` file with mock dictionaries. While easy for learning, this collapses under real-world constraints:
1. **Tight Coupling**: Database operations, input validation, and business logic are tangled in the same route handler function.
2. **Configuration Drift**: Hardcoded ports, database URLs, and secret keys make automated deployments impossible.
3. **Zero Observability**: When an endpoint throws a 500 error in production, without structured logs and correlation IDs, debugging is impossible.
4. **Untestable**: Monolithic routes cannot be easily unit-tested or mocked.

---

## 23.1 Production Architecture: Layered (3-Tier) Pattern

In professional backends, enforce **Separation of Concerns**:

```
[ Client Request ]
       |
       v
+--------------------------+
| 1. API / Router Layer    |  (Path params, request validation, HTTP status codes)
+--------------------------+
       |
       v
+--------------------------+
| 2. Service Layer (Logic) |  (Pure business rules, ML orchestrations, calculations)
+--------------------------+
       |
       v
+--------------------------+
| 3. Data / Repository     |  (SQL queries, cache lookups, database transactions)
+--------------------------+
       |
       v
[ Database / Storage / Model ]
```

### Enterprise Project Layout

```
hospital_backend/
├── app/
│   ├── api/                  # Route handlers (Controllers)
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   └── patients.py
│   │       └── router.py
│   ├── core/                 # App-wide configurations & utilities
│   │   ├── config.py         # Pydantic BaseSettings & env vars
│   │   ├── security.py       # Password hashing & JWT logic
│   │   └── logging.py        # Structured JSON logger
│   ├── db/                   # Database engine & session setup
│   │   ├── base.py
│   │   └── session.py
│   ├── models/               # SQLAlchemy ORM models (database tables)
│   │   └── patient.py
│   ├── schemas/              # Pydantic validation schemas (data contracts)
│   │   └── patient.py
│   ├── services/             # Core business logic
│   │   └── patient_service.py
│   └── main.py               # FastAPI factory & middleware mounting
├── tests/                    # Automated test suite
│   ├── conftest.py
│   └── test_patients.py
├── .env.example              # Sample environment variables
├── Dockerfile
└── requirements.txt
```

---

## 23.2 Centralized Settings with `pydantic-settings`

Never use raw `os.environ.get()` scattered across your codebase. Use `BaseSettings` to validate environment variables at startup:

```python
# app/core/config.py
from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Healthcare Core API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "hospital_db"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
```

---

## 23.3 Middleware: Correlation IDs & Request Timing

Every incoming request should receive a unique `X-Request-ID`. This ID is returned in the response header and attached to all log lines, allowing you to trace an entire distributed request.

```python
import time
import uuid
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Attach unique Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # 2. Measure execution duration
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000  # in ms

        # 3. Inject tracing headers into response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
        
        return response

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

---

## 23.4 Automated Testing with `pytest` and `httpx`

Production code is verified using automated test suites running against test databases:

```python
# tests/test_patients.py
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_create_and_get_patient():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test creation
        payload = {"name": "Test Patient", "age": 40, "city": "Delhi", "diagnosis": "Fever"}
        post_resp = await client.post("/api/v1/patients", json=payload)
        assert post_resp.status_code == 201
        data = post_resp.json()
        assert data["name"] == "Test Patient"
        created_id = data["id"]

        # Test retrieval
        get_resp = await client.get(f"/api/v1/patients/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == created_id
```

---

## 23.5 Production Health & Readiness Probes

Container orchestrators (Docker Swarm, Kubernetes) require health checks to decide whether to route traffic to a container or restart it:

```python
from fastapi import APIRouter, status
from sqlalchemy import text
from app.db.session import engine

router = APIRouter(tags=["Health"])

# Liveness probe: Is the web process running?
@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness():
    return {"status": "alive"}

# Readiness probe: Can the application actually talk to its database/cache?
@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}, status.HTTP_503_SERVICE_UNAVAILABLE
```
