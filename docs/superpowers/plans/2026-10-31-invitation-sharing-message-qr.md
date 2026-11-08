# Invitation Message and QR Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give organisers a complete invitation message for group chats and an optional locally generated QR code without changing invitation security or backend behaviour.

**Architecture:** Add one pure invitation-message formatter beside the existing Session UI, then extend the shared `CopyLinkField` with optional message-copy and QR controls. Both current invitation surfaces supply the same Session metadata, while `qrcode.react` renders an SVG entirely in the browser.

**Tech Stack:** React 19, TypeScript 6, `qrcode.react` 4.2, Node test runner, existing Vite/Oxlint toolchain

**Spec:** `docs/superpowers/specs/2026-10-31-invitation-sharing-message-qr-design.md`

## Global Constraints

- Keep the existing raw-link copy action and native device share action.
- The invitation URL remains Access Data and must not be logged.
- QR generation must happen entirely in the browser; no third-party QR endpoint or network request is allowed.
- The QR code is hidden by default.
- Do not change backend APIs, the database schema, invitation token generation, permissions, or Google sign-in return behaviour.
- Reuse the application's existing Session timezone formatting helpers.

## Review Focus

- Clipboard unavailable or rejected: keep the raw link selected and show a useful manual-copy message.
- Single-day versus multi-day Sessions: the copied `Dates` line must match existing UI formatting.
- Response deadline timezone: format in the Session timezone, never the browser timezone.
- Long invitation URL on a narrow phone: actions and QR must remain usable without horizontal page overflow.
- QR correctness and privacy: encode the exact invitation URL in a local SVG and make no network request.

---

### Task 1: Invitation message formatter

**Files:**
- Create: `frontend/src/sessions/invitationSharing.ts`
- Create: `frontend/tests/invitationSharing.test.ts`

**Interfaces:**
- Consumes: `formatIsoDate`, `formatDateTime`, and the existing `IsoDate`, `IsoDateTime`, and `TimeZone` types.
- Produces: `buildInvitationMessage(input: InvitationMessageInput): string`, where the input contains `name`, `activityName`, `startDate`, `endDate`, `responseDeadline`, `timezone`, and `invitationUrl`.

- [ ] **Step 1: Write failing tests for exact single-day and multi-day invitation messages**

  Assert the five lines are title, activity, dates, response deadline, and `Join and mark when you're free: <exact URL>`. Include a response deadline with an explicit UTC offset and assert Singapore-time output.

- [ ] **Step 2: Run the focused test and verify it fails because the module does not exist**

  Run: `cd frontend && node --experimental-strip-types --test tests/invitationSharing.test.ts`
  Expected: FAIL with module-not-found for `invitationSharing.ts`.

- [ ] **Step 3: Implement the pure formatter**

  Use this signature:

  ```ts
  export type InvitationMessageInput = {
    name: string
    activityName: string
    startDate: IsoDate
    endDate: IsoDate
    responseDeadline: IsoDateTime
    timezone: TimeZone
    invitationUrl: string
  }

  export function buildInvitationMessage(input: InvitationMessageInput): string
  ```

  Reuse the same single-day/range logic already present in `InviteCreated` and `ResponseStatusPage`; do not parse or rewrite the invitation URL.

- [ ] **Step 4: Run the focused test and verify it passes**

  Run: `cd frontend && node --experimental-strip-types --test tests/invitationSharing.test.ts`
  Expected: both tests PASS.

- [ ] **Step 5: Commit the formatter and tests**

  ```bash
  git add frontend/src/sessions/invitationSharing.ts frontend/tests/invitationSharing.test.ts
  git commit -m "feat: format complete invitation messages"
  ```

---

### Task 2: Shared copy-message and QR controls

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/components/CopyLinkField.tsx`
- Modify: `frontend/src/components/CopyLinkField.css`

**Interfaces:**
- Consumes: optional `message?: string` and `showQr?: boolean` props supplied by invitation screens.
- Produces: the existing raw-link field plus `Copy invitation message` and a collapsed `Show QR code` / `Hide QR code` control. The QR SVG receives `value={url}` exactly.

- [ ] **Step 1: Add the local SVG QR dependency**

  Run: `cd frontend && npm install qrcode.react@4.2.0`
  Expected: `package.json` and `package-lock.json` record `qrcode.react`; no install script or external QR service is added.

- [ ] **Step 2: Extend `CopyLinkField` props and clipboard behaviour**

  Add `message?: string` and `showQr?: boolean`. Keep the existing raw-link `Copy` button. When `message` exists, `Copy invitation message` writes the complete message and reports `Invitation message copied`; on failure, select the raw-link input and show the existing manual-copy guidance.

- [ ] **Step 3: Add the hidden-by-default QR interaction**

  When `showQr` is true, render a button with `aria-expanded`; expand an inline panel containing `QRCodeSVG` with `value={url}`, `title="Invitation QR code"`, error correction `level="M"`, and a four-module margin. Do not add images, logos, fetch calls, analytics, or URL transformation.

- [ ] **Step 4: Add responsive and accessible styling**

  Keep controls at least the existing tap-target height, allow the action group to wrap on narrow screens, constrain the SVG to its container, and centre the QR panel without exposing the full token in extra visible text.

- [ ] **Step 5: Verify type-checking, lint, and build**

  Run: `cd frontend && npm run lint && npm run build`
  Expected: both commands exit 0; the Vite bundle contains the QR renderer locally.

- [ ] **Step 6: Commit the shared component**

  ```bash
  git add frontend/package.json frontend/package-lock.json frontend/src/components/CopyLinkField.tsx frontend/src/components/CopyLinkField.css
  git commit -m "feat: add invitation message and QR controls"
  ```

---

### Task 3: Wire both organiser invitation surfaces

**Files:**
- Modify: `frontend/src/sessions/InviteCreated.tsx`
- Modify: `frontend/src/pages/ResponseStatusPage.tsx`
- Modify: `frontend/tests/invitationSharing.test.ts`

**Interfaces:**
- Consumes: `buildInvitationMessage(input)` from Task 1 and the extended `CopyLinkField` props from Task 2.
- Produces: identical invitation-message and QR capabilities after Session creation and on the organiser response-status page.

- [ ] **Step 1: Add a regression assertion for every field supplied by the two screens**

  Extend the pure formatter test to assert the exact activity name, date range, response deadline, and invitation URL used by a representative `CreateSessionResponse` / `SessionDetail` projection.

- [ ] **Step 2: Wire `InviteCreated`**

  Build the message from `session.name`, `session.activityType.name`, `session.startDate`, `session.endDate`, `session.responseDeadline`, `session.timezone`, and `invitationUrl`; pass it as `message` and enable `showQr`.

- [ ] **Step 3: Wire `ResponseStatusPage`**

  Use the same fields and `invitation.data.invitationUrl`; pass the resulting message and enable `showQr` only while the existing active-session invitation section is rendered.

- [ ] **Step 4: Run the complete frontend verification**

  Run: `cd frontend && npm test && npm run lint && npm run build`
  Expected: all tests PASS, lint exits 0, and the production build succeeds.

- [ ] **Step 5: Perform a local browser smoke test**

  On both invitation surfaces verify: raw `Copy` still works; `Copy invitation message` produces all five lines; `Show QR code` expands an SVG; `Hide QR code` collapses it; the page stays within a mobile-width viewport. Decode or scan the QR and confirm it equals the exact displayed invitation URL.

- [ ] **Step 6: Commit the wiring**

  ```bash
  git add frontend/src/sessions/InviteCreated.tsx frontend/src/pages/ResponseStatusPage.tsx frontend/tests/invitationSharing.test.ts
  git commit -m "feat: share complete session invitations"
  ```

---

### Task 4: Review, publish, and production smoke test

**Files:**
- Modify if findings require it: files from Tasks 1–3
- Track: `docs/superpowers/specs/2026-10-31-invitation-sharing-message-qr-design.md`
- Track: `docs/superpowers/plans/2026-10-31-invitation-sharing-message-qr.md`

**Interfaces:**
- Consumes: the completed frontend feature and green verification from Tasks 1–3.
- Produces: reviewed commits on `feature/production-pilot`, an automatic Render deployment, and evidence from the real site.

- [ ] **Step 1: Run final branch verification**

  Run: `cd frontend && npm test && npm run lint && npm run build`
  Expected: all commands exit 0 with no new warnings.

- [ ] **Step 2: Review the complete branch against the approved design**

  Focus on invitation-token leakage, clipboard fallback, exact timezone formatting, QR network independence, accessibility, and mobile layout. Fix material findings and rerun Step 1.

- [ ] **Step 3: Commit the approved design and plan if not already tracked**

  ```bash
  git add docs/superpowers/specs/2026-10-31-invitation-sharing-message-qr-design.md docs/superpowers/plans/2026-10-31-invitation-sharing-message-qr.md
  git commit -m "docs: plan invitation message and QR sharing"
  ```

- [ ] **Step 4: Push the reviewed commit range to `feature/production-pilot`**

  Use a fast-forward update with the current remote head as the lease. Do not rewrite shared history.

- [ ] **Step 5: Verify Render and the live site**

  Wait for the new commit to become `Live`. On the real organiser response-status page, verify complete-message copying and QR expand/collapse; scan the QR and confirm it opens the same `/join/<token>` URL. Confirm an invited Google user can still join normally.
