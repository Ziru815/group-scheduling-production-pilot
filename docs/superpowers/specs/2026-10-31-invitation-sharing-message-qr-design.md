# Invitation Message and QR Sharing Design

## Intent

Make invitation sharing feel complete in a real group chat while preserving the existing secure invitation flow. The primary path is a copyable, human-readable invitation message. A QR code is a secondary, optional path for face-to-face sharing and the project presentation.

## Goals

- Keep the existing raw-link copy action and native device share action.
- Add a clear `Copy invitation message` action on both the post-creation screen and the organiser response-status screen.
- Include the Session name, activity, date range, response deadline, and invitation URL in the copied message.
- Add a collapsed `Show QR code` action that renders the same invitation URL locally in the browser.
- Keep both additions accessible on mobile and desktop and provide clear success or failure feedback.

## Non-goals

- Do not rotate, revoke, expire, shorten, or otherwise change invitation tokens.
- Do not add email, SMS, WhatsApp, Telegram, or other provider-specific delivery integrations.
- Do not change who can see the invitation link or who can join a Session.
- Do not change the Google sign-in return flow.

## Constraints and Security

- The invitation URL remains Access Data and must not be logged.
- QR generation happens entirely in the browser. The invitation URL must not be sent to a third-party QR service.
- The QR code is hidden by default so it does not clutter the normal group-chat workflow or expose the token unnecessarily during screen sharing.
- The existing organiser-only invitation endpoint and unguessable token remain unchanged.
- The copied message uses text only and treats Session data as plain text, not HTML.

## Approaches Considered

### 1. Rich invitation message only

Smallest change and best for group chats, but does not help with face-to-face sharing or a live presentation.

### 2. Rich invitation message plus an optional local QR code — selected

Adds the useful group-chat path first and keeps the QR code behind an explicit toggle. This has a small frontend dependency and slightly more testing, but no backend or database change.

### 3. Revocable links or provider-specific sharing

More control or convenience, but requires backend state, new error cases, or third-party integrations. It is not required by the SRS and is disproportionate to the current need.

## User Experience

The existing invitation field remains visible with `Copy` and, where supported, `Share link…`.

Below it, the organiser sees:

1. `Copy invitation message` — copies a message in this shape:

   ```text
   You're invited to “Weekend Picnic”
   Activity: Picnic
   Dates: 1 Nov 2026
   Respond by: 31 Oct 2026, 9:00 pm
   Join and mark when you're free: https://…/join/…
   ```

2. `Show QR code` — expands an inline card containing a locally generated QR code, the label `Scan to open the invitation`, and a `Hide QR code` action.

The same component and wording are used immediately after Session creation and later on the organiser's response-status page. Date and time formatting reuse the application's existing Session timezone helpers.

## Implementation Shape

- Extend `CopyLinkField` with an optional preformatted invitation message and optional QR rendering.
- Build the message from Session data at the two call sites so the shared component remains generic.
- Use a small client-side QR library that renders SVG without network calls.
- Keep clipboard fallback behaviour: if automatic copying fails, select the raw link and explain how to copy manually.
- Add focused tests for message formatting, clipboard success/failure, QR toggle behaviour, and the guarantee that QR generation has no network path.

## Acceptance Criteria

- The organiser can copy a complete invitation message from both invitation-sharing screens.
- The copied message contains the correct Session details and exact invitation URL.
- The existing raw-link copy and native share actions still work.
- The QR code is hidden initially, expands on request, and encodes the exact invitation URL locally.
- No backend API, database schema, invitation token, or permission behaviour changes.
- Frontend tests, lint, and production build pass.
