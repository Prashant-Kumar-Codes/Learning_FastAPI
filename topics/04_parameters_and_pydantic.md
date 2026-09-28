# Module 04: Validation, Parameters & Pydantic Schemas

A comprehensive guide to input validation using `Path()`, `Query()`, and Pydantic `BaseModel` schemas in FastAPI.

---

## 14. Using `Path()` for Validation & Metadata

The `Path()` function from `fastapi` allows you to add validation constraints, metadata, and documentation to path parameters.

### Syntax & Constraints

```python
from fastapi import FastAPI, Path, status

app = FastAPI()

@app.get("/patients/{patient_id}", status_code=status.HTTP_200_OK)
def get_patient(
    patient_id: str = Path(
        ...,  # Ellipsis indicates the parameter is required
        title="Patient Identifier",
        description="Unique patient code formatted as 'P' followed by 3 digits",
        pattern=r"^P\d{3}$",    # Regex validation
        examples=["P001", "P042"]
    )
):
    return {"patient_id": patient_id}
```

### Numeric Constraints
For integer and floating point path parameters:
- `ge`: Greater than or equal to (`>=`)
- `gt`: Greater than (`>`)
- `le`: Less than or equal to (`<=`)
- `lt`: Less than (`<`)

```python
@app.get("/wards/{ward_id}/beds/{bed_number}")
def get_bed(
    ward_id: int = Path(..., ge=1, le=50, description="Ward number between 1 and 50"),
    bed_number: int = Path(..., gt=0, lt=100, description="Bed number between 1 and 99")
):
    return {"ward_id": ward_id, "bed_number": bed_number}
```

---

## 15. Using `Query()` for Filtering, Sorting & Pagination

### Path vs. Query Parameters

| Feature | Path Parameter (`/patients/{id}`) | Query Parameter (`/patients?city=Delhi`) |
| :--- | :--- | :--- |
| **URL Placement** | Part of the path hierarchy. | Appended after `?` as `key=value` pairs. |
| **Semantic Role** | Identifies a specific, unique resource. | Filters, sorts, or paginates a resource collection. |
| **Optionality** | Always mandatory. | Typically optional with default values. |

### Query Parameter Syntax

```
GET /patients?city=Delhi&sort_by=age&order=desc&limit=10&offset=0
             ^          ^           ^          ^        ^
             |          +-----------+----------+--------+--> Query pairs separated by '&'
             +--> '?' denotes beginning of query string
```

### Declaring Query Parameters in FastAPI

```python
from typing import Literal
from fastapi import FastAPI, Query, status

app = FastAPI()

@app.get("/patients", status_code=status.HTTP_200_OK)
def list_patients(
    # Optional filter
    city: str | None = Query(
        default=None,
        min_length=2,
        max_length=50,
        description="Filter records by city"
    ),
    # Required query parameter using '...'
    sort_by: Literal["age", "height", "weight"] = Query(
        ...,
        description="Field to sort by"
    ),
    # Default value parameter
    order: Literal["asc", "desc"] = Query(
        default="asc",
        description="Sort direction"
    ),
    # Pagination
    limit: int = Query(default=10, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset")
):
    return {
        "city": city,
        "sort_by": sort_by,
        "order": order,
        "limit": limit,
        "offset": offset
    }
```

### Multi-Value / List Query Parameters
Clients can pass repeated query parameters (e.g., `?departments=cardio&departments=neuro`):

```python
@app.get("/search")
def search_departments(
    departments: list[str] = Query(
        default=[],
        description="Pass multiple department filters"
    )
):
    return {"filters": departments}
```

---

## 16. Working with POST, Request Bodies & Pydantic

### 16.1 What is an HTTP Request Body?

An HTTP Request Body contains the data sent from the client to the server in `POST`, `PUT`, or `PATCH` requests. It is typically transmitted as a JSON-encoded string with `Content-Type: application/json`.

---

### 16.2 Defining Data Models with Pydantic `BaseModel`

Pydantic models declare data schemas using standard Python type annotations. FastAPI uses these models to:
1. Parse raw incoming JSON into validated Python objects.
2. Generate automatic OpenAPI specifications.
3. Return informative `422 Unprocessable Entity` errors when validation fails.

```python
from typing import Literal
from pydantic import BaseModel, Field, EmailStr

class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Jane Doe"])
    email: EmailStr = Field(..., description="Contact email address")
    city: str = Field(..., min_length=2, max_length=50, examples=["Delhi"])
    age: int = Field(..., gt=0, le=120, description="Age must be between 1 and 120")
    gender: Literal["male", "female", "other"]
    height_cm: float = Field(..., gt=30.0, lt=260.0)
    weight_kg: float = Field(..., gt=2.0, lt=400.0)

class PatientResponse(PatientCreate):
    id: str = Field(..., description="Unique generated patient identifier")
```

---

### 16.3 The `response_model` Pattern

Setting `response_model` in the endpoint decorator ensures **security and contract enforcement**:
- It guarantees the output adheres to the specified schema.
- It automatically filters out unexposed attributes (such as internal DB IDs, password hashes, or sensitive flags).

```python
import uuid
from fastapi import FastAPI, status

app = FastAPI()
DATABASE: dict[str, dict] = {}

@app.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"]
)
def create_patient(payload: PatientCreate):
    new_id = f"P_{uuid.uuid4().hex[:6].upper()}"
    
    # model_dump() converts Pydantic model to a standard Python dict
    patient_record = payload.model_dump()
    patient_record["id"] = new_id

    DATABASE[new_id] = patient_record
    return patient_record
```

---

### 16.4 Complete, Production-Grade REST CRUD Reference

Below is a complete, runnable module integrating routes, semantic status codes, `Path`, `Query`, and Pydantic validation:

```python
from typing import Literal
from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

app = FastAPI(title="Patients Management System")

# ----------------- SCHEMAS -----------------
class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., gt=0, le=120)
    city: str = Field(..., min_length=2, max_length=50)

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    age: int | None = Field(default=None, gt=0, le=120)
    city: str | None = Field(default=None, min_length=2, max_length=50)

class PatientOut(PatientBase):
    id: str

# ----------------- MOCK DATASTORE -----------------
PATIENT_DB: dict[str, dict] = {
    "P001": {"id": "P001", "name": "Aarav Sharma", "age": 28, "city": "Delhi"},
    "P002": {"id": "P002", "name": "Diya Patel", "age": 34, "city": "Mumbai"},
}

# ----------------- ENDPOINTS -----------------

# 1. CREATE (POST)
@app.post("/patients", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(patient: PatientCreate):
    new_id = f"P{len(PATIENT_DB) + 1:03d}"
    record = patient.model_dump()
    record["id"] = new_id
    PATIENT_DB[new_id] = record
    return record

# 2. READ ALL / FILTER (GET)
@app.get("/patients", response_model=list[PatientOut], status_code=status.HTTP_200_OK)
def list_patients(
    city: str | None = Query(default=None, description="Filter by city"),
    order: Literal["asc", "desc"] = Query(default="asc", description="Sort by age")
):
    results = list(PATIENT_DB.values())
    if city:
        results = [p for p in results if p["city"].lower() == city.lower()]
    
    # Correct reverse boolean assignment
    is_descending = (order == "desc")
    results = sorted(results, key=lambda x: x["age"], reverse=is_descending)
    return results

# 3. READ ONE / PATH (GET)
@app.get("/patients/{patient_id}", response_model=PatientOut, status_code=status.HTTP_200_OK)
def get_patient(
    patient_id: str = Path(..., pattern=r"^P\d{3}$", description="Patient ID (e.g. P001)")
):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found."
        )
    return PATIENT_DB[patient_id]

# 4. PARTIAL UPDATE (PATCH)
@app.patch("/patients/{patient_id}", response_model=PatientOut, status_code=status.HTTP_200_OK)
def update_patient(
    patient_id: str = Path(..., pattern=r"^P\d{3}$"),
    updates: PatientUpdate = ...
):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found."
        )
    
    record = PATIENT_DB[patient_id]
    # exclude_unset=True ensures only explicitly passed fields are updated
    update_data = updates.model_dump(exclude_unset=True)
    record.update(update_data)
    PATIENT_DB[patient_id] = record
    return record

# 5. DELETE (DELETE)
@app.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: str = Path(..., pattern=r"^P\d{3}$")):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found."
        )
    del PATIENT_DB[patient_id]
    return None
```
