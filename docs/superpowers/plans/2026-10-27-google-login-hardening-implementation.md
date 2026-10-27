# Google Login Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver production-safe Google OpenID Connect login with browser-bound state, nonce, PKCE, verified email, secure application sessions, and no public debug-auth escape hatch.

**Architecture:** A focused Google OAuth adapter owns authorization transactions and Google token exchange. Browser routes consume a short-lived signed transaction cookie exactly once, while `AuthenticationService` owns database identity matching and the existing app-session cookie remains the only browser credential after login.

**Tech Stack:** FastAPI, httpx, google-auth, itsdangerous, SQLModel, pytest

**Spec:** `docs/superpowers/specs/2026-10-27-production-pilot-design.md`

## Global Constraints

- Request only `openid email profile`; do not request Calendar access or store Google refresh tokens.
- Public cookies are `HttpOnly`, `Secure`, `SameSite=Lax`, and scoped to `/`.
- The exact Google callback is `/api/auth/google/callback` on the public HTTPS origin.
- Never log authorization codes, ID tokens, cookies, nonce, verifier, or full Google payloads.
- Debug persona endpoints return 404 in production.

## Review Focus

- A validly signed state copied into another browser must fail; Task 1 adds `test_callback_rejects_state_without_matching_transaction_cookie`.
- A transaction may be used only once; Task 2 adds `test_callback_always_clears_transaction_cookie`.
- A Google identity with `email_verified=false` must fail; Task 1 adds `test_verify_identity_rejects_unverified_email`.
- A second Google subject claiming an existing email must not silently take over the account; Task 2 adds `test_google_login_rejects_existing_email_with_different_subject`.
- An external `next=https://...` redirect must never leave the application; Task 2 adds `test_login_replaces_external_next_with_signin`.

---

### Task 1: Implement a testable Google OAuth adapter

**Files:**
- Create: `backend/app/adapters/google_oauth.py`
- Create: `backend/tests/test_google_oauth.py`
- Modify: `backend/app/adapters/__init__.py`

**Interfaces:**
- Consumes: Google client ID/secret/redirect URI, application signing secret, and an injected `httpx.AsyncClient`.
- Produces: `GoogleIdentity`, `GoogleOAuthStart`, and `GoogleOAuthClient.begin(next_path: str) -> GoogleOAuthStart`; `GoogleOAuthClient.complete(code: str, returned_state: str, transaction_cookie: str) -> Awaitable[GoogleIdentity]`.

- [ ] **Step 1: Write failing transaction and PKCE tests**

Add `test_begin_emits_random_state_nonce_and_s256_challenge`, `test_begin_preserves_only_relative_next_path`, `test_callback_rejects_state_without_matching_transaction_cookie`, `test_callback_rejects_expired_transaction`, and `test_callback_sends_original_code_verifier`. Assert exact query keys `response_type=code`, `scope=openid email profile`, `code_challenge_method=S256`, and `nonce`.

- [ ] **Step 2: Run tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_google_oauth.py -v`. Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement transaction creation and validation**

Use `secrets.token_urlsafe`, SHA-256 base64url PKCE, and `URLSafeTimedSerializer` with a dedicated salt. The signed cookie payload contains state, nonce, verifier, and safe relative next path and expires after 600 seconds.

- [ ] **Step 4: Add failing identity-validation tests**

Add `test_complete_rejects_nonce_mismatch`, `test_complete_rejects_wrong_audience_or_issuer`, `test_verify_identity_rejects_unverified_email`, and `test_complete_returns_normalized_google_identity`. Mock token HTTP with `httpx.MockTransport` and inject the ID-token verifier; do not call Google in unit tests.

- [ ] **Step 5: Implement code exchange and identity validation**

Post the code, client credentials, redirect URI, grant type, and verifier to Google's token endpoint. Verify the ID token with google-auth, require the transaction nonce, Google issuer, configured audience, subject, email, and `email_verified is True`; return normalized lowercase email and display name.

- [ ] **Step 6: Verify and commit**

Run `backend/.venv/bin/python -m pytest backend/tests/test_google_oauth.py -v` and commit with `git commit -m "feat: add browser-bound Google OAuth client"`.

### Task 2: Wire OAuth to browser routes and account persistence

**Files:**
- Modify: `backend/app/controllers/web_api.py:64-142`
- Modify: `backend/app/services/authentication_service.py`
- Modify: `backend/app/repositories/aggregates.py:15-20`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_authentication_authorization.py`
- Modify: `backend/tests/test_web_integration.py`

**Interfaces:**
- Consumes: `GoogleOAuthClient` and `GoogleIdentity` from Task 1.
- Produces: one-time `google_oauth_transaction` cookie flow and `AuthenticationService.google_identity_login(db: Session, identity: GoogleIdentity) -> AuthResponse`.

- [ ] **Step 1: Write failing browser-flow tests**

Add `test_google_login_sets_http_only_transaction_cookie`, `test_callback_requires_matching_cookie`, `test_callback_always_clears_transaction_cookie`, `test_callback_sets_secure_app_cookie`, and `test_login_replaces_external_next_with_signin`. Override the OAuth client with a fake and assert cookie flags and redirect locations.

- [ ] **Step 2: Write failing account-collision tests**

Add `test_google_login_creates_account_by_subject`, `test_google_login_updates_display_name_for_same_subject`, and `test_google_login_rejects_existing_email_with_different_subject`. The collision must return a generic sign-in failure to the browser and must not alter either account.

- [ ] **Step 3: Run targeted tests and verify failure**

Run `backend/.venv/bin/python -m pytest backend/tests/test_google_oauth.py backend/tests/test_authentication_authorization.py backend/tests/test_web_integration.py -k 'google or callback or external_next' -v`. Expected: new tests fail.

- [ ] **Step 4: Refactor browser routes**

Make `/api/auth/google/login` call `begin`, set the short-lived transaction cookie, and redirect to Google. Make the callback require and consume that cookie, call `complete`, issue the app cookie only after account persistence succeeds, and clear the transaction cookie on every callback exit path.

- [ ] **Step 5: Refactor identity persistence**

Implement `google_identity_login`. Match first by `(GOOGLE, subject)`; update its email/name only when safe; reject an email already owned by a different account. Require active status before issuing the application token.

- [ ] **Step 6: Preserve legacy API behavior deliberately**

Keep `/api/v1/auth/google` only if its current tests or documented clients require it; route it through the same verified identity persistence rules. Otherwise remove it together with its contract/tests in this commit, never leave a weaker parallel login path.

- [ ] **Step 7: Verify and commit**

Run the full backend suite. Expected: PASS. Commit with `git commit -m "feat: harden Google sign-in flow"`.

### Task 3: Lock production auth and document Google setup

**Files:**
- Modify: `backend/tests/test_web_integration.py`
- Modify: `frontend/src/pages/SignInPage.tsx`
- Modify: `frontend/docs/api-contract.md`
- Modify: `docs/deployment.md`
- Create: `docs/runbooks/google-login-smoke-test.md`

**Interfaces:**
- Consumes: hardened routes from Task 2 and the Railway HTTPS domain.
- Produces: a repeatable Google Cloud Console configuration and three-account smoke test.

- [ ] **Step 1: Add production debug-auth denial tests**

With production settings, assert `/api/dev/users` and `/api/dev/sign-in` return 404 and `/api/auth/google/login` never creates a development account or app-session cookie.

- [ ] **Step 2: Update user-safe error copy and API contract**

Keep browser messages generic for declined, expired transaction, account conflict, and provider outage. Document that sensitive details are server-side only and that Google Calendar is outside this login scope.

- [ ] **Step 3: Write the Google configuration runbook**

Document consent-screen fields, `openid email profile`, exact local/public origins and redirect URIs, test-user handling if the app remains in testing mode, secret rotation, and the three-account browser test. Use placeholders, never real IDs/secrets.

- [ ] **Step 4: Verify automated auth behavior**

Run full backend tests plus frontend lint/build. Expected: PASS and no build-time demo authentication in a normal production build.

- [ ] **Step 5: Execute the live login smoke test**

After Railway exists, sign in with three team Google accounts in isolated browsers, confirm each `/api/me` identity, log out, and confirm an expired/cleared cookie returns 401. Record only pass/fail and redacted account labels in the runbook.

- [ ] **Step 6: Commit**

Run `git add backend frontend docs && git commit -m "docs: add Google login production runbook"`.

