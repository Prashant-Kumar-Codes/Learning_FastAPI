# Module 12: High-Performance APIs for Machine Learning & Deep Learning

A specialized guide for AI/ML engineers on serving PyTorch, Hugging Face, Scikit-learn, and computer vision models using FastAPI.

---

## 24. Why ML/DL Serving is Fundamentally Different

Traditional web APIs are **I/O-bound**: they spend 95% of their time waiting for database queries or network responses. The CPU remains mostly idle.

Machine Learning APIs are **Compute-bound and Memory-heavy**:
1. **Massive Memory Footprints**: Weights for a deep learning model or vision transformer occupy hundreds of megabytes to several gigabytes of RAM or GPU VRAM.
2. **Heavy CPU/GPU Saturation**: Executing matrix multiplications (forward passes) maxes out CPU cores or GPU tensor cores.
3. **Event Loop Starvation Risk**: Running a synchronous PyTorch forward pass inside an `async def` route will **block the entire ASGI event loop**, preventing any other HTTP request from being handled.

---

## 24.1 Application Lifespan: Loading Models Once

> [!CAUTION]
> **The #1 Anti-Pattern**: Never load a model weights file (`.pt`, `.onnx`, `.joblib`) inside a route handler!
> Doing so means every incoming request re-reads gigabytes from disk into memory, causing massive latency and immediate Out-Of-Memory (OOM) crashes.

Use FastAPI's modern **Lifespan Context Manager** to load models into memory during server startup and release them during shutdown:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import torch
import torchvision.models as models

class ModelContainer:
    """Holds loaded ML models and metadata."""
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def load(self):
        # 1. Load model architecture & weights
        self.model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        # 2. Set to evaluation mode (disables dropout, fixes batchnorm)
        self.model.eval()
        self.model.to(self.device)
        
        # 3. Model Warm-up (executes initial CUDA kernel compilation)
        dummy_input = torch.randn(1, 3, 224, 224, device=self.device)
        with torch.no_grad():
            _ = self.model(dummy_input)
        print(f"ML Model loaded successfully on {self.device}")

    def unload(self):
        # Cleanly release CUDA VRAM
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        print("Model unloaded.")

model_container = ModelContainer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    model_container.load()
    app.state.ml_model = model_container
    yield
    # SHUTDOWN
    model_container.unload()

app = FastAPI(title="ML Serving API", lifespan=lifespan)
```

---

## 24.2 Non-Blocking Inference with `run_in_threadpool`

Because model inference is CPU/GPU intensive, offload the forward pass to a threadpool so FastAPI can continue processing other concurrent requests:

```python
import io
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image
from pydantic import BaseModel
import torch
import torchvision.transforms as transforms

class PredictionResponse(BaseModel):
    class_id: int
    confidence: float

# Image Preprocessing Pipeline
preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def run_synchronous_inference(image_bytes: bytes, container) -> PredictionResponse:
    """
    Synchronous CPU/GPU heavy function.
    Must be executed inside an offloaded worker thread!
    """
    # 1. Open image from in-memory bytes
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(image).unsqueeze(0).to(container.device)

    # 2. Execute inference under torch.no_grad()
    with torch.no_grad():
        logits = container.model(tensor)
        probabilities = torch.nn.functional.softmax(logits[0], dim=0)
        confidence, class_id = torch.max(probabilities, dim=0)

    return PredictionResponse(
        class_id=int(class_id.item()),
        confidence=float(confidence.item())
    )

@app.post(
    "/api/v1/predict/vision",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK
)
async def predict_image(
    request: Request,
    file: UploadFile = File(..., description="JPEG/PNG image file")
):
    # 1. Validate MIME type
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Only JPEG and PNG are supported."
        )

    # 2. Read bytes asynchronously
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large.")

    # 3. Offload blocking compute to threadpool
    container = request.app.state.ml_model
    prediction = await run_in_threadpool(run_synchronous_inference, image_bytes, container)
    return prediction
```

---

## 24.3 Serving Tabular Data & Features (Batch Validation)

For classic tabular models (XGBoost, Scikit-Learn, LightGBM), define strict feature vectors:

```python
from typing import Annotated
from fastapi import FastAPI
import numpy as np
from pydantic import BaseModel, Field

app = FastAPI()

class PatientFeatures(BaseModel):
    age: int = Field(..., ge=1, le=120)
    systolic_bp: int = Field(..., ge=50, le=250, description="Systolic Blood Pressure (mmHg)")
    cholesterol: float = Field(..., ge=50.0, le=500.0, description="Serum Cholesterol (mg/dL)")
    smoker: bool

class RiskScoreResponse(BaseModel):
    risk_probability: float
    high_risk: bool

@app.post("/api/v1/predict/cardiac-risk", response_model=RiskScoreResponse)
async def predict_cardiac_risk(features: PatientFeatures):
    # Convert validated schema directly into NumPy array shape (1, n_features)
    feature_vector = np.array([[
        features.age,
        features.systolic_bp,
        features.cholesterol,
        int(features.smoker)
    ]], dtype=np.float32)

    # Simulate ML model scoring
    # In real app: model.predict_proba(feature_vector)
    mock_score = float(1 / (1 + np.exp(- (features.age * 0.03 + features.cholesterol * 0.01 - 3.5))))
    
    return RiskScoreResponse(
        risk_probability=round(mock_score, 4),
        high_risk=(mock_score > 0.65)
    )
```

---

## 24.4 Handling Long-Running Inference: Asynchronous Task Queues

If an inference job takes more than 1–2 seconds (e.g., video processing, 3D medical CT segmentations, audio transcription), holding the HTTP connection open causes client timeouts and gateway 504 errors.

### The Job Polling Pattern
1. Client submits task: `POST /api/v1/segmentation/jobs` -> Returns `202 Accepted` with `{"job_id": "job_991"}`.
2. Background worker (Celery / Redis Queue) picks up the job and executes inference.
3. Client polls: `GET /api/v1/segmentation/jobs/job_991` -> Returns `{"status": "PENDING"}` or `{"status": "COMPLETED", "result": {...}}`.

```python
import uuid
from fastapi import BackgroundTasks, FastAPI, status
from pydantic import BaseModel

app = FastAPI()

JOBS: dict[str, dict] = {}

class JobResponse(BaseModel):
    job_id: str
    status: str

def run_heavy_inference_task(job_id: str, payload_data: str):
    import time
    # Simulating 5-second heavy model run
    time.sleep(5)
    JOBS[job_id] = {
        "status": "COMPLETED",
        "result": {"segmentation_mask_url": f"https://cdn.hospital.com/masks/{job_id}.png"}
    }

@app.post("/api/v1/jobs/segmentation", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_segmentation_job(payload: str, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "PROCESSING", "result": None}

    # Queue background execution
    background_tasks.add_task(run_heavy_inference_task, job_id, payload)

    return JobResponse(job_id=job_id, status="PROCESSING")

@app.get("/api/v1/jobs/segmentation/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in JOBS:
        return {"error": "Job not found"}, 404
    return JOBS[job_id]
```
