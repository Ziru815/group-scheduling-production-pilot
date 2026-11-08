# Group QR Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain that an organiser can display one invitation QR code for nearby people to scan and join, while online sharing should use the complete invitation message.

**Architecture:** Keep the existing `CopyLinkField` API, QR value, collapsed interaction and invitation flow unchanged. Replace only the expanded-panel guidance, protect the user-visible behavior with the existing React DOM test, then verify and publish the reviewed commit to the current production branch.

**Tech Stack:** React 19, TypeScript, `qrcode.react`, Node test runner, jsdom, oxlint, Vite

**Spec:** `docs/superpowers/specs/2026-10-31-group-qr-guidance-design.md`

## Global Constraints

- Use this exact guidance: `Show this code so people nearby can scan and join. For online sharing, copy the invitation message.`
- Keep the QR collapsed by default and continue encoding the exact invitation URL.
- Do not change backend, database, authentication, invitation-token, or availability behavior.
- Add no dependency, external QR service, analytics, or network request.
- Preserve raw-link copy, invitation-message copy, native share, accessibility and mobile layout.

## Review Focus

- Before expansion, the QR and its guidance remain absent so the invitation screen stays compact; Task 1's component test asserts both are hidden.
- After expansion, nearby group-scanning and online message-sharing are both explained; Task 1 asserts both phrases.
- Collapsing again removes the QR and guidance; Task 1 asserts both disappear.
- The QR stays an inline SVG with its existing accessible title rather than an external image; Task 1 asserts the SVG and title after expansion.
- Existing complete-message copying remains operational; Task 1 reruns the existing clipboard test and the full frontend suite.

---

### Task 1: Clarify group QR sharing

**Files:**
- Modify: `frontend/tests/copyLinkField.test.tsx`
- Modify: `frontend/src/components/CopyLinkField.tsx`
- Track: `docs/superpowers/specs/2026-10-31-group-qr-guidance-design.md`
- Track: `docs/superpowers/plans/2026-10-31-group-qr-guidance.md`

**Interfaces:**
- Consumes: existing `CopyLinkField({ url, message, showQr })` behavior.
- Produces: unchanged component props and QR behavior with clearer expanded-panel guidance.

- [ ] **Step 1: Write the failing component assertion**

  Extend `keeps the QR hidden until the organiser expands it` to assert the initial DOM contains neither `people nearby` nor `online sharing`; after expanding, assert both phrases, the inline SVG and the accessible `Invitation QR code` title; after collapsing, assert both phrases and the SVG disappear.

- [ ] **Step 2: Run the focused test and verify RED**

  Run: `cd frontend && npm run test:ui -- --test-name-pattern="keeps the QR hidden"`

  Expected: FAIL because the expanded panel still says only `Scan to open the invitation` and does not explain nearby or online sharing.

- [ ] **Step 3: Replace the expanded-panel caption**

  In `CopyLinkField.tsx`, replace the existing QR paragraph with the exact guidance from Global Constraints. Do not change component props, QR configuration or toggling.

- [ ] **Step 4: Run the focused test and verify GREEN**

  Run: `cd frontend && npm run test:ui -- --test-name-pattern="keeps the QR hidden"`

  Expected: PASS.

- [ ] **Step 5: Run complete frontend verification**

  Run: `cd frontend && npm test && npm run lint && npm run build`

  Expected: 21 tests pass, lint exits 0, and the production build succeeds.

- [ ] **Step 6: Commit the reviewed change**

  ```bash
  git add frontend/tests/copyLinkField.test.tsx frontend/src/components/CopyLinkField.tsx docs/superpowers/specs/2026-10-31-group-qr-guidance-design.md docs/superpowers/plans/2026-10-31-group-qr-guidance.md
  git commit -m "feat: explain group QR invitation sharing"
  ```

---

### Task 2: Publish and production smoke test

**Files:**
- Modify only if review finds a material issue: Task 1 files

**Interfaces:**
- Consumes: Task 1's green commit.
- Produces: a reviewed fast-forward update on `feature/production-pilot` and verified Render deployment.

- [ ] **Step 1: Review the complete branch**

  Review the diff for misleading access claims, invitation-token exposure, accessibility regressions and unintended QR behavior changes. Fix any Critical or Important finding with a failing test first.

- [ ] **Step 2: Re-run final verification**

  Run: `cd frontend && npm test && npm run lint && npm run build`

  Expected: 21 tests pass, lint exits 0, and the production build succeeds.

- [ ] **Step 3: Publish with a fast-forward lease**

  Update `feature/production-pilot` only if its head still matches the implementation base. Do not rewrite shared history.

- [ ] **Step 4: Verify Render and the real organiser page**

  Wait for the new commit to become `Live`. Expand and collapse the QR on an organiser response page; verify the new guidance appears only while expanded, the inline QR remains visible, and the invitation URL still opens the normal Session flow.
