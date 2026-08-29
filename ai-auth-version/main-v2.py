"""FastAPI authentication API backed by the official Supabase SDK."""

import os
import re
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from supabase import Client, create_client


app = FastAPI(title="Supabase Authentication API")

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="Supabase access token",
    auto_error=False,
)


class Credentials(BaseModel):
    email: str
    password: str


class SafeUser(BaseModel):
    id: str
    email: str | None = None
    user_metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class Authentication:
    user: SafeUser
    token: str
    client: Client


class AuthenticationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


@app.exception_handler(RequestValidationError)
async def invalid_request_body(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request, exc
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Email and password are required"},
    )


@app.exception_handler(AuthenticationError)
async def authentication_error(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": exc.message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured")
    if key.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_KEY must be a public client key")
    return create_client(url, key)


def _required_credentials(credentials: Credentials) -> tuple[str, str]:
    email = credentials.email.strip()
    password = credentials.password
    if not email or not password:
        raise ValueError
    return email, password


def _bad_input() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Email and password are required"},
    )


def authenticate(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
    ) -> Authentication:
    """Strictly parse and remotely verify a Supabase bearer token."""
    authorization = request.headers.get("Authorization")
    if (
        authorization is None
        or re.fullmatch(r"Bearer [^\s]+", authorization) is None
        or credentials is None
        or credentials.scheme != "Bearer"
        or credentials.credentials != authorization[7:]
    ):
        raise AuthenticationError("Bearer token required")

    client = _supabase_client()
    try:
        response = client.auth.get_user(credentials.credentials)
        user = response.user
        if user is None:
            raise ValueError
        safe_user = SafeUser(
            id=str(user.id),
            email=user.email,
            user_metadata=user.user_metadata or {},
        )
    except Exception:
        raise AuthenticationError("Invalid or expired token")

    return Authentication(
        user=safe_user,
        token=credentials.credentials,
        client=client,
    )


CurrentAuthentication = Annotated[Authentication, Depends(authenticate)]


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: Credentials) -> Any:
    try:
        email, password = _required_credentials(credentials)
    except ValueError:
        return _bad_input()

    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        return _bad_input()

    try:
        response = _supabase_client().auth.sign_up(
            {"email": email, "password": password}
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Unable to register user"},
        )

    user = response.user
    return {
        "id": str(user.id) if user is not None else None,
        "email": user.email if user is not None else email,
        "message": "User registered successfully",
    }


@app.post("/auth/login")
def login(credentials: Credentials) -> Any:
    try:
        email, password = _required_credentials(credentials)
    except ValueError:
        return _bad_input()

    try:
        response = _supabase_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = response.session
        if session is None or not session.access_token or not session.refresh_token:
            raise ValueError
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Invalid login credentials"},
        )

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": session.token_type or "bearer",
        "expires_in": session.expires_in,
    }


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authentication: CurrentAuthentication) -> Response:
    authentication.client.auth.sign_out()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/public/info")
def public_info() -> dict[str, str]:
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile")
def protected_profile(authentication: CurrentAuthentication) -> dict[str, Any]:
    return {"user": authentication.user.model_dump()}


@app.get("/protected/dashboard")
def protected_dashboard(authentication: CurrentAuthentication) -> dict[str, str]:
    return {
        "message": "Welcome to the protected dashboard",
        "user_id": authentication.user.id,
    }
