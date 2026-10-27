# Production Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a reproducible, version-controlled, production-safe build that serves the React application and FastAPI API from one container and is ready for Railway PostgreSQL.

**Architecture:** Local development keeps Vite and FastAPI separate, while the production image compiles React and serves it from FastAPI on one origin. Runtime validation rejects unsafe production settings, Alembic owns schema changes, and CI proves backend/frontend behavior from a clean checkout.

**Tech Stack:** Git/GitHub, Python 3.13, FastAPI, SQLModel, Alembic, Node 22, React/Vite, Docker, GitHub Actions, Railway

**Spec:** `docs/superpowers/specs/2026-10-27-production-pilot-design.md`

## Global Constraints

- Public deployment must set `DEBUG_AUTH_ENABLED=false`, `USE_MOCK_PROVIDERS=false`, `SESSION_COOKIE_SECURE=true`, and `AUTO_CREATE_TABLES=false`.
- Public frontend and `/api` must share one HTTPS origin.
- Secrets must never be committed, logged, placed in screenshots, or copied into documentation.
- Database migrations must run before application startup and block deployment on failure.
- Preserve the current local mock/demo path.

## Review Focus

- A production process with a default signing secret must refuse to start; Task 2 adds `test_production_rejects_default_secret`.
- A missing PostgreSQL connection in production must refuse to start; Task 2 adds `test_production_requires_postgresql`.
- SPA fallback must not turn an unknown `/api/*` route into HTML; Task 3 adds `test_unknown_api_route_remains_json_404`.
- A deep browser route such as `/sessions/example` must serve `index.html`; Task 3 adds `test_spa_fallback_serves_deep_link`.
- A clean checkout must use locked dependency versions and pass all suites; Task 4 exercises the exact clean-install commands in CI.

---

### Task 1: Establish the recoverable baseline

**Files:**
- Modify: `.gitignore`
- Create: `docs/development.md`

**Interfaces:**
- Consumes: the imported ZIP snapshot.
- Produces: a local `main` baseline commit and documented clean setup commands used by every later task.

- [ ] **Step 1: Scan tracked candidates for credentials**

Run `rg -n --hidden --glob '!backend/.venv/**' --glob '!frontend/node_modules/**' '(BEGIN (RSA|OPENSSH) PRIVATE KEY|GOOGLE_CLIENT_SECRET=.+|ONEMAP_(TOKEN|PASSWORD)=.+|postgres(ql)?://[^:]+:[^@]+@)' .` and inspect every match. Expected: examples contain placeholders only; remove any real secret before Git initialization.

- [ ] **Step 2: Extend ignore rules**

Add `.env`, `.env.*` with explicit `!.env.example`, coverage/build caches, IDE metadata, local database dumps, and Railway/Google credential downloads to `.gitignore` without ignoring the committed example files.

- [ ] **Step 3: Create the baseline commit**

Run `git init -b main`, `git add .`, `git diff --cached --check`, and `git commit -m "chore: import group scheduling baseline"`. Expected: one clean baseline commit and no ignored dependency/secret files.

- [ ] **Step 4: Recreate dependencies from locks**

Run `python3 -m venv backend/.venv`, `backend/.venv/bin/python -m pip install -r backend/requirements.txt`, and `(cd frontend && npm ci)`. Record these commands and supported Python/Node versions in `docs/development.md`.

- [ ] **Step 5: Verify the imported baseline**

Run `backend/.venv/bin/python -m pytest -q`, `(cd frontend && npm run lint)`, and `(cd frontend && npm run build)`. Expected: all three pass; if the imported code fails, stop feature work and use `superpowers:systematic-debugging` to record/fix the baseline first.

- [ ] **Step 6: Commit setup documentation**

Run `git add .gitignore docs/development.md && git commit -m "docs: add reproducible development setup"`.

### Task 2: Enforce production configuration and readiness

**Files:**
- Modify: `backend/app/core/config.py:5-35`
- Modify: `backend/app/core/database.py`
- Modify: `backend/app/main.py:18-52`
- Modify: `backend/.env.example`
- Create: `backend/tests/test_production_runtime.py`

**Interfaces:**
- Consumes: environment variables loaded by `Settings`.
- Produces: `Settings.validate_runtime() -> None`, `GET /health`, and `GET /ready`.

- [ ] **Step 1: Write failing production-setting tests**

Add `test_production_rejects_default_secret`, `test_production_requires_postgresql`, `test_production_rejects_debug_auth`, `test_production_rejects_mock_providers`, and `test_production_requires_secure_cookie`. Each constructs `Settings(_env_file=None, app_environment="production", ...)` and asserts `validate_runtime()` raises `ValueError` for exactly one unsafe value.

- [ ] **Step 2: Run the new tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_production_runtime.py -v`. Expected: FAIL because `app_environment` and `validate_runtime` do not exist.

- [ ] **Step 3: Implement production validation**

Add `app_environment: Literal["development", "test", "production"] = "development"` and `Settings.validate_runtime() -> None` to `backend/app/core/config.py`. In production require a non-default 32+ character session secret, a `postgresql+psycopg://` database URL, debug/mock flags false, secure cookies true, auto-create false, and non-empty Google and OneMap configuration.

- [ ] **Step 4: Add database readiness**

Add `database_is_ready() -> bool` in `backend/app/core/database.py` using `SELECT 1`; make `/ready` return 200 only when it succeeds and 503 otherwise. Keep `/health` process-only.

- [ ] **Step 5: Wire startup validation and test readiness**

Call `settings.validate_runtime()` at lifespan entry. Add tests `test_ready_returns_200_when_database_responds` and `test_ready_returns_503_when_database_fails` using dependency/engine monkeypatches.

- [ ] **Step 6: Run targeted and full backend tests**

Run `backend/.venv/bin/python -m pytest backend/tests/test_production_runtime.py -v` then `backend/.venv/bin/python -m pytest -q`. Expected: PASS.

- [ ] **Step 7: Document variables and commit**

Add `APP_ENVIRONMENT=development` and safe comments to `backend/.env.example`, then commit with `git commit -am "feat: validate production runtime settings"` plus the new test file.

### Task 3: Build and test the same-origin application container

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `backend/app/static_site.py`
- Modify: `backend/app/main.py:25-28`
- Modify: `frontend/vite.config.ts`
- Modify: `backend/tests/test_production_runtime.py`

**Interfaces:**
- Consumes: frontend output directory supplied as `STATIC_DIR`.
- Produces: `mount_static_site(app: FastAPI, static_dir: Path) -> None` and one production image listening on `$PORT`.

- [ ] **Step 1: Write failing static-site tests**

Add `test_spa_fallback_serves_deep_link`, `test_static_asset_is_served`, and `test_unknown_api_route_remains_json_404`. Use a temporary static directory containing `index.html` and `assets/app.js`; assert content types and that `/api/not-real` remains a JSON 404.

- [ ] **Step 2: Run tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_production_runtime.py -k 'spa or static or unknown_api' -v`. Expected: FAIL because no static-site mount exists.

- [ ] **Step 3: Implement the SPA/static boundary**

Create `mount_static_site(app: FastAPI, static_dir: Path) -> None`. Mount `/assets` when present, serve real files safely, and return `index.html` only for non-API browser paths. Register it after both API routers and system routes.

- [ ] **Step 4: Implement the multi-stage image**

Create a root `Dockerfile` with Node 22 and `npm ci && npm run build`, then Python 3.13-slim with locked backend requirements and copied frontend assets. Start `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` from `/app/backend`; do not seed demo data.

- [ ] **Step 5: Verify local application behavior**

Run the targeted tests, full backend suite, frontend lint/build, and `docker build -t group-scheduler:local .` when Docker is available. Expected: all available checks pass; if Docker is unavailable, CI in Task 4 becomes the required image-build evidence.

- [ ] **Step 6: Commit**

Run `git add Dockerfile .dockerignore backend/app/static_site.py backend/app/main.py backend/tests/test_production_runtime.py frontend/vite.config.ts && git commit -m "feat: serve production app from one container"`.

### Task 4: Add CI and Railway deployment skeleton

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `railway.toml`
- Create: `.env.production.example`
- Create: `docs/deployment.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the root Dockerfile and Alembic configuration.
- Produces: repeatable CI plus a Railway service configured with pre-deploy migrations and `/ready` health checks.

- [ ] **Step 1: Add the clean-checkout CI workflow**

Create jobs for Python 3.13 backend tests, Node 22 `npm ci`/lint/build, and root Docker image build. Trigger on pull requests and pushes to `main`; cache only dependency downloads, never generated artifacts as evidence.

- [ ] **Step 2: Add Railway configuration**

Configure Dockerfile builds, pre-deploy command `cd backend && alembic upgrade head`, start command using `$PORT`, `/ready` health check, and restart-on-failure policy. Do not embed environment values in `railway.toml`.

- [ ] **Step 3: Write production environment and deployment documentation**

List every required variable with placeholders in `.env.production.example`. In `docs/deployment.md`, document generated-domain setup, PostgreSQL `DATABASE_URL`, migration order, log redaction, rollback, and the rule that debug/mock flags stay false.

- [ ] **Step 4: Verify configuration files**

Run `git diff --check`, parse the TOML with Python's `tomllib`, and run all backend/frontend checks. Expected: no syntax errors and all tests pass.

- [ ] **Step 5: Commit**

Run `git add .github railway.toml .env.production.example docs/deployment.md README.md && git commit -m "ci: add production deployment pipeline"`.

- [ ] **Step 6: Push a private baseline and verify CI**

After the user's GitHub connection is confirmed, create a private repository, add it as `origin`, push the current branch, and verify all CI jobs pass. Never create a public repository for this project; use a new documentation commit for later corrections rather than rewriting shared history.

