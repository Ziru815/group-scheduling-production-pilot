# Google login setup and smoke test

Use this runbook after the Railway application has a stable HTTPS domain. It configures identity-only Google sign-in and verifies three separate team accounts without recording emails, tokens, cookies, authorization codes, or client secrets.

Official references:

- [Google web-server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google OpenID Connect reference](https://developers.google.com/identity/openid-connect/openid-connect)
- [Google OAuth redirect URI rules](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation)
- [Google app audience and test users](https://support.google.com/cloud/answer/15549945)

## Required values

Choose placeholders before opening any console:

```text
PUBLIC_ORIGIN=https://<generated-domain>
PUBLIC_CALLBACK=https://<generated-domain>/api/auth/google/callback
LOCAL_ORIGIN=http://localhost:5173
LOCAL_CALLBACK=http://localhost:8000/api/auth/google/callback
```

The public callback must match `GOOGLE_REDIRECT_URI` exactly. Scheme, hostname, port, path, case, and trailing slash are significant.

## Google Cloud configuration

1. Select or create the course team's Google Cloud project.
2. In Google Auth Platform, configure Branding with the application name `Group Scheduler`, a monitored support email, and team contact information. Do not claim a production domain the team does not control.
3. Set Audience to **External** unless every tester belongs to the same Google Workspace organization. Keep Publishing status at **Testing** for the course pilot.
4. Add exactly the three team Google accounts used for the smoke test as test users. Record them below only as Account A, B, and C.
5. Under Data Access, keep only the identity scopes `openid`, `email`, and `profile`. Do not add Google Calendar, Drive, Gmail, or offline access scopes to sign-in.
6. Create a client with application type **Web application**.
7. Add authorized JavaScript origins:

   ```text
   http://localhost:5173
   https://<generated-domain>
   ```

8. Add authorized redirect URIs:

   ```text
   http://localhost:8000/api/auth/google/callback
   https://<generated-domain>/api/auth/google/callback
   ```

9. Copy the client ID and client secret directly into Railway variables `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Set `GOOGLE_REDIRECT_URI` to `PUBLIC_CALLBACK`. Never download credentials into this repository.
10. Redeploy the Railway application and confirm `/health` and `/ready` both return HTTP 200.

## Three-account browser test

Use three isolated browser profiles or one normal profile plus two private sessions. Do not use an embedded webview. Clear the application's cookies before retrying a failed transaction.

For each Account A, B, and C:

1. Open `PUBLIC_ORIGIN/signin`.
2. Select **Sign in with Google** and choose that account.
3. Confirm Google's consent page requests only basic identity (`openid email profile`) and does not mention Calendar access.
4. Confirm the browser returns to the exact Railway origin and `/api/me` shows the correct display name and that account's own email.
5. Sign out, then confirm `/api/me` returns HTTP 401.
6. Start sign-in again, wait more than ten minutes or clear the `google_oauth_transaction` cookie before returning, and confirm the app shows the same generic retry message without exposing technical details.

Use Account A to create a session, then use Accounts B and C to open the invitation and join. Return to Account A and confirm three distinct participants appear. This proves account identity, shared database persistence, and cross-browser access together.

## Redacted result record

Do not replace account labels with names or email addresses.

| Check | Account A | Account B | Account C |
|---|---|---|---|
| Google consent shows identity only | NOT RUN | NOT RUN | NOT RUN |
| Callback returns to public origin | NOT RUN | NOT RUN | NOT RUN |
| `/api/me` matches current account | NOT RUN | NOT RUN | NOT RUN |
| Logout makes `/api/me` return 401 | NOT RUN | NOT RUN | NOT RUN |
| Session create/join persistence | NOT RUN | NOT RUN | NOT RUN |

Run date: `YYYY-MM-DD`

Tester: `team member label`

Railway deployment commit: `<full Git commit SHA>`

## Failure guide

- `redirect_uri_mismatch`: compare the configured redirect URI character-for-character with `GOOGLE_REDIRECT_URI` and the URI sent by the app.
- `access_denied`: confirm the account is an allowed test user and retry intentionally; a user cancellation should remain a normal, generic browser message.
- Generic retry message for every account: check Railway has the correct client ID/secret, then inspect redacted application logs and deployment health.
- One account fails with an existing-email conflict: do not alter database identities manually. Confirm the Google subject/account history and use a reviewed data-recovery decision.
- Cookie does not persist: confirm the site is HTTPS and `SESSION_COOKIE_SECURE=true`, then test without browser extensions that block cookies.

## Secret rotation

If the client secret is exposed or a team member with access leaves:

1. create or reset the client secret in Google Cloud;
2. replace `GOOGLE_CLIENT_SECRET` in Railway without placing it in a shell history or file;
3. redeploy and rerun all three account checks;
4. revoke/delete the old secret;
5. record only the rotation date and successful test result, never the secret.
