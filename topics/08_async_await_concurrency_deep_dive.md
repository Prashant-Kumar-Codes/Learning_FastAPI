# Module 08: Asynchronous Python & Concurrency in FastAPI

A deep dive into Python's Event Loop, the mechanics of `async`/`await`, how FastAPI routes synchronous vs. asynchronous endpoints, and how to manually manage concurrency.

---

## 20. The Mechanics of `async` and `await`

FastAPI is an ASGI framework built on `asyncio`. To write scalable backends, you must understand what happens under the hood when a request arrives.

### The Single-Threaded Event Loop
Traditional WSGI frameworks (like Flask or Django on Gunicorn) handle concurrency by spawning multiple OS processes or worker threads. If a thread waits on a database query for 200ms, that thread is completely idle and blocked.

In contrast, Python's `asyncio` runs a **single thread** with an **Event Loop**:
1. When a task reaches an `await` expression (e.g. awaiting an async DB call, network request, or redis cache), it **yields control** back to the event loop.
2. The event loop switches execution to another pending HTTP request.
3. When the I/O operation finishes, the event loop resumes the original task.

```
Request 1:  [Execute] ---> await db_query() (pauses) ------> [Resume & Return]
                                   \
Event Loop:                         v Switches
Request 2:                     [Execute] ---> await cache_get() (pauses)
```

---

## 20.1 `def` vs. `async def` in FastAPI: The Hidden Mechanism

FastAPI handles `def` and `async def` differently. Choosing the wrong one can stall your entire server.

| Declaration | Where FastAPI Executes It | Use Case | Fatal Mistake |
| :--- | :--- | :--- | :--- |
| `async def endpoint()` | Directly on the **main Event Loop** thread | Calling non-blocking async libraries (`asyncpg`, `aiofiles`, `httpx.AsyncClient`) | Putting blocking synchronous calls (`time.sleep`, `requests.get`, `torch.infer`) inside `async def`. It freezes all requests! |
| `def endpoint()` | In an external **Threadpool** (`starlette.concurrency`) | Calling legacy synchronous libraries (`sqlite3`, `requests`, `pandas`, PyTorch) | Overusing for simple async I/O; adds thread context-switching overhead. |

> [!CAUTION]
> **The Golden Rule**:
> - If you use `async def`, you **MUST NEVER** call blocking synchronous operations inside it.
> - If you must use synchronous libraries (e.g., standard `requests`, `time.sleep`, heavy NumPy/Torch operations), declare the endpoint as normal `def`, OR offload it manually.

---

## 20.2 What Happens When You Block the Event Loop?

```python
# DANGEROUS CODE - DO NOT DO THIS
import time
from fastapi import FastAPI

app = FastAPI()

@app.get("/bad-async")
async def bad_endpoint():
    # This blocks the single event loop thread for 5 seconds!
    # No other user can be served during these 5 seconds!
    time.sleep(5)
    return {"message": "Delayed"}
```
If 10 users hit `/bad-async` simultaneously, the 10th user waits 50 seconds!

---

## 20.3 How to Offload Blocking Tasks Manually

When you are already inside an `async def` function (or an async pipeline) and need to call a CPU-bound or blocking synchronous function, you must offload it to a threadpool.

### Method 1: `anyio.to_thread.run_sync` / `starlette.concurrency.run_in_threadpool`
FastAPI internally uses Starlette's `run_in_threadpool`:

```python
import time
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

app = FastAPI()

def blocking_cpu_or_io_task(patient_id: str, iterations: int) -> dict:
    """Simulates a heavy blocking calculation or synchronous SDK call."""
    time.sleep(2)  # Synchronous blocking call
    result = sum(i * i for i in range(iterations))
    return {"patient_id": patient_id, "score": result}

@app.get("/process/{patient_id}")
async def process_patient(patient_id: str):
    # Manually offload the blocking function to the external threadpool
    result = await run_in_threadpool(blocking_cpu_or_io_task, patient_id, 1_000_000)
    return {"status": "success", "result": result}
```

### Method 2: Standard Python `asyncio.to_thread` (Python 3.9+)
In standard Python 3.9+, you can use `asyncio.to_thread()` directly:

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()

def synchronous_file_read(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/read-config")
async def read_config():
    # Executes synchronous_file_read in a separate worker thread
    content = await asyncio.to_thread(synchronous_file_read, "README.md")
    return {"bytes_read": len(content)}
```

---

## 20.4 Parallel Concurrency with `asyncio.gather`

If an endpoint needs to fetch data from three independent external APIs or services, running them sequentially wastes time:
- Sequential: $100\text{ms} + 100\text{ms} + 100\text{ms} = 300\text{ms}$
- Concurrent: $\max(100\text{ms}, 100\text{ms}, 100\text{ms}) = 100\text{ms}$

```python
import asyncio
import httpx
from fastapi import FastAPI

app = FastAPI()

async def fetch_user_data(client: httpx.AsyncClient, user_id: str) -> dict:
    await asyncio.sleep(0.1) # Simulating network call
    return {"id": user_id, "name": "Aarav"}

async def fetch_user_orders(client: httpx.AsyncClient, user_id: str) -> list:
    await asyncio.sleep(0.1) # Simulating network call
    return [{"order_id": "ORD-1"}, {"order_id": "ORD-2"}]

async def fetch_user_notifications(client: httpx.AsyncClient, user_id: str) -> int:
    await asyncio.sleep(0.1) # Simulating network call
    return 3

@app.get("/dashboard/{user_id}")
async def get_dashboard(user_id: str):
    async with httpx.AsyncClient() as client:
        # Run all three async tasks concurrently!
        profile, orders, notifs = await asyncio.gather(
            fetch_user_data(client, user_id),
            fetch_user_orders(client, user_id),
            fetch_user_notifications(client, user_id)
        )

    return {
        "profile": profile,
        "orders": orders,
        "unread_notifications": notifs
    }
```
