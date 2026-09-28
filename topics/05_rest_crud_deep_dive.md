# Module 05: Deep Dive: REST CRUD Operations (POST, PUT, PATCH, DELETE)

A comprehensive guide to implementing standard HTTP mutation verbs with clean semantics, idempotency guarantees, and production code examples in FastAPI.

---

## 17. Deep Dive: RESTful Mutation Methods

In REST architectures, data mutations are governed by standard HTTP verbs. Understanding the semantic differences between `POST`, `PUT`, `PATCH`, and `DELETE` prevents subtle API design bugs.

### Summary Comparison Table

| HTTP Verb | Operation | Idempotent? | Safe? | Typical Success Status | Request Body? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **POST** | Create resource / Action | **No** (calling $N$ times creates $N$ records) | No | `201 Created` | **Yes** |
| **PUT** | Complete replacement | **Yes** (calling $N$ times leaves identical state) | No | `200 OK` or `204 No Content` | **Yes** (full entity) |
| **PATCH**| Partial update | **No** (contextual; e.g. append operations) | No | `200 OK` | **Yes** (subset of fields) |
| **DELETE**| Removal of resource | **Yes** (resource stays deleted after first call) | No | `204 No Content` or `200 OK` | Optional (typically No) |

---

## 17.1 POST: Resource Creation

`POST` is used to create a new subordinate resource under a collection URI (e.g. `POST /patients`), or to submit processing commands that have side effects.

### Semantic Rules for POST
1. **Non-Idempotent**: Submitting the same `POST /patients` request twice with identical data must create two distinct records (with different generated IDs), unless an explicit business rule enforces uniqueness (which returns `409 Conflict`).
2. **Status Code**: Return `201 Created` upon successful generation.
3. **Location Header**: In strict REST, return a `Location` response header indicating the URI of the newly created entity (e.g., `Location: /patients/P003`).

### Complete POST Example

```python
import uuid
from fastapi import FastAPI, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="POST Example")

# Database simulation
PATIENT_DB: dict[str, dict] = {}

class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Ananya Roy"])
    age: int = Field(..., gt=0, le=120, examples=[29])
    diagnosis: str = Field(..., min_length=3, max_length=200, examples=["Hypertension"])

class PatientOut(PatientCreate):
    id: str

@app.post(
    "/patients",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient record"
)
def create_patient(payload: PatientCreate, response: Response):
    # 1. Generate unique server-side identifier
    patient_id = f"P{len(PATIENT_DB) + 1:03d}"

    # 2. Serialize Pydantic payload to dictionary and attach ID
    new_patient = payload.model_dump()
    new_patient["id"] = patient_id

    # 3. Store record in database
    PATIENT_DB[patient_id] = new_patient

    # 4. Set Location header pointing to the created resource
    response.headers["Location"] = f"/patients/{patient_id}"

    return new_patient
```

---

## 17.2 PUT: Complete Resource Replacement

`PUT` replaces the **entire representation** of a target resource at the specified URI.

### Semantic Rules for PUT
1. **Full Representation**: The client must send all required fields for the entity. Any field omitted by the client is reset to its default value or cleared.
2. **Idempotency**: Executing `PUT /patients/P001` once has the exact same side-effect as executing it 100 times.
3. **PUT vs. PATCH**:
   - `PUT`: *"Replace this entire patient object with this new payload."*
   - `PATCH`: *"Update only the patient's phone number; leave everything else untouched."*
4. **Status Codes**:
   - `200 OK`: Returns the updated resource.
   - `204 No Content`: Resource updated, but no body returned.
   - `404 Not Found`: Target resource does not exist (unless designing an upsert where PUT creates if missing).

### Complete PUT Example

```python
from fastapi import FastAPI, HTTPException, Path, status
from pydantic import BaseModel, Field

app = FastAPI(title="PUT Example")

PATIENT_DB: dict[str, dict] = {
    "P001": {"id": "P001", "name": "Rahul Verma", "age": 30, "city": "Delhi"}
}

class PatientPutSchema(BaseModel):
    """Full replacement schema: every field is mandatory."""
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., gt=0, le=120)
    city: str = Field(..., min_length=2, max_length=50)

class PatientOut(PatientPutSchema):
    id: str

@app.put(
    "/patients/{patient_id}",
    response_model=PatientOut,
    status_code=status.HTTP_200_OK,
    summary="Completely replace patient record"
)
def replace_patient(
    patient_id: str = Path(..., pattern=r"^P\d{3}$"),
    payload: PatientPutSchema = ...
):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found."
        )

    # Completely overwrite existing record (preserving unchanged primary key)
    updated_record = payload.model_dump()
    updated_record["id"] = patient_id
    PATIENT_DB[patient_id] = updated_record

    return updated_record
```

---

## 17.3 PATCH: Partial Resource Update

When you only need to change one or two fields of an entity (e.g. updating a patient's city without re-sending their name and age), use `PATCH`.

### Key FastAPI Pattern: `model_dump(exclude_unset=True)`
If a client sends `{"city": "Pune"}`, Pydantic's default `model_dump()` would include `name=None, age=None`, inadvertently wiping out existing fields.
By passing `exclude_unset=True`, Pydantic only extracts fields that were **explicitly sent** in the incoming JSON request.

```python
from fastapi import FastAPI, HTTPException, Path, status
from pydantic import BaseModel, Field

app = FastAPI(title="PATCH Example")

PATIENT_DB: dict[str, dict] = {
    "P001": {"id": "P001", "name": "Rahul Verma", "age": 30, "city": "Delhi"}
}

class PatientPatchSchema(BaseModel):
    """Partial schema: all fields are optional."""
    name: str | None = Field(default=None, min_length=2, max_length=100)
    age: int | None = Field(default=None, gt=0, le=120)
    city: str | None = Field(default=None, min_length=2, max_length=50)

class PatientOut(BaseModel):
    id: str
    name: str
    age: int
    city: str

@app.patch(
    "/patients/{patient_id}",
    response_model=PatientOut,
    status_code=status.HTTP_200_OK,
    summary="Partially update patient fields"
)
def patch_patient(
    patient_id: str = Path(..., pattern=r"^P\d{3}$"),
    payload: PatientPatchSchema = ...
):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found."
        )

    # 1. Extract only the fields supplied by client
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body cannot be empty for PATCH update."
        )

    # 2. Mutate existing stored entity
    record = PATIENT_DB[patient_id]
    record.update(update_data)
    PATIENT_DB[patient_id] = record

    return record
```

---

## 17.4 DELETE: Resource Deletion

`DELETE` removes the resource targeted by the request URI.

### Semantic Rules for DELETE
1. **Idempotent**: Calling `DELETE /patients/P001` once deletes the record. Calling it again leaves the system in a state where the record does not exist. (In HTTP semantics, the second call can return `404 Not Found` or `204 No Content`; both are standard, but returning `404` communicates that the resource is already absent).
2. **Status Code**:
   - `204 No Content`: The standard RESTful return code when no response body is sent. FastAPI automatically handles omitting the `Content-Type` and body.
   - `200 OK`: Used if you choose to return the deleted item or a confirmation dictionary like `{"detail": "Record deleted"}`.

### Complete DELETE Example

```python
from fastapi import FastAPI, HTTPException, Path, Response, status

app = FastAPI(title="DELETE Example")

PATIENT_DB: dict[str, dict] = {
    "P001": {"id": "P001", "name": "Rahul Verma", "age": 30, "city": "Delhi"},
    "P002": {"id": "P002", "name": "Sara Khan", "age": 25, "city": "Mumbai"},
}

# Style A: Production REST standard (204 No Content)
@app.delete(
    "/patients/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a patient (returns 204)"
)
def delete_patient(patient_id: str = Path(..., pattern=r"^P\d{3}$")):
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' does not exist."
        )

    # Remove item from persistence layer
    del PATIENT_DB[patient_id]

    # Return empty response for 204
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Style B: Alternative returning confirmation message (200 OK)
@app.delete(
    "/v2/patients/{patient_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a patient with JSON confirmation"
)
def delete_patient_with_message(patient_id: str = Path(..., pattern=r"^P\d{3}$")) -> dict[str, str]:
    if patient_id not in PATIENT_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' does not exist."
        )

    del PATIENT_DB[patient_id]
    return {"message": f"Patient '{patient_id}' successfully removed."}
```
