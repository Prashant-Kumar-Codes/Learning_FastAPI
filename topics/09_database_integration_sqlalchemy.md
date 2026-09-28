# Module 09: Database Integration (SQLAlchemy 2.0 & Async Engine)

A complete guide to integrating relational databases with FastAPI using modern SQLAlchemy 2.0, asynchronous sessions, dependency injection, and complete CRUD operations.

---

## 21. Merging FastAPI with a Database

In production systems, data must persist across server restarts, handle concurrent multi-user transactions safely, and scale via indexing and connection pooling.

### Why Use an ORM (SQLAlchemy 2.0)?
1. **Prevents SQL Injection**: Queries are parameterized automatically. You never concatenate user strings into raw SQL.
2. **Object-Relational Mapping**: Maps database table rows to Python objects with type hints.
3. **Connection Pooling**: Reuses a pool of open DB connections instead of establishing a new TCP connection on every request (which destroys latency).
4. **Session Management & Unit of Work**: Groups operations into atomic database transactions (ACID guarantees).

### The Two-Model Architecture: Schemas vs. Models
A common beginner confusion is mixing Pydantic models with SQLAlchemy models:

```
[ HTTP Request (JSON) ]
         |
         v
+------------------------+
| Pydantic Schema        |  <-- Boundary Validation & Serialization
| (PatientCreate)        |      (Runtime type checks, Field constraints)
+------------------------+
         |
         v
+------------------------+
| SQLAlchemy ORM Model   |  <-- Persistence & Database Mapping
| (PatientModel)         |      (Tables, Columns, Foreign Keys, Indexes)
+------------------------+
         |
         v
[ Relational Database (PostgreSQL / SQLite) ]
```

---

## 21.1 Setting Up the Async Database Engine & Session

Using modern SQLAlchemy 2.0 with asynchronous SQLite (`aiosqlite`) or PostgreSQL (`asyncpg`).

```python
# database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Use SQLite for local development (or postgresql+asyncpg://user:pass@localhost/dbname)
DATABASE_URL = "sqlite+aiosqlite:///./hospital.db"

# 1. Create Async Engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True to print generated SQL statements to terminal
    future=True
)

# 2. Session factory configured for async commits
async_session_factory = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession
)

# 3. Base class for all ORM models
class Base(DeclarativeBase):
    pass

# 4. Dependency Injection function for route handlers
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an active database session for the request lifecycle,
    ensuring it is safely closed when the request finishes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## 21.2 Defining the ORM Model & Pydantic Schemas

### SQLAlchemy 2.0 Model (`models.py`)
```python
# models.py
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Pydantic Validation Schemas (`schemas.py`)
```python
# schemas.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., gt=0, le=120)
    city: str = Field(..., min_length=2, max_length=50)
    diagnosis: str = Field(..., min_length=2, max_length=200)

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    age: int | None = Field(default=None, gt=0, le=120)
    city: str | None = Field(default=None, min_length=2, max_length=50)
    diagnosis: str | None = Field(default=None, min_length=2, max_length=200)

class PatientResponse(PatientBase):
    id: int
    created_at: datetime

    # Enable ORM mode so Pydantic can read attributes from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)
```

---

## 21.3 Complete, Production CRUD Operations (`main.py`)

Here is the complete, runnable FastAPI application executing all database operations:

```python
# main.py
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, engine, get_db
from models import Patient
from schemas import PatientCreate, PatientResponse, PatientUpdate

# Lifespan event to create database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables (in production, use Alembic migrations instead)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown logic: dispose engine pool
    await engine.dispose()

app = FastAPI(title="FastAPI + SQLAlchemy 2.0 Async CRUD", lifespan=lifespan)

# Type alias for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]

# ================= 1. CREATE (POST) =================
@app.post(
    "/api/v1/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"]
)
async def create_patient(payload: PatientCreate, db: DbSession):
    # Instantiate ORM object from validated Pydantic schema
    db_patient = Patient(**payload.model_dump())
    db.add(db_patient)
    await db.commit()
    await db.refresh(db_patient)  # Loads auto-generated ID & timestamp
    return db_patient

# ================= 2. READ ALL / PAGINATED & FILTERED (GET) =================
@app.get(
    "/api/v1/patients",
    response_model=list[PatientResponse],
    status_code=status.HTTP_200_OK,
    tags=["Patients"]
)
async def list_patients(
    db: DbSession,
    city: str | None = Query(default=None, description="Filter by city"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    query = select(Patient)
    if city:
        query = query.where(Patient.city.ilike(f"%{city}%"))
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    patients = result.scalars().all()
    return patients

# ================= 3. READ ONE BY ID (GET) =================
@app.get(
    "/api/v1/patients/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    tags=["Patients"]
)
async def get_patient(patient_id: int, db: DbSession):
    query = select(Patient).where(Patient.id == patient_id)
    result = await db.execute(query)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} does not exist."
        )
    return patient

# ================= 4. PARTIAL UPDATE (PATCH) =================
@app.patch(
    "/api/v1/patients/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    tags=["Patients"]
)
async def update_patient(patient_id: int, payload: PatientUpdate, db: DbSession):
    query = select(Patient).where(Patient.id == patient_id)
    result = await db.execute(query)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found."
        )

    # Extract only passed fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return patient

# ================= 5. DELETE (DELETE) =================
@app.delete(
    "/api/v1/patients/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Patients"]
)
async def delete_patient(patient_id: int, db: DbSession):
    query = select(Patient).where(Patient.id == patient_id)
    result = await db.execute(query)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found."
        )

    await db.delete(patient)
    await db.commit()
    return None
```

---

## 21.4 Database Migrations with Alembic

In real projects, you never drop tables or run `create_all()` in production when schemas change. You use **Alembic** to generate incremental migration scripts:

```bash
# 1. Initialize Alembic environment
alembic init alembic

# 2. Generate migration script by detecting model diffs
alembic revision --autogenerate -m "create patients table"

# 3. Apply migration to DB
alembic upgrade head
```
This preserves your production data when adding columns or altering indexes.
