# Module 06: Professional REST API Naming & URL Design

A production-grade guide to designing intuitive, scalable, and standard-compliant API routes in FastAPI.

---

## 18. Professional API Naming Conventions

Poor URI naming causes confusion, client bugs, and messy backend routers. Modern industry standards (Stripe, GitHub, AWS, Google Cloud) follow strict REST guidelines.

### Core Principles

| Principle | Correct Pattern | Anti-Pattern | Reason |
| :--- | :--- | :--- | :--- |
| **Use Nouns, Not Verbs** | `GET /patients` | `GET /getPatients` | The HTTP method (`GET`) is already the verb. Adding verbs creates redundancy. |
| **Use Plural Resources** | `GET /patients`, `POST /patients` | `GET /patient` | The endpoint represents a collection of resources, not just one. |
| **Lowercase & Hyphens** | `GET /medical-records` | `GET /medical_records`, `/medicalRecords` | URLs are case-insensitive on some proxies; kebab-case is web standard. |
| **Consistent Sub-Resources** | `GET /patients/{id}/appointments` | `GET /getAppointmentsByPatientId` | Reflects true hierarchical data relationships. |
| **No CRUD in Paths** | `DELETE /patients/{id}` | `POST /patients/delete` | HTTP verbs control the mutation. |

---

## 18.1 Standard Route Mappings Across Major Situations

### 1. Simple Resource Collection & Single Items
```
GET    /api/v1/patients             # Retrieve paginated list of patients
POST   /api/v1/patients             # Create a new patient
GET    /api/v1/patients/{id}        # Retrieve specific patient
PUT    /api/v1/patients/{id}        # Replace full patient record
PATCH  /api/v1/patients/{id}        # Partially update patient
DELETE /api/v1/patients/{id}        # Delete specific patient
```

### 2. Nested Sub-Resources (Hierarchical Relationships)
When a child resource cannot exist without its parent, nest it under the parent URI:
```
GET    /api/v1/patients/{patient_id}/prescriptions            # List prescriptions for patient
POST   /api/v1/patients/{patient_id}/prescriptions            # Add prescription to patient
GET    /api/v1/patients/{patient_id}/prescriptions/{presc_id} # Get specific prescription
DELETE /api/v1/patients/{patient_id}/prescriptions/{presc_id} # Delete specific prescription
```

> **Design Tip (Avoid Deep Nesting)**:
> Never nest deeper than 2 levels (e.g. avoid `/hospitals/{id}/wards/{id}/patients/{id}/prescriptions/{id}`). If resources become deeply nested, flatten them: `/api/v1/prescriptions/{presc_id}`.

### 3. Non-CRUD Operations (Actions & Controller Verbs)
Sometimes an API operation does not fit cleanly into simple CRUD (e.g. logging in, approving an invoice, initiating an ML prediction, or canceling an appointment).
In professional APIs, use sub-resource action verbs with `POST`:

```
POST   /api/v1/auth/login                  # User authentication / token generation
POST   /api/v1/auth/logout                 # Invalidate session/token
POST   /api/v1/appointments/{id}/cancel   # Business action on existing resource
POST   /api/v1/invoices/{id}/pay           # State transition
POST   /api/v1/models/ecg-classifier/predict # Trigger ML inference
```

---

## 18.2 API Versioning Strategies

Never deploy production APIs without versioning. When requirements change, breaking changes can be made under `/v2/` without crashing legacy mobile apps or external integrations.

| Versioning Method | Example | Production Recommendation |
| :--- | :--- | :--- |
| **URI Path (Standard)** | `https://api.domain.com/v1/patients` | **Strongly Recommended**: Clear, browser-testable, easily routed by reverse proxies (Nginx/Traefik). |
| **Header-Based** | `Accept: application/vnd.company.v1+json` | Used by GitHub; harder to test manually in browser and documentation. |
| **Query Parameter** | `/patients?version=1` | Not recommended; leads to cache pollution. |

---

## 18.3 Modular Routing with `APIRouter`

In professional applications, never dump all routes into a single `main.py`. Organize them modularly using `APIRouter`.

### Directory Structure
```
app/
├── main.py
└── api/
    └── v1/
        ├── api.py            # Aggregates all v1 routers
        └── endpoints/
            ├── auth.py       # Authentication routes
            ├── patients.py   # Patient CRUD routes
            └── ml_models.py  # Model inference routes
```

### Code Example: `app/api/v1/endpoints/patients.py`
```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/patients", tags=["Patients"])

class PatientSchema(BaseModel):
    name: str
    age: int

@router.get("", status_code=status.HTTP_200_OK)
def list_patients():
    return [{"id": "P001", "name": "Aarav"}]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientSchema):
    return {"id": "P002", **payload.model_dump()}

@router.get("/{patient_id}", status_code=status.HTTP_200_OK)
def get_patient(patient_id: str):
    return {"id": patient_id, "name": "Aarav"}
```

### Code Example: `app/main.py`
```python
from fastapi import FastAPI
from app.api.v1.endpoints import auth, patients, ml_models

app = FastAPI(title="Production Healthcare Backend", version="1.0.0")

# Mount routers under unified versioned prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(ml_models.router, prefix="/api/v1")
```
This produces clean, structured endpoints:
- `/api/v1/patients`
- `/api/v1/patients/{patient_id}`
- `/api/v1/auth/login`
- `/api/v1/models/ecg-classifier/predict`
