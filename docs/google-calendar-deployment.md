# Google Calendar deployment runbook

This runbook enables the optional Google Calendar integration on the existing
Render deployment. Keep manual availability working throughout the rollout by
leaving `GOOGLE_CALENDAR_ENABLED=false` until the database migration and every
secret are in place.

## 1. Configure Google Cloud

1. Open the Google Cloud project that owns the existing web OAuth client.
2. In **APIs & Services → Library**, enable **Google Calendar API**.
3. In **OAuth consent screen**, keep the application in **Testing** for the
   assessment and add every demonstrator and marker account as a test user.
4. Add these Calendar scopes to the consent screen:
   - `https://www.googleapis.com/auth/calendar.freebusy`
   - `https://www.googleapis.com/auth/calendar.app.created`
5. Keep the identity scopes `openid` and `email`. They only verify that Calendar
   consent came from the same Google account used to sign in.
6. In the existing **Web application** OAuth client, add this exact authorised
   redirect URI:

   `https://group-scheduling-app.onrender.com/api/calendar/google/callback`

Do not add a wildcard, a frontend route, or the Google sign-in callback in its
place. The existing sign-in callback remains separately configured.

### Testing-mode warning

For an External Google OAuth app left in **Testing**, refresh tokens for scopes
such as Calendar normally expire after seven days. Reconnect each demo account
within seven days of the presentation, or publish/verify the OAuth app if the
integration must live longer. This is a Google test-mode limit, not a Render or
database failure.

## 2. Configure Render without committing secrets

In **Render → group-scheduling-app → Environment**, set:

| Variable | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Existing Google web OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Existing Google web OAuth client secret |
| `GOOGLE_CALENDAR_REDIRECT_URI` | `https://group-scheduling-app.onrender.com/api/calendar/google/callback` |
| `GOOGLE_CALENDAR_CREDENTIAL_KEY` | A newly generated Fernet key (below) |
| `GOOGLE_CALENDAR_OAUTH_TRANSACTION_COOKIE_NAME` | `group_scheduler_calendar_oauth` |
| `GOOGLE_CALENDAR_ENABLED` | `false` during the first deployment |

Generate the credential-encryption key locally from the backend virtual
environment, copy the single printed value directly into Render, and do not put
it in Git, chat, screenshots, or a `.env` file:

```bash
cd backend
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The same Fernet key must remain configured for the life of the stored Calendar
connections. Rotating or losing it makes existing encrypted refresh tokens
unreadable; users would need to reconnect.

## 3. Deploy disabled first, then enable

1. Keep `GOOGLE_CALENDAR_ENABLED=false` and deploy the target Git commit.
2. Confirm the Render startup log completes `alembic upgrade head` before
   starting Uvicorn. The additive Calendar credential migration must succeed.
3. Confirm `GET /ready` returns a healthy response and normal Google sign-in and
   manual availability still work.
4. Recheck that all five values in the table above are present.
5. Change only `GOOGLE_CALENDAR_ENABLED` to `true` and deploy again.

The flag controls Calendar consent and provider calls. It does not affect normal
sign-in, session creation, manual availability, recommendation generation, or
confirmation.

## 4. Two-user live acceptance test

Use two different test-user Google accounts and a short disposable Session.

1. User A signs in, creates a Session, joins it as organiser, and connects
   Google Calendar from the availability page.
2. User B signs in through a separate browser profile, joins the invitation,
   connects Calendar, and submits availability.
3. Each user imports busy times. Verify the UI receives only busy interval start
   and end times; no Google event title, attendee, location, or description is
   displayed or persisted.
4. User A generates recommendations. In each connected account, verify a
   **Group Scheduler** secondary calendar exists and tentative holds are
   transparent (they do not make the user busy).
5. User A confirms a feasible option. Verify attending connected users receive
   one opaque final event with the selected venue and that all tentative holds
   are removed. Non-attendees must not receive a final event.
6. Disconnect and reconnect one account, then use **Retry calendar sync**. Verify
   the retry is idempotent and does not duplicate the final event.
7. Confirm manual availability and plan confirmation still work for a third user
   who never connects Calendar.

Never paste a refresh token, access token, client secret, or Fernet key into an
issue, log, screenshot, or test report.

## 5. Rollback and incident response

For a Calendar-specific incident, set `GOOGLE_CALENDAR_ENABLED=false` and deploy.
Leave the additive database tables and migration in place. Manual scheduling and
Google identity sign-in remain available, while new Calendar consent and sync
calls stop.

If only one account is affected, disconnect it from the profile page and
reconnect with the same Google identity. Provider errors shown to users are
sanitised; diagnose with Render request timing and status logs, not token values.

## 6. Post-assessment cleanup

After the final assessment:

1. Set `GOOGLE_CALENDAR_ENABLED=false`.
2. Disconnect test accounts in the application so Google grants are revoked and
   encrypted refresh tokens are cleared.
3. Remove test users or return the Google OAuth app to its intended publishing
   state; remove the Calendar callback if the service is being retired.
4. Delete the test users' **Group Scheduler** secondary calendars if no longer
   needed.
5. Remove the Calendar secret values from Render, then suspend or delete the
   Render web/database services according to the course retention plan.

