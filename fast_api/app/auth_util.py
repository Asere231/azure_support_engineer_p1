import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "7bca9c84e2a3928e1d2c4b5d6e7f8a90123456789abcdef0123456789abcdef")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_MINUTES = 30

def create_token(username: str) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)

    payload =  {
        "sub": username,
        "iat": issued_at.timestamp(),
        "exp": expires_at.timestamp()
    }

    encoded_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_token

def validate_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please re-authenticate",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed or invalid authorization token signature",
            headers={"WWW-Authenticate": "Bearer"}
        )
