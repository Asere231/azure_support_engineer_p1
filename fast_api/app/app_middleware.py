import time
import logging
from fastapi import FastAPI, status, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.exceptions import UserRegistrationError, InvalidCredentialsError
from app.dao import UserDAO
from app.auth_util import create_token, validate_token

# Azure middleware logging.
import os
from azure.identity import DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient

from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%{asctime}s - %{levelname}s - %{message}s")

user_dao = UserDAO()

app = FastAPI(title="FastAPI P1")
security = HTTPBearer()

class AuthRequestBody(BaseModel):
    username: str = Field(..., examples=["hello"])
    password: str = Field(..., examples=["blank_text"])

class TokenResponseBody(BaseModel):
    access_token: str
    token_type: str

# Middleware Logger goes here.

# Configure synchronous Azure client.
endpoint    = 'https://dce-middleware-j5hv.koreasouth-1.ingest.monitor.azure.com' # os.environ['DATA_COLLECTION_ENDPOINT']
rule_id     = 'dcr-390659561e7642938342b240fc3382eb' # os.environ['LOGS_DCR_RULE_ID']
stream_name = 'Custom-JWT_Auth_HTTP_Errors_CL' # os.environ['LOGS_DCR_STREAM_NAME']

credential  = DefaultAzureCredential()
logs_client = LogsIngestionClient(endpoint=endpoint, credential=credential, logging_enable=True)

# Things to try and capture:
# Failed HTTP requests.
# Registration of new users.

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Here's how this one works: it process the request first, then checks for
    # a failure. If one occured, we send a log to our LAW.
    try:
        response = await call_next(request)

    except HTTPException as e:
        logging.error("HTTPExcept, logging to Azure")
        # Send this execption to the LAW.
        timestamp = datetime.now(timezone.utc).isoformat()
        log_body = [{
            "TimeGenerated": timestamp,
            "HTTPCode": e.status_code,
            "Details": e.detail,
            "Computer": "vm-jwt-auth"
        }]
        logs_client.upload(rule_id=rule_id, stream_name=stream_name, logs=log_body)
        raise e
    
    except Exception as e:
        logging.error("Exception, logging to Azure")
        # Send this 500 execption to the LAW.
        timestamp = datetime.now(timezone.utc).isoformat()
        log_body = [{
            "TimeGenerated": timestamp,
            "HTTPCode": "500",
            "Details": str(e),
            "Computer": "vm-jwt-auth"
        }]
        logs_client.upload(rule_id=rule_id, stream_name=stream_name, logs=log_body)
        raise e
    # Else just return the response as normal.
    return response

async def ensure_token_is_valid(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token_str = credentials.credentials
    payload = validate_token(token_str)
    return {"identity": payload.get("sub")}

@app.post("/register", status_code=201)
async def register(payload: AuthRequestBody):
    try:
        user_dao.create_user(username=payload.username, password=payload.password)
        return {"status": "success", "detail": f"Account for user `{payload.username}` has been provisioned"}
    except UserRegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login", response_model=TokenResponseBody, status_code=200)
async def login(payload: AuthRequestBody):
    try:
        user_dao.validate_user(username=payload.username, password=payload.password)

        response_token = create_token(username=payload.username)
        return {
            "access_token": response_token,
            "token_type": "bearer"
        }
    except InvalidCredentialsError as e:
        logging.error("Invalid credentials")
        raise HTTPException(status_code=401, detail=str(e))
    