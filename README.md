# Login & Protect API

Week 4, Assignment 1 | FlyRank Backend Track | Md. Tamjid Hossain

This project continues my Week 3 FastAPI and PostgreSQL task API. It adds Supabase authentication: register an account, log in, read a private profile, and log out. The same verification dependency protects the profile, dashboard, and logout routes.

Supabase handles account storage, password hashing, and token signing. This API does not store passwords or implement its own cryptography.

## Setup and run

Requirements: Docker Desktop with Docker Compose, and a free Supabase project. Python 3.12+ is needed only for local development or tests.

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell).
2. Set `SUPABASE_URL` to your Supabase project URL and `SUPABASE_KEY` to its anon or publishable key. Never use a service-role or secret key.
3. In a practice project, turn off **Authentication > Sign In / Providers > Confirm email** for the immediate signup/login exercise. Otherwise, confirm the email before logging in. Keep confirmation enabled in a production project.
4. Set a local PostgreSQL password in both `POSTGRES_PASSWORD` and `DATABASE_URL`. The example `dev` password is for local practice only.
5. Run the complete stack with one command:

```sh
docker compose up --build
```

Open `http://localhost:3000/docs`. If port 3000 is already occupied, set `PORT=3001` in `.env`, then use `http://localhost:3001/docs`. The local verification run uses 3001 so the Week 3 server can keep running.

Compose creates the database and waits for it to become healthy before starting the API. Stop with `docker compose down`; the named database volume preserves existing tasks.

| Variable | Purpose |
| --- | --- |
| SUPABASE_URL | Your project's HTTPS URL |
| SUPABASE_KEY | Public anon/publishable project key |
| POSTGRES_USER | Local database username |
| POSTGRES_PASSWORD | Local development database password |
| POSTGRES_DB | Local database name |
| DATABASE_URL | PostgreSQL connection URL; host is `db` inside Compose |
| PORT | Host port; defaults to 3000 |

The real `.env` is ignored by Git and Docker. `.env.example` contains placeholders only. No user tokens should be copied into screenshots, commits, or logs.

## API reference

| Method | Endpoint | Bearer token? | Success | Common errors |
| --- | --- | --- | --- | --- |
| POST | /auth/signup | No | 201, safe user object | 400 invalid/missing input |
| POST | /auth/login | No | 200, access and refresh tokens | 400 missing input, 401 rejected credentials |
| POST | /auth/logout | Yes | 204, empty body | 401 missing/invalid token |
| GET | /protected/profile | Yes | 200, id/email/created_at | 401 missing/invalid token |
| GET | /public/info | No | 200, public message | - |
| GET | /protected/dashboard | Yes | 200, welcome message/user ID | 401 missing/invalid token |

Authentication-service outages return 503 instead of pretending that valid credentials are wrong. Errors use a JSON `error` field. A 401 from a protected route also sends `WWW-Authenticate: Bearer`.

The original `/tasks` CRUD routes, `/`, and `/health` remain available. **The legacy tasks are still shared public practice data.** Authentication is applied to the assignment's protected endpoints; this is not yet a private per-user task service. Tenant isolation belongs to the next assignment.

## Try the full flow

These are Bash curl examples. In PowerShell, use `curl.exe` and a JSON file with `--data-binary @file.json` if inline quoting is inconvenient. Use your chosen port and a disposable test email.

```sh
curl -i -X POST http://localhost:3000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"student@example.com","password":"Example-only-Long-Password!"}'

curl -i -X POST http://localhost:3000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"student@example.com","password":"Example-only-Long-Password!"}'

curl -i http://localhost:3000/protected/profile \
  -H 'Authorization: Bearer PASTE_ACCESS_TOKEN'

curl -i http://localhost:3000/protected/dashboard \
  -H 'Authorization: Bearer PASTE_ACCESS_TOKEN'

curl -i http://localhost:3000/public/info

curl -i -X POST http://localhost:3000/auth/logout \
  -H 'Authorization: Bearer PASTE_ACCESS_TOKEN'
```

Check that signup is 201, login is 200, authenticated profile is 200, and logout is an empty 204. Also try an empty password (400), no Authorization header (401), a Basic header (401), and a modified JWT signature (401). Never test tampering by changing only padding bits; change a meaningful character in the signature.

An editable request collection is in `examples/auth.http`.

## Swagger UI

1. Open `/docs`, expand **POST /auth/signup**, choose **Try it out**, and register a test user.
2. Run **POST /auth/login** with the same credentials.
3. Copy only the `access_token` value. Click **Authorize** and paste it without the `Bearer ` prefix.
4. Run **GET /protected/profile** and **GET /protected/dashboard**. Both should return 200.
5. Run **POST /auth/logout**; it should return 204.
6. Clear authorization, then call the profile again to see a 401.

The Swagger page and its bearer controls were inspected. The final browser Authorize + Try it out checkpoint and screenshot remain pending after browser automation was blocked on localhost. The successful live curl checks do not replace that browser checkpoint.

## Why the guard is reusable

`require_user` parses the header and calls Supabase `get_user(token)`. It rejects a malformed header before trusting a token and rejects any token Supabase cannot verify. A successful response supplies the verified user to each route through FastAPI's dependency system. Profile and dashboard do not contain separate authentication checks.

Each request gets a separate Supabase client with session persistence and automatic refresh disabled. This prevents one caller's login from becoming another caller's server-side session.

## What logout actually does

Logout calls the SDK's JWT-taking `auth.admin.sign_out(token, scope="local")`, which posts the verified caller's access token to Supabase's logout endpoint. Despite the SDK namespace, this operation uses the caller's JWT and the project's public key, not a service-role key. It avoids calling session-based `sign_out()` on a fresh client, which could silently do nothing.

Supabase invalidates that session's refresh token. An already-issued access JWT may continue to work until its expiry. Clients must discard their local access and refresh tokens after logout. The API does not claim instant JWT revocation and does not keep an in-memory token blacklist that disappears on restart.

## Tests and evidence

```sh
python -m venv .venv
# Activate the environment, then:
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The automated suite uses FastAPI's real request handling and the real Supabase SDK with a simulated HTTP transport. It checks input validation, safe response fields, rejected credentials, bearer parsing, remote verification requests, service failures, caller-specific logout, empty 204 responses, and OpenAPI security. These automated tests do not replace live Supabase tests.

See `docs/verification-summary.md` for the current verification status and `docs/test-results.txt` for the saved test output. Old Week 3 evidence is kept in `docs/week3/` and is not presented as evidence for the new auth flow.

## Project structure

```text
app/main.py          Existing task routes, error handlers, Swagger
app/auth_client.py   Environment loading and isolated Supabase client
app/auth_routes.py   Auth endpoints and reusable verification guard
app/repository.py    Existing PostgreSQL task storage
tests/               Automated regression and authentication tests
examples/auth.http   Manual authentication requests
docs/                Current verification evidence and previous-week archive
```

## Development history

The repository retains the Week 3 history. New commits record setup, signup/login, public and guarded routes, remote token verification, reusable protection/logout, Swagger, and submission documentation. Intermediate Stage 2 code fails closed until remote verification is implemented.

## References

- [Supabase Python Auth](https://supabase.com/docs/reference/python/auth-api)
- [Supabase get_user](https://supabase.com/docs/reference/python/auth-getuser)
- [Supabase logout and JWT expiry](https://supabase.com/docs/reference/python/auth-signout)
- [FastAPI HTTPBearer](https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer)

Optional stretch features and the AI-rematch bonus are not claimed as completed.
