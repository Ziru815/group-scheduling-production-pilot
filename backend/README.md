# Group Scheduling — Backend & Database Full Skeleton

This is a **working implementation skeleton**, not the earlier TODO-only placeholder. It follows the revised Lab 3 model: FastAPI, SQLModel, PostgreSQL, 15 persistent entities, nine controller responsibilities, aggregate repositories, privacy-safe DTOs and a source-revision guard against stale recommendation/confirmation races.

## What works now

- Google-token verification boundary plus a disabled-by-default local demo login.
- Atomic Session + organiser creation; invitation-based idempotent join (Option A: a Participant exists only after opening/joining the link).
- Session membership and organiser authorization on the server.
- Owner-only availability create/update/read/withdraw, including explicit zero availability.
- Candidate timeslot enumeration, four-state attendance, centroid shortlist, combinations, route-estimate storage, scoring/ranking and stale-result rejection.
- Final-plan confirmation only for a current feasible result.
- PostgreSQL/SQLite setup, Docker Compose, labelled demo seed and tests for the core rules.

## Intentionally configurable or incomplete

The values from the TBD meeting summary (60-minute journey cap, 10 venues, 12 participants, 15-minute step and 60/40 weights) are configuration defaults, **not silently treated as final SRS requirements**. Google Calendar writes require an approved OAuth scope and credential vault. Mall dataset, hosting and LTA use remain decisions. OneMap calls require a real token. When routing is missing, combinations remain `DATA_UNAVAILABLE`; the system never substitutes zero or straight-line travel time.

## Run locally in five minutes

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. For a classroom-only demo, set `DEBUG_AUTH_ENABLED=true`, restart, and call `POST /api/v1/auth/dev`. Never use this setting in deployment.

To use SQLite without Docker, set `DATABASE_URL=sqlite:///./group_scheduling.db`.

## Recommended API flow

1. `POST /auth/google` (or `/auth/dev` locally).
2. `GET /activities`, then `POST /sessions`; save the returned invitation token.
3. Other signed-in users `POST /participants/join`.
4. Each member `PUT /sessions/{id}/availability/me`, then geocodes their own record.
5. Organiser generates recommendations; route each generated combination; then rescores.
6. All members can view ranked options; only the organiser confirms with the expected source revision.

## Architecture mapping

- `models/domain.py`: all 15 database entities from the domain model.
- `repositories/aggregates.py`: eight aggregate repositories.
- `services/application_services.py`: Session, availability, generation, scoring and final-plan orchestration.
- `controllers/router.py`: thin HTTP controllers corresponding to the class diagram.
- `adapters/`: replaceable Google/OneMap/data.gov.sg/LTA boundaries.
- `schemas/api.py`: public/private DTO boundary; private origin/calendar credentials are never exposed in member result responses.

## Before merging into Live 4/5

1. Team approves the TBD defaults and Calendar scope/hold behavior.
2. Add a real venue import job for the accepted government datasets.
3. Configure secrets in a secret manager and turn off auto-create in production.
4. Run the included initial Alembic migration against a disposable PostgreSQL database and review future migrations.
5. Add integration tests using a disposable PostgreSQL database and mocked providers.

