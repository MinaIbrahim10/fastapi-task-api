"""FastAPI authentication API backed by Supabase Auth."""

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class Credentials(BaseModel):
    email: str | None = None
    password: str | None = None


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None
    user_metadata: dict[str, Any] = {}


def _configuration() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be configured")
    if anon_key.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_ANON_KEY must not contain a secret key")
    return url, anon_key


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    url, anon_key = _configuration()
    app.state.supabase_url = url
    app.state.anon_key = anon_key
    app.state.http = httpx.AsyncClient(timeout=10.0)
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    title="Supabase Authentication API",
    description="Authentication endpoints using Supabase as the identity provider.",
    lifespan=lifespan,
)

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="Supabase access token",
    auto_error=False,
)


def _require_input(credentials: Credentials) -> tuple[str, str]:
    email = credentials.email.strip() if credentials.email else ""
    password = credentials.password if credentials.password else ""
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required",
        )
    return email, password


async def _supabase_request(
    request: Request,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: dict[str, str] | None = None,
) -> httpx.Response:
    headers = {
        "apikey": request.app.state.anon_key,
        "Content-Type": "application/json",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return await request.app.state.http.request(
            method,
            f"{request.app.state.supabase_url}/auth/v1{path}",
            headers=headers,
            json=json,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc


async def authenticated_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
) -> AuthenticatedUser:
    """Strictly parse and verify a Supabase bearer token."""
    if (
        credentials is None
        or credentials.scheme != "Bearer"
        or not credentials.credentials
        or credentials.credentials.strip() != credentials.credentials
        or any(character.isspace() for character in credentials.credentials)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = await _supabase_request(
        request, "GET", "/user", token=credentials.credentials
    )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = response.json()
        return AuthenticatedUser(
            id=user["id"],
            email=user.get("email"),
            user_metadata=user.get("user_metadata") or {},
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token response",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[AuthenticatedUser, Depends(authenticated_user)]


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(credentials: Credentials, request: Request) -> dict[str, Any]:
    email, password = _require_input(credentials)
    response = await _supabase_request(
        request, "POST", "/signup", json={"email": email, "password": password}
    )
    if response.status_code not in (status.HTTP_200_OK, status.HTTP_201_CREATED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user",
        )
    data = response.json()
    user = data.get("user") or data
    return {
        "id": user.get("id"),
        "email": user.get("email", email),
        "message": "User registered successfully",
    }


@app.post("/auth/login")
async def login(credentials: Credentials, request: Request) -> dict[str, str]:
    email, password = _require_input(credentials)
    response = await _supabase_request(
        request,
        "POST",
        "/token?grant_type=password",
        json={"email": email, "password": password},
    )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    data = response.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": access_token, "refresh_token": refresh_token}


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, user: CurrentUser) -> Response:
    del user
    authorization = request.headers.get("Authorization")
    token = authorization[len("Bearer ") :] if authorization else ""
    response = await _supabase_request(request, "POST", "/logout", token=token)
    if response.status_code not in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to sign out",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/public/info")
async def public_info() -> dict[str, str]:
    return {"message": "This is public information"}


@app.get("/protected/profile")
async def protected_profile(user: CurrentUser) -> dict[str, Any]:
    return {"user": user.model_dump()}


@app.get("/protected/dashboard")
async def protected_dashboard(user: CurrentUser) -> dict[str, Any]:
    return {
        "message": "Welcome to the protected dashboard",
        "user_id": user.id,
    }
