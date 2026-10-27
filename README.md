# Group Scheduling Application

This repository integrates the supplied React frontend, FastAPI and SQLModel backend, SQL database, and standalone recommendation engine into one application that follows SRS v2.2.

## What is integrated

- The React client calls one browser API under `/api` using the documented camelCase contract and an httpOnly session cookie.
- The FastAPI application owns authentication, authorization, privacy filtering, Session and response workflows, recommendation orchestration, confirmation, and provider access.
- The standalone recommender is now the backend's core engine. It remains independent of HTTP and SQL, while `IntegratedRecommendationService` maps database snapshots into engine inputs and persists its Timeslots, attendance, shortlist, Combinations, travel estimates, scores, and ranks.
- PostgreSQL is the default deployment database. SQLite remains available for a zero-setup local run.
- The previous `/api/v1` backend surface remains available during migration; the frontend uses `/api`.

See `SRS_TRACEABILITY.md` for requirement coverage and the SRS items that still require external credentials or a stakeholder decision.

## Production pilot

The production image serves the React frontend and FastAPI API from one origin. CI verifies Python 3.13, Node 22, Railway configuration, and the root Docker image on every pull request and production-pilot branch update.

- Use `docs/development.md` for a reproducible local setup.
- Use `docs/deployment.md` for the private GitHub and Railway PostgreSQL deployment procedure.
- Use `.env.production.example` only as a variable checklist; keep all real secrets in Railway.

## Fastest demo with Docker

```bash
docker compose up --build
```

Open <http://localhost:5173>. The demo uses labelled test identities, mock geocoding/routing, and demo Venue data. Use the `DEV` pill to switch between the organiser and participants. Mock routing is deliberately disabled by default outside this demo profile because SRS NFR-8 requires live routing for real scoring.

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a local integrated demo, set these values in `backend/.env`:

```dotenv
DATABASE_URL=sqlite:///./group_scheduling.db
DEBUG_AUTH_ENABLED=true
USE_MOCK_PROVIDERS=true
FRONTEND_BASE_URL=http://localhost:5173
```

Then start the API:

```bash
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

Frontend, in another terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The integrated frontend example already has `VITE_USE_MOCKS=false` and `VITE_DEMO_AUTH=true`; it therefore uses the FastAPI backend rather than the original in-page MSW backend.

## Live provider configuration

For non-demo scoring, keep `USE_MOCK_PROVIDERS=false` and configure OneMap with either `ONEMAP_TOKEN` or `ONEMAP_EMAIL` plus `ONEMAP_PASSWORD`. Configure Google identity with `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and a callback URI registered as `GOOGLE_REDIRECT_URI`.

The SRS still leaves the public-transport provider, Mall data source, score normalization, journey cap, shortlist size, default attendance threshold, Candidate Timeslot step, and tie-break rule open. Their current values are explicit configuration defaults, not claimed stakeholder decisions.

## Verification

```bash
cd backend
.venv/bin/pytest -q

cd ../frontend
npm run build
npm run lint
```

The end-to-end backend test signs in two identities, creates and joins a Session, stores privacy-safe responses, runs the imported recommendation engine, returns the exact frontend result shape, and confirms the selected plan.

