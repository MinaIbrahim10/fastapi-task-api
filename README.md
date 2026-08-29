# FastAPI Task API — Supabase Authentication & Protected Routes

A FastAPI backend demonstrating production-style authentication and authorization using Supabase Auth.

This branch extends the original Task API with:

- user signup
- user login
- JWT access tokens
- refresh tokens
- protected routes
- reusable authentication dependencies
- role-based authorization
- logout
- refresh flow
- login rate limiting
- Swagger UI Bearer authentication
- automated security tests

## Architecture

```text
Client
  |
  | email + password
  v
FastAPI -----------------> Supabase Auth
  ^                            |
  |                            |
  | JWT / verified user        |
  +----------------------------+
```

Supabase acts as the Identity Provider.

Passwords are never stored or hashed by this application.

## Security Model

The API distinguishes authentication from authorization:

```text
401 Unauthorized
= the server cannot verify who you are

403 Forbidden
= the server knows who you are, but you are not allowed
```

Examples:

```text
Missing/invalid JWT -> 401
Authenticated non-admin -> 403
```

## Environment Variables

Create a local `.env` file:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-publishable-key
PORT=8000
```

The real `.env` file is ignored by Git.

A safe template is provided as:

```text
.env.example
```

Never commit:

- service-role keys
- secret keys
- access tokens
- refresh tokens
- passwords

## Setup

Clone the repository and switch to this branch:

```bash
git clone https://github.com/MinaIbrahim10/fastapi-task-api.git
cd fastapi-task-api
git switch w2-a4-supabase-auth
```

Create the environment:

```bash
python3.13 -m venv .venv-auth
source .venv-auth/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements-auth.txt
```

Create `.env` from the example:

```bash
cp .env.example .env
```

Then insert your own Supabase project URL and publishable key.

## Run

Start the application with:

```bash
uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## API Reference

| Method | Endpoint | Authentication | Purpose |
|---|---|---:|---|
| POST | `/auth/signup` | No | Create a Supabase user |
| POST | `/auth/login` | No | Login and receive access + refresh tokens |
| POST | `/auth/logout` | Bearer JWT | End the authenticated session |
| POST | `/auth/refresh` | Refresh token body | Obtain a fresh access token |
| GET | `/public/info` | No | Public information |
| GET | `/protected/profile` | Bearer JWT | Current authenticated user |
| GET | `/protected/dashboard` | Bearer JWT | Second protected route |
| GET | `/protected/admin` | Bearer JWT + admin role | Admin-only route |
| GET | `/auth/health` | No | Safe Supabase configuration health check |

The original Task API endpoints remain available on this branch as well.

## Signup

```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"StrongPassword123"}'
```

Successful signup:

```text
HTTP 201 Created
```

## Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"StrongPassword123"}'
```

Successful login returns:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Tokens should never be committed or logged.

## Protected Route

```bash
curl http://127.0.0.1:8000/protected/profile \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

A verified request returns safe user metadata.

Missing or malformed authentication returns:

```json
{
  "error": "Access token required"
}
```

An invalid or tampered token returns:

```json
{
  "error": "Invalid or expired token"
}
```

## Strict Bearer Parsing

The authentication dependency accepts the standard form:

```text
Authorization: Bearer <token>
```

Malformed variations are rejected, including:

```text
Authorization: <token>
Authorization: Basic <token>
Authorization: Bearer
Authorization: Bearer token extra
```

This prevents accidentally accepting malformed authentication headers.

## Reusable Authentication Dependency

Token verification is implemented once in a reusable FastAPI dependency.

That same guard protects:

```text
/protected/profile
/protected/dashboard
/protected/admin
/auth/logout
```

Adding another protected route does not require duplicating authentication logic.

## 401 vs 403

This project demonstrates both authentication and authorization failures.

### 401 Unauthorized

Returned when the identity cannot be trusted:

```text
missing token
malformed Bearer header
expired token
tampered token
invalid login
```

### 403 Forbidden

Returned when authentication succeeds but authorization fails.

For example:

```text
GET /protected/admin
```

A normal authenticated user receives:

```json
{
  "error": "Admin access required"
}
```

with:

```text
HTTP 403 Forbidden
```

## Refresh Tokens

Access tokens are intentionally short-lived.

The login response also provides a refresh token that can obtain a new access token:

```bash
curl -X POST http://127.0.0.1:8000/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"<REFRESH_TOKEN>"}'
```

A real Supabase test confirmed:

```text
refresh request -> 200
new access token -> created
new refresh token -> created
new access token -> protected profile returned 200
```

Short-lived access tokens reduce the useful lifetime of a stolen access credential, while refresh tokens allow a legitimate client to continue a session without repeatedly asking for a password.

## Logout Experiment

A real logout flow was tested against Supabase.

Observed result:

```text
login -> 200
protected route -> 200
logout -> 204
reuse the same access token -> 401
```

For this Supabase session, the logged-out token was rejected on the next verified request.

The important architectural point is that logout behavior depends on how the Identity Provider validates and revokes sessions. Applications should never assume that deleting a token on the client alone is equivalent to server-side session invalidation.

## Login Rate Limiting

Repeated failed login attempts are rate limited.

Current development policy:

```text
5 failed attempts within 60 seconds
```

Further attempts receive:

```text
HTTP 429 Too Many Requests
```

Example response:

```json
{
  "error": "Too many failed login attempts. Try again later."
}
```

Rate limiting belongs near login because authentication endpoints are common brute-force targets.

## JWT Notes

A JWT contains signed claims about a user/session.

Common claims can include:

```text
subject/user ID
issuer
audience
issued-at time
expiry time
authentication metadata
```

A JWT payload is encoded, not encrypted.

Anyone who possesses the token can decode and read its payload, which is why application secrets, passwords, and private credentials must never be stored inside JWT claims.

The signature protects integrity: modifying even one character causes verification to fail.

This was verified manually by modifying a real Supabase access token:

```text
valid token -> HTTP 200
tampered token -> HTTP 401
```

## Swagger UI

FastAPI exposes interactive documentation at:

```text
http://127.0.0.1:8000/docs
```

Protected routes use the `SupabaseJWT` HTTP Bearer security scheme.

Swagger displays lock icons beside protected routes and provides an **Authorize** button.

![Swagger UI with Supabase Bearer authentication](screenshots/auth-swagger.png)

## Real End-to-End Verification

The implementation was tested with a real Supabase project.

Verified flows:

```text
real signup -> success
real login -> 200
access token returned -> yes
refresh token returned -> yes

protected profile with valid token -> 200
protected profile with tampered token -> 401

protected dashboard -> 200
admin route with normal user -> 403

refresh flow -> 200
refreshed access token -> protected profile 200

logout -> 204
reuse token after logout -> 401

invalid refresh token -> 401
```

## Automated Tests

Run:

```bash
python -m pytest -q
```

Current verified result:

```text
31 passed
```

Tests cover:

- signup
- login
- invalid credentials
- input validation
- public route
- missing bearer token
- malformed bearer headers
- valid token verification
- invalid token rejection
- reusable protected-route dependency
- dashboard protection
- admin authorization
- 403 behavior
- logout
- refresh flow
- invalid refresh tokens
- login rate limiting
- Swagger UI availability
- OpenAPI Bearer security scheme
- protected-route lock metadata
- public-route OpenAPI behavior

## Security Decisions

### No custom password hashing

Supabase handles password storage and cryptography.

The backend does not implement password hashing itself.

### Token Safety

Access tokens and refresh tokens are never intentionally printed in application logs or committed to the repository.

### Publishable Key Only

The project uses the Supabase publishable/anon-style application key.

A `service_role` or secret key must never be used for this exercise.

### Secrets Stay Outside Git

`.env` is ignored and `.env.example` contains placeholders only.

## Project Structure

```text
fastapi-task-api/
├── main.py
├── auth_config.py
├── requirements-auth.txt
├── .env.example
├── .gitignore
├── README.md
├── screenshots/
│   └── auth-swagger.png
└── tests/
    ├── test_auth_stage1.py
    ├── test_auth_stage23.py
    ├── test_auth_stage4_extras.py
    └── test_auth_stage5_swagger.py
```

## Assignment Progress

Core stages:

- [x] Stage 0 — Supabase configuration
- [x] Stage 1 — Signup and login
- [x] Stage 2 — Public and protected gates
- [x] Stage 3 — Real JWT verification
- [x] Stage 4 — Reusable auth dependency and logout
- [x] Stage 5 — Swagger Bearer authentication
- [x] Stage 6 — README and publication preparation

Extras and stretch:

- [x] strict Bearer parsing
- [x] second protected route
- [x] real 403 authorization case
- [x] refresh-token flow
- [x] real logout experiment
- [x] login brute-force rate limiting
- [x] JWT security explanation
- [x] automated auth tests
- [x] OpenAPI security tests
- [x] safe auth configuration health endpoint
- [x] secret-management documentation

Stage 7 AI rematch will be documented after the hand-built implementation is complete.
