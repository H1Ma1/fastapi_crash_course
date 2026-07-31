import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.exceptions import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import User


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


if not GOOGLE_CLIENT_ID:
    raise RuntimeError("Не найдена переменная GOOGLE_CLIENT_ID")

if not JWT_SECRET_KEY:
    raise RuntimeError("Не найдена переменная JWT_SECRET_KEY")


bearer_scheme = HTTPBearer(auto_error=False)


def verify_google_token(credential: str) -> dict:
    try:
        google_user = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except ValueError as error:
        print("GOOGLE TOKEN ERROR:", error)

        raise HTTPException(
            status_code=401,
            detail="Недействительный Google token",
        )
    google_id = google_user.get("sub")
    email = google_user.get("email")

    if not google_id or not email:
        raise HTTPException(
            status_code=401,
            detail="Google token не содержит нужные данные пользователя",
        )

    return {
        "google_id": google_id,
        "email": email,
        "name": google_user.get("name"),
        "picture": google_user.get("picture"),
    }


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
    except PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Недействительный или просроченный token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Нужно войти в аккаунт",
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Token не содержит пользователя",
        )

    user = await session.get(User, int(user_id))

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Пользователь не найден",
        )

    return user