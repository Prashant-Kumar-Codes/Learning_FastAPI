# Module 03: FastAPI Endpoints, HTTP Methods & RESTful CRUD

A comprehensive guide to declaring routes, handling HTTP methods, utilizing semantic status codes, and structuring RESTful CRUD APIs.

---

## 11. Creating Endpoints & Basic GET Syntax

### Initializing the Application

Every FastAPI project begins by instantiating the `FastAPI` class:

```python
# main.py
from fastapi import FastAPI, status

app = FastAPI(
    title="Hospital Patient Management API",
    description="Backend service for managing patient records and appointments",
    version="1.0.0"
)

# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK, tags=["Health"])
def health_check() -> dict[str, str]:
    """
    Returns server operational status.
    """
    return {"status": "healthy", "version": "1.0.0"}

# Informational endpoint
@app.get("/about", status_code=status.HTTP_200_OK, tags=["General"])
async def about() -> dict[str, str]:
    return {"message": "Patients API service v1"}
```

### Starting the Uvicorn ASGI Server

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- `main`: The Python file `main.py`.
- `app`: The `FastAPI` instance inside `main.py`.
- `--reload`: Auto-reloads the server on file modifications (development only).

### Automatic Interactive Documentation
- **Swagger UI**: Visit `http://127.0.0.1:8000/docs` to test endpoints interactively.
- **ReDoc**: Visit `http://127.0.0.1:8000/redoc` for clean, publication-ready API documentation.

---

## 12. HTTP Methods, Semantic Status Codes & RESTful CRUD

### 12.1 HTTP Methods (Verbs)

RESTful APIs map standard HTTP methods to resource operations:

| HTTP Verb | Operation | REST Meaning | Safe? | Idempotent? |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | Read | Retrieve a resource representation without modifying server state. | **Yes** | **Yes** |
| **POST** | Create | Create a new resource or trigger an action with side effects. | No | No |
| **PUT** | Replace | Completely replace the resource at the target URL. | No | **Yes** |
| **PATCH**| Update | Apply partial modifications to a resource. | No | No / Contextual |
| **DELETE**| Delete | Remove the targeted resource. | No | **Yes** |

> **Definitions**:
> - **Safe**: Does not alter server state (GET, HEAD, OPTIONS).
> - **Idempotent**: Making $N \ge 1$ identical requests results in the exact same server state as making 1 request (GET, PUT, DELETE).

---

### 12.2 Semantic HTTP Status Codes

FastAPI provides status constants via `fastapi.status` to eliminate magic numbers:

```python
from fastapi import status
```

#### 2xx — Success
- `status.HTTP_200_OK`: Default success code for `GET`, `PUT`, or `PATCH`.
- `status.HTTP_201_CREATED`: Returned by `POST` when a new entity is successfully created.
- `status.HTTP_204_NO_CONTENT`: Returned by `DELETE` when an entity is deleted and no response body is sent.

#### 3xx — Redirection
- `status.HTTP_301_MOVED_PERMANENTLY`: Resource has permanently moved to a new URI.
- `status.HTTP_307_TEMPORARY_REDIRECT`: Resource temporarily resides under a different URI.

#### 4xx — Client Error
- `status.HTTP_400_BAD_REQUEST`: General client-side error (malformed request, invalid logic).
- `status.HTTP_401_UNAUTHORIZED`: Authentication missing or token invalid.
- `status.HTTP_403_FORBIDDEN`: Authenticated, but lacking permission/role.
- `status.HTTP_404_NOT_FOUND`: Resource with the specified identifier does not exist.
- `status.HTTP_409_CONFLICT`: State conflict (e.g., trying to create a patient with an existing ID/email).
- `status.HTTP_422_UNPROCESSABLE_ENTITY`: Automatic FastAPI validation error (type mismatch, schema validation failure).

#### 5xx — Server Error
- `status.HTTP_500_INTERNAL_SERVER_ERROR`: Unhandled exception in backend code.
- `status.HTTP_502_BAD_GATEWAY`: Reverse proxy received an invalid response from upstream server.
- `status.HTTP_503_SERVICE_UNAVAILABLE`: Server overloaded or temporarily down.

---

### 12.3 What is CRUD?

**CRUD** maps database operations to RESTful HTTP endpoints:

```
Operation       HTTP Method    Endpoint Example           Status Code
---------------------------------------------------------------------
Create          POST           /patients                  201 Created
Read (Collection) GET          /patients                  200 OK
Read (Item)     GET            /patients/{patient_id}     200 OK
Update (Full)   PUT            /patients/{patient_id}     200 OK
Update (Partial) PATCH         /patients/{patient_id}     200 OK
Delete          DELETE         /patients/{patient_id}     204 No Content
```

### Raising `HTTPException`

```python
from fastapi import HTTPException, status

# Note: The argument name is 'detail', NOT 'detials'
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Patient '{patient_id}' does not exist in the database."
)
```

---

## 13. Dynamic API Endpoints & Route Matching

Dynamic routes capture values directly from the URL path:

```python
from fastapi import FastAPI, HTTPException, status

app = FastAPI()

PATIENTS = {
    "P001": {"name": "Alice", "city": "Delhi"},
    "P002": {"name": "Bob", "city": "Mumbai"}
}

@app.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    if patient_id not in PATIENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient ID '{patient_id}' not found."
        )
    return PATIENTS[patient_id]
```

### Route Declaration Order (Precedence)

FastAPI evaluates routes sequentially in the **exact order they appear in source code**:

```python
# 1. SPECIFIC (Static) Route MUST come FIRST
@app.get("/patients/me")
def get_current_patient_profile():
    return {"profile": "Active logged-in patient"}

# 2. GENERAL (Dynamic) Route MUST come SECOND
@app.get("/patients/{patient_id}")
def get_patient_by_id(patient_id: str):
    return {"patient_id": patient_id}
```

> **Warning**: If `/patients/{patient_id}` were placed before `/patients/me`, a request to `/patients/me` would match the dynamic route first, assigning the string `"me"` to `patient_id`.
