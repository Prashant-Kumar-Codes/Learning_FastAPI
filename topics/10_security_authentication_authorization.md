# Module 10: Security, Authentication & Production Hardening

A comprehensive guide to securing FastAPI backends: JWT authentication, password hashing with bcrypt, role-based access control (RBAC), CORS middleware, and rate limiting.

---

## 22. Why Backend Security is Non-Negotiable

A backend API is the front door to your databases and ML models. If security is an afterthought:
1. **Broken Authentication**: Attackers can impersonate other users or doctors.
2. **Data Exposure (IDOR)**: Changing an ID in the URL allows unauthorized users to read confidential medical records.
3. **Denial of Service / Brute-Force**: Scripted bots exhaust server CPU and lock databases.
4. **Credential Leakage**: Storing plaintext passwords compromises user accounts across other services.

---

## 22.1 Password Hashing with Bcrypt

Never store plaintext passwords or weak hashes (MD5, SHA-1). Use salted algorithms like **bcrypt** or **argon2**.

```python
# security.py
from passlib.context import CryptContext

# Configure password context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Generate salted bcrypt hash."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify raw password against stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

---

## 22.2 OAuth2 with Password Flow & JWT Tokens

In REST APIs, authentication is stateless. The client sends login credentials, receives a signed **JSON Web Token (JWT)**, and passes the token in the `Authorization: Bearer <token>` header for subsequent requests.

```
Client                      FastAPI Backend
  |                                |
  |-- POST /auth/login (u/p) ----->| Verify password hash
  |<-- 200 OK (JWT Access Token) --| Sign JWT with SECRET_KEY
  |                                |
  |-- GET /patients (Bearer JWT) ->| Verify signature & expiration
  |<-- 200 OK (Patient Data) ------| If valid, grant access
```

### Complete Implementation

```python
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration (In production, load via environment variables!)
SECRET_KEY = "SUPER_SECRET_CHANGE_ME_IN_PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

app = FastAPI(title="Security & JWT Demo")

# Mock User Database
MOCK_USERS_DB = {
    "doctor_sharma": {
        "username": "doctor_sharma",
        "hashed_password": pwd_context.hash("DoctorSecure123!"),
        "role": "doctor"
    },
    "patient_aarav": {
        "username": "patient_aarav",
        "hashed_password": pwd_context.hash("PatientPass456!"),
        "role": "patient"
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfile(BaseModel):
    username: str
    role: str

# Helper: Create signed JWT token
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Dependency: Extract & validate JWT from request header
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserProfile:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None or username not in MOCK_USERS_DB:
            raise credentials_exception
        user_dict = MOCK_USERS_DB[username]
        return UserProfile(username=user_dict["username"], role=user_dict["role"])
    except jwt.PyJWTError:
        raise credentials_exception

# ================= ENDPOINTS =================

# 1. Login Endpoint to acquire Token
@app.post("/api/v1/auth/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = MOCK_USERS_DB.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return Token(access_token=access_token, token_type="bearer")

# 2. Protected Endpoint (Any Authenticated User)
@app.get("/api/v1/users/me", response_model=UserProfile)
async def read_users_me(current_user: Annotated[UserProfile, Depends(get_current_user)]):
    return current_user
```

---

## 22.3 Role-Based Access Control (RBAC)

Not all authenticated users have identical privileges. An RBAC dependency gate prevents patients from accessing doctor-only routes:

```python
class RequireRole:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Annotated[UserProfile, Depends(get_current_user)]) -> UserProfile:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {self.allowed_roles}"
            )
        return current_user

# Doctor-only endpoint
@app.get(
    "/api/v1/prescriptions/all",
    dependencies=[Depends(RequireRole(["doctor", "admin"]))]
)
async def get_all_prescriptions():
    return {"message": "Access granted: sensitive prescriptions list."}
```

---

## 22.4 CORS Configuration (Cross-Origin Resource Sharing)

When your frontend (e.g. `http://localhost:3000` or `https://app.hospital.com`) calls your backend on `https://api.hospital.com`, the browser blocks it unless CORS headers are explicitly granted.

```python
from fastapi.middleware.cors import CORSMiddleware

# Production CORS: Explicitly whitelist allowed domains
ALLOWED_ORIGINS = [
    "http://localhost:3000",       # Next.js / React dev server
    "https://hospital-portal.com", # Production web app
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # NEVER use ["*"] in production with credentials!
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

> [!WARNING]
> Setting `allow_origins=["*"]` allows any malicious website visited by your users to execute authenticated requests against your backend via Cross-Origin attacks. Always whitelist exact origin domains.

---

## 22.5 Rate Limiting with SlowAPI

Rate limiting protects your login, search, and ML inference endpoints from brute-force attacks and abuse.

```python
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Initialize limiter by client IP address
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Protect login: limit to 5 attempts per minute per IP
@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login(request: Request):
    return {"message": "Processed"}
```
