# Public pilot deployment

The public pilot uses one Railway application service and one Railway PostgreSQL service in Singapore. The application builds the root `Dockerfile`, serves the React site and FastAPI API on one HTTPS origin, runs Alembic before each release, and exposes `/ready` as the deployment health check.

## Render fallback while Railway sign-ups are paused

The repository also includes `render.yaml` for a temporary Render deployment.
Use this path only when a new Railway account cannot be created. It preserves
the same Docker, FastAPI, React, PostgreSQL, OAuth, and provider architecture;
Railway configuration remains available for a later switch.

The initial Blueprint deliberately selects one free Singapore web service and
one free Singapore PostgreSQL database. Render's free web service sleeps after
15 minutes without inbound traffic and can take about one minute to wake. Its
free PostgreSQL database expires 30 days after creation and has no backups. This
fits the assessment pilot only if the database is created close to the demo and
the team exports any required evidence before expiry.

1. Sign in to Render with the GitHub account that can access the private
   repository. Install Render's GitHub App only for
   `group-scheduling-production-pilot`.
2. In Render, create a Blueprint from the private repository, select
   `feature/production-pilot`, and use the root `render.yaml`.
3. Confirm that both resources show `Free` and `Singapore` before applying the
   Blueprint. Stop if any paid plan is selected.
4. For the first infrastructure-only deploy, enter temporary non-secret values
   for the prompted URL and provider variables. Use `https://example.invalid`
   for `FRONTEND_BASE_URL` and `ALLOWED_ORIGINS`, use the corresponding
   `/api/auth/google/callback` value for `GOOGLE_REDIRECT_URI`, and use
   `pending-configuration` for the provider credentials. These values only let
   the container start long enough to obtain its generated domain; Google login
   and routing are expected to remain unavailable.
5. Copy the generated `https://...onrender.com` origin. Create the Google OAuth
   client with that exact JavaScript origin and callback, obtain the real OneMap
   token, replace all temporary variables in Render, and redeploy.
6. Verify `/health` and `/ready`, then run the venue dry run and apply from a
   Render shell or one-off job. Free web services do not include shell access;
   if that remains unavailable, run the sync locally with a short-lived external
   database URL. Temporarily allow only the current operator IP in the database
   access controls, remove that rule immediately after the sync, and never allow
   `0.0.0.0/0`. Alternatively, temporarily use a paid service only after the
   billing owner approves it.
7. Open the site at least two minutes before each rehearsal or presentation so
   the free instance is awake. Export required evidence and remove both Render
   resources after grading or before the free database's 30-day expiry.

Because free Render web services do not support pre-deploy commands,
`backend/scripts/start_production.sh` performs the deployment gate at process
start. It exits immediately if migration or reference-data seeding fails and
starts Uvicorn only after both succeed.

Railway's older `railway.toml` Config-as-Code path is deprecated for new services. This repository therefore keeps the supported TypeScript configuration in `.railway/railway.ts`. The configuration pins one replica in Railway's Singapore region, restarts failed processes up to ten times, and preserves secrets that are entered in Railway rather than Git.

## 1. Create the private source repository

Create a **private** GitHub repository and push this project. Keep the repository private because the course snapshot may include project material that is not intended for public redistribution.

Do not commit `.env` files, Google client secrets, OneMap credentials, exported Railway variables, database dumps, or screenshots containing credentials.

## 2. Create and link Railway resources

1. In Railway, create a project from the private GitHub repository and select the root `Dockerfile` for the application service.
2. Add a PostgreSQL service named `postgres` and keep the application service name `app`, matching `.railway/railway.ts`.
3. Generate a Railway domain for `app`.
4. Install the current Railway CLI, sign in, and link this checkout to the project and production environment.
5. From the repository root, run:

   ```bash
   npm ci --prefix .railway
   railway config plan
   ```

   Review the plan before running `railway config apply`. Applying infrastructure changes can create, change, or remove cloud resources, so do not use unattended destructive flags.

The GitHub source is intentionally linked in Railway's UI instead of hard-coded in the TypeScript file; this keeps the configuration valid before the final GitHub owner/repository name is chosen.

## 3. Configure production variables

Use `.env.production.example` as the checklist, but enter values in the Railway `app` service. Do not upload a populated file.

The Infrastructure-as-Code file supplies these fixed safety values:

- `APP_ENVIRONMENT=production`
- `AUTO_CREATE_TABLES=false`
- `DEBUG_AUTH_ENABLED=false`
- `USE_MOCK_PROVIDERS=false`
- `SESSION_COOKIE_SECURE=true`
- `DATABASE_URL` as a private reference to Railway PostgreSQL

Enter these deployment-specific values in Railway:

- `APP_SESSION_SECRET`: a random value of at least 32 characters.
- `FRONTEND_BASE_URL` and `ALLOWED_ORIGINS`: the generated `https://...up.railway.app` origin, without a trailing slash.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: values from the Google Cloud OAuth client.
- `GOOGLE_REDIRECT_URI`: the same origin plus `/api/auth/google/callback`.
- `ONEMAP_TOKEN`: the token used for live Singapore geocoding/routing.

The application accepts Railway's standard `postgresql://` reference and selects the installed psycopg 3 driver internally. Never replace the private reference with the database's public URL.

## 4. Configure Google OAuth

Follow `docs/runbooks/google-login-smoke-test.md` for the complete Google Cloud and three-account verification procedure. In the Google Cloud OAuth web client, add exactly this authorized redirect URI:

```text
https://<generated-domain>/api/auth/google/callback
```

Add the generated HTTPS origin under authorized JavaScript origins. Use named team accounts as test users while the app audience remains in testing. A mismatch in scheme, host, path, case, or trailing slash causes Google to reject the login.

Sign-in requests only `openid email profile`; do not add Calendar scopes to this OAuth client flow and do not configure offline access. Keep the client secret only in Railway. If it appears in source, logs, screenshots, chat, or demo footage, rotate it in Google Cloud and update Railway before continuing.

## 5. Deployment and migration order

For every deployment Railway should:

1. build the root Dockerfile;
2. run `alembic upgrade head` from the image's `/app/backend` working directory;
3. run `python -m scripts.seed_reference_data` to idempotently create only the six public activity types—never demo users or venues;
4. start Uvicorn on Railway's `$PORT`;
5. accept the release only after `/ready` returns HTTP 200.

The migration must finish successfully before the new application starts. `AUTO_CREATE_TABLES` stays false in production so startup cannot silently create an unreviewed schema.

After the first healthy deployment, run `python -m scripts.sync_venues --dry-run`
and review its counts before running `python -m scripts.sync_venues --apply`.
The sync is separate from every deployment so an upstream provider outage cannot
block an otherwise safe application release.

## 6. Verify a release

After Railway reports a healthy deployment, check:

```bash
curl -fsS https://<generated-domain>/health
curl -fsS https://<generated-domain>/ready
```

Then use a clean or incognito browser to verify Google sign-in, create a group, join it from a second Google account, submit availability and location consent, generate recommendations, and confirm a venue. Debug identity switching and mock providers must not appear in the public pilot.

## Logs, secrets, rollback, and recovery

- Treat request cookies, OAuth codes, access tokens, database URLs, OneMap credentials, emails, and precise participant locations as sensitive. Do not paste them into issues, chat messages, screenshots, or demo recordings.
- Application logs should identify operations with internal IDs, not raw provider payloads or credentials.
- If a release fails after migration, inspect the pre-deploy and application logs, then redeploy the last known-good Git commit. Do not rewrite shared Git history.
- Prefer backward-compatible migrations. If a migration requires a database rollback, take a Railway backup first and use a reviewed Alembic downgrade only when the migration defines a safe reverse path.
- Before the presentation, export or verify a recent database backup and keep a local demo profile as a fallback. The fallback is for presentation continuity, not evidence that the public pilot is healthy.
