# Render Fallback Deployment Design

## Intent

Provide a public course-demo deployment while Railway has paused new account
sign-ups. Preserve the existing same-origin React/FastAPI application,
PostgreSQL persistence, Google OAuth flow, and verified venue catalogue.

## Goals

- Deploy one Docker web service and one PostgreSQL database in Render's
  Singapore region from the private GitHub repository.
- Use free instances initially, with no payment required.
- Refuse to start the application if Alembic migration or reference-data
  seeding fails.
- Keep all provider credentials in Render secrets, never in Git.
- Keep Railway configuration intact so the team can switch back later.

## Non-goals

- No business-feature, database-schema, or UI redesign.
- No custom domain, paid Render feature, or long-term hosting commitment.
- No promise of always-on availability on the free web plan.

## Constraints

- Render free web services sleep after 15 minutes without inbound traffic and
  can take about a minute to wake.
- Render free PostgreSQL expires 30 days after creation and has no backups.
- Render pre-deploy commands are not available on free web services. The
  container start command must therefore run `alembic upgrade head`, then
  `python -m scripts.seed_reference_data`, then `exec uvicorn ...` with `&&`
  semantics enforced by `set -e`.
- The public service must use `APP_ENVIRONMENT=production`, secure cookies,
  real providers, and `/ready` as its health check.

## Approaches

1. Wait for Railway sign-ups to reopen. This changes no code but has no stated
   recovery date and risks the course schedule.
2. Use Render free web and PostgreSQL instances. This needs a small startup
   wrapper and Blueprint, but preserves the architecture and fits the three-week
   assessment window. **Selected.**
3. Split hosting across Cloud Run and an external PostgreSQL provider. This is
   viable but adds billing, IAM, and cross-provider networking complexity.

## Verification

- Automated tests prove migration, seed, and server command ordering and prove
  migration failure prevents later commands.
- Static assertions pin the Blueprint to free Singapore resources, Docker,
  `/ready`, database references, production safety flags, and unsynced secrets.
- Existing backend, frontend, IaC, and Docker CI continue to pass.
