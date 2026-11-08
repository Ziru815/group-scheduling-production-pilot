# Development setup

## Supported toolchain

- Python 3.13
- Node.js 22.13 or newer in the Node 22 line for CI and containers
- npm 10 or newer
- PostgreSQL 16 for database integration checks

The imported baseline was also verified locally with Node.js 24.10.0 and npm 11.6.0. Production and CI remain pinned to Node 22 so the deployment toolchain is predictable.

## Clean installation

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm ci)
```

Do not commit `.venv`, `node_modules`, `.env` files, database dumps, OAuth credential downloads, or platform credentials.

## Baseline verification

Run all three checks before feature work and before pushing a release:

```bash
(cd backend && .venv/bin/python -m pytest -q)
(cd frontend && npm run lint)
(cd frontend && npm run build)
```

The accepted imported baseline on 2026-10-28 produced:

- backend: 62 passed;
- frontend lint: passed;
- frontend production build: passed.

## Local modes

The normal local frontend may proxy `/api` to FastAPI. Mock providers and debug personas are development-only controls. Never copy local `.env` values into source files or enable debug/mock flags in the public assessment environment.
