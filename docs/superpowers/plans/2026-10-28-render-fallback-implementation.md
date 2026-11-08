# Render Fallback Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested, no-cost Render deployment path for the public course pilot while Railway sign-ups are paused.

**Architecture:** A Render Blueprint creates one free Singapore Docker web service and one free Singapore PostgreSQL database. Because Render free services do not support pre-deploy commands, a fail-fast shell entrypoint runs Alembic and idempotent reference seeding before replacing itself with Uvicorn.

**Tech Stack:** Render Blueprint, Docker, POSIX shell, FastAPI, Alembic, PostgreSQL, pytest

**Spec:** `docs/superpowers/specs/2026-10-28-render-fallback-design.md`

## Global Constraints

- Do not change business behavior or database schema.
- Do not remove Railway configuration.
- Do not commit provider credentials or populated environment files.
- Use Render `free` web and PostgreSQL plans in `singapore`.
- Migration or reference seed failure must prevent Uvicorn startup.

## Review Focus

- A failed migration must stop before seed or Uvicorn.
- A failed seed must stop before Uvicorn.
- The generated Render database connection must reach `DATABASE_URL` without interpolation.
- Google and OneMap secrets must be dashboard prompts, not Git values.
- The service must listen on Render's injected `PORT` and expose `/ready`.

---

### Task 1: Render startup gate and Blueprint

**Files:**
- Create: `backend/tests/test_render_deployment.py`
- Create: `backend/scripts/start_production.sh`
- Create: `render.yaml`
- Modify: `docs/deployment.md`

**Interfaces:**
- Consumes: existing Alembic migrations, `scripts.seed_reference_data`, root Dockerfile, production settings.
- Produces: `sh scripts/start_production.sh` and a root Render Blueprint for `group-scheduling-app` and `group-scheduling-postgres`.

- [ ] **Step 1: Write failing startup-order and Blueprint tests**

Add subprocess tests with fake `alembic`, `python`, and `uvicorn` commands. Assert successful order, `PORT` propagation, migration-failure short circuit, and seed-failure short circuit. Add static Blueprint assertions for free Singapore resources, Docker, `/ready`, database reference, production safety values, generated session secret, and unsynced Google/OneMap secrets.

- [ ] **Step 2: Verify RED**

Run: `cd backend && .venv/bin/pytest -q tests/test_render_deployment.py`

Expected: FAIL because `scripts/start_production.sh` and `render.yaml` do not exist.

- [ ] **Step 3: Add the minimal startup script and Blueprint**

The shell script uses `set -eu`, runs migration and seed in order, and `exec`s Uvicorn on `${PORT:-10000}`. The Blueprint uses the root Dockerfile and database connection reference, with no secret values committed.

- [ ] **Step 4: Document Render fallback and free-plan limitations**

Add account creation, Blueprint deployment, secret entry, generated-domain callback, wake-up, venue sync, and 30-day shutdown/export instructions without copying credentials into documentation.

- [ ] **Step 5: Verify GREEN and regression suites**

Run the targeted test, full backend suite, frontend lint/build, Railway IaC `npm run check`, official Render Blueprint Schema validation, and root Docker CI-equivalent checks available locally. Expected: all pass.

- [ ] **Step 6: Commit**

Commit message: `feat: add Render fallback deployment`
