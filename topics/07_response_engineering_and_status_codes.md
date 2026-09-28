# Module 07: Response Engineering & Error Handling

A guide to crafting predictable, type-safe, and standardized HTTP responses and global exception handlers in FastAPI.

---

## 19. Returning Responses the Professional Way

Returning ad-hoc raw dictionaries from endpoints leads to inconsistent client parsing, missing metadata, and exposed internal server leaks. A production backend guarantees structured response envelopes.

### The Four Pillars of Response Engineering
1. **`response_model` Filtering**: Strip sensitive internal fields (e.g. `hashed_password`, internal DB flags).
2. **Standardized Response Envelope**: Predictable structure (`success`, `data`, `message`, `meta`).
3. **Custom Exception Handlers**: Uniform error JSON formats across both validation (422) and business logic (4xx/5xx).
4. **Structured Pagination**: Always return items along with total count, page, and limit.

---

## 19.1 Using `response_model` to Filter Sensitive Data

FastAPI uses Pydantic's `response_model` to serialize data before sending it out. Any field present in the database object that is **not** declared in `response_model` is automatically removed.

```python
from fastapi import FastAPI, status
from pydantic import BaseModel, EmailStr

app = FastAPI()

# Internal Database Representation (contains private fields)
class UserInDB(BaseModel):
    id: str
    username: str
    email: EmailStr
    hashed_password: str
    is_admin: bool

# Public API Response Schema (sanitized)
class UserPublic(BaseModel):
    id: str
    username: str
    email: EmailStr

@app.get("/users/me", response_model=UserPublic)
def get_current_user():
    # Simulating DB record
    user_db = UserInDB(
        id="usr_123",
        username="prashant",
        email="user@example.com",
        hashed_password="argon2id$v=19$m=65536...secret",
        is_admin=True
    )
    # Even though user_db has hashed_password, FastAPI returns ONLY fields in UserPublic
    return user_db
```

---

## 19.2 Standardized JSON Response Envelope

Instead of returning raw arrays or raw dictionaries, wrap responses in a standardized envelope:

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class StandardResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T | None = None

class PaginatedMeta(BaseModel):
    total_records: int
    page: int
    page_size: int
    total_pages: int

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: list[T]
    meta: PaginatedMeta
```

### Implementing in Endpoints

```python
from fastapi import FastAPI, Query, status

app = FastAPI()

class PatientItem(BaseModel):
    id: str
    name: str

@app.get(
    "/api/v1/patients",
    response_model=PaginatedResponse[PatientItem],
    status_code=status.HTTP_200_OK
)
def get_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100)
):
    mock_db = [{"id": f"P{i:03d}", "name": f"Patient {i}"} for i in range(1, 45)]
    
    total = len(mock_db)
    start = (page - 1) * page_size
    items = mock_db[start : start + page_size]
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        success=True,
        message="Patients retrieved successfully.",
        data=items,
        meta=PaginatedMeta(
            total_records=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )
```

---

## 19.3 Global Exception Handlers for Unified Errors

When errors occur, clients shouldn't receive generic HTML pages or default unstructured traces. Catch exceptions globally with `@app.exception_handler`:

```python
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

# 1. Custom Business Logic Exception
class ResourceNotFoundException(Exception):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier

@app.exception_handler(ResourceNotFoundException)
async def handle_not_found(request: Request, exc: ResourceNotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "error_code": "RESOURCE_NOT_FOUND",
            "message": f"{exc.resource} with ID '{exc.identifier}' does not exist.",
            "path": str(request.url.path)
        }
    )

# 2. Overriding FastAPI's default 422 RequestValidationError
@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join([str(loc) for loc in err["loc"] if loc != "body"])
        errors.append({"field": field, "issue": err["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "VALIDATION_FAILED",
            "message": "Invalid request parameters or payload.",
            "errors": errors,
            "path": str(request.url.path)
        }
    )

@app.get("/items/{item_id}")
def get_item(item_id: str):
    if item_id != "valid_item":
        raise ResourceNotFoundException(resource="Item", identifier=item_id)
    return {"id": item_id}
```

---

## 19.4 Streaming Responses & File Downloads

For large payloads, generated files, or LLM token streaming, returning a monolithic JSON block causes high memory usage and latency. Use `StreamingResponse` or `FileResponse`.

```python
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

async def mock_llm_token_generator(prompt: str) -> AsyncGenerator[str, None]:
    words = f"Response to prompt: '{prompt}' streaming word by word from model.".split()
    for word in words:
        await asyncio.sleep(0.1)  # Simulate GPU token generation delay
        yield f"data: {word}\n\n"

@app.get("/api/v1/chat/stream")
async def stream_chat(prompt: str):
    return StreamingResponse(
        mock_llm_token_generator(prompt),
        media_type="text/event-stream"
    )
```
