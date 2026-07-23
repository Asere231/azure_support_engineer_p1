import time
import logging
from fastapi import FastAPI, status, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.exceptions import UserRegistrationError, InvalidCredentialsError
from app.dao import UserDAO
from app.auth_util import create_token, validate_token

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
    