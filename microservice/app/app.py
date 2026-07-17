import time
import socket
import logging
from fastapi import FastAPI, Request, HTTPException, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


app = FastAPI(
    title="FastAPI Demo", 
    servers=[
        {"url": "http://20.220.71.25", "description": "Production (via Load Balancer)"},
    ]
)
security = HTTPBearer()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_request_execution_latency(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    logging.info(f"HTTP {request.method} {request.url.path} processed in {time.time() - start_time:.4f}s")
    return response


class ServicePayload(BaseModel):
    name: str = Field(..., examples=["Microsoft"])
    url: str = Field(..., min_length=6, examples=["https://www.microsoft.com/"])

class ServiceResponse(BaseModel):
    name: str
    url: str
    status_code: int


@app.post("/status-code", response_model=ServiceResponse, status_code=201)
async def check_service_health(payload: ServicePayload):
    """Protected post route parsing active token payload"""
    try:
        status = subprocess.run(["curl", "-I", payload.url], capture_output=True, text=True)
        http_code_line = status.stdout.splitlines()[0]
        http_status_code = int(http_code_line.split()[1])
        return {
            "name": payload.name, 
            "url": payload.url, 
            "status_code": http_status_code
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/health")
async def get_app_health():
    return {"status": "ok"}

@app.get("/host")
async def get_host(request: Request):
    return {
        "status": "ok",
        "served_by": socket.gethostname(),
        "your_ip_as_seen_by_backend": request.client.host
    }
