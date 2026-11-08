# Grouped Recommendation Times Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated venue/time result cards with one ranked venue/outcome card whose exact stored times can be selected and confirmed.

**Architecture:** Keep the backend contract and all stored Combinations unchanged. Add a pure frontend grouping/selection module, then adapt `ResultsPage` and `RankedOptionCard` to render one group at a time while confirmation continues to submit the selected Combination ID.

**Tech Stack:** React 19, TypeScript 6, React Router, Node test runner, CSS, Vite

**Spec:** `docs/superpowers/specs/2026-10-31-grouped-recommendation-times-design.md`

## Global Constraints

- Do not change candidate generation, scoring, ranking, venue shortlisting or backend API responses.
- Never group options with different venue IDs, feasibility, scores, travel facts, attendee travel facts or absentee statuses.
- Keep every stored time selectable and submit its exact `combinationId` on confirmation.
- Display no more than six time buttons until the user asks to show all times.
- Keep stale-result, read-only, organiser-only and data-unavailable behaviour unchanged.
- Add no new runtime or test dependencies.

## Review Focus

- Coincidentally equal scores with different attendee IDs must remain separate; Task 1 pins this with a negative grouping test.
- The same people with a changed routing status or travel duration must remain separate; Task 1 pins both fields in the grouping signature test.
- A confirmed time that is not the group's earliest option must be selected by default; Task 1 pins confirmation precedence.
- A stale preferred selection after regeneration must fall back to the confirmed option and then the first ranked option; Task 1 pins both fallbacks.
- Data-unavailable groups must remain after feasible groups and must not become confirmable; Task 2 retains the divider and selected-option confirmation guard, followed by the production journey check in Task 3.

---

### Task 1: Recommendation grouping and selection model

**Files:**
- Create: `frontend/src/results/groupRecommendations.ts`
- Create: `frontend/tests/groupRecommendations.test.ts`

**Interfaces:**
- Consumes: `RankedCombination` from `frontend/src/api/types.ts`.
- Produces: `RankedOptionGroup { key: string; displayRank: number; options: RankedCombination[] }`.
- Produces: `groupRankedCombinations(options: readonly RankedCombination[]): RankedOptionGroup[]`.
- Produces: `selectedOptionForGroup(group: RankedOptionGroup, preferredCombinationId?: string, confirmedCombinationId?: string): RankedCombination`.

- [ ] **Step 1: Write failing tests for safe grouping**

Add tests named `groups only equivalent outcomes at one venue`, `keeps different attendance and routing outcomes separate`, and `keeps group order while sorting times chronologically`. Fixtures must include the reported shape: eleven same-venue/same-score combinations with 15-minute start increments.

- [ ] **Step 2: Run the grouping tests and verify RED**

Run: `cd frontend && npm test -- --test-name-pattern='group|attendance|order'`

Expected: FAIL because `src/results/groupRecommendations.ts` does not exist.

- [ ] **Step 3: Implement the canonical grouping signature and ordered groups**

Implement `groupRankedCombinations`. Build the signature from venue ID, feasibility, score/travel aggregates, sorted attendee tuples (`participantId`, transport mode, routing status, travel minutes) and sorted absentee tuples (`participantId`, attendance status). Exclude rank, time and Combination ID. Preserve first-seen group order, sort each group's options by start then raw rank, and assign consecutive `displayRank` values.

- [ ] **Step 4: Run the safe-grouping tests and verify GREEN**

Run: `cd frontend && npm test -- --test-name-pattern='group|attendance|order'`

Expected: PASS.

- [ ] **Step 5: Write failing tests for selection precedence**

Add tests named `selects an explicit valid time`, `prefers a confirmed time when the explicit selection is stale`, and `falls back to the first ranked time`.

- [ ] **Step 6: Run the selection tests and verify RED**

Run: `cd frontend && npm test -- --test-name-pattern='selects|prefers|falls back'`

Expected: FAIL because `selectedOptionForGroup` is not implemented.

- [ ] **Step 7: Implement `selectedOptionForGroup`**

Resolve in this exact order: a preferred ID present in the group, a confirmed ID present in the group, then `group.options[0]`. Reject an empty group with a descriptive error.

- [ ] **Step 8: Run all frontend unit tests and verify GREEN**

Run: `cd frontend && npm test`

Expected: all tests pass.

- [ ] **Step 9: Commit the model**

```bash
git add frontend/src/results/groupRecommendations.ts frontend/tests/groupRecommendations.test.ts
git commit -m "feat: group equivalent recommendation times"
```

### Task 2: Grouped Best matches interaction

**Files:**
- Modify: `frontend/src/pages/ResultsPage.tsx`
- Modify: `frontend/src/results/RankedOptionCard.tsx`
- Modify: `frontend/src/results/RankedOptionCard.css`

**Interfaces:**
- Consumes: `groupRankedCombinations` and `selectedOptionForGroup` from Task 1.
- Produces: `RankedOptionCard` props for `options`, `selectedCombinationId`, `displayRank`, `onSelectOption`, expansion, confirmation and existing session facts.

- [ ] **Step 1: Integrate groups into `ResultsPage` first and verify the contract is RED**

Use `useMemo` to build groups, replace expanded Combination state with expanded group-key state, keep a `Record<string, string>` of chosen Combination IDs, and pass the new grouped props to `RankedOptionCard`. Resolve the exact selected option through `selectedOptionForGroup` for confirmation and all confirmation messages.

Run: `cd frontend && npm run build`

Expected: FAIL with TypeScript prop errors because `RankedOptionCard` still exposes the flat-option interface.

- [ ] **Step 2: Implement the grouped card contract**

Update `RankedOptionCard` so its summary and details use the selected option, group rank drives Top match/`#N`, and multiple options add an accessible “N time options” label plus a **Choose a time** section. Each time button uses `aria-pressed`, calls `onSelectOption(combinationId)`, and shows the full formatted range.

- [ ] **Step 3: Add six-item progressive disclosure**

Keep local `showAllTimes` state. Render the first six options initially and a `Show all N times`/`Show fewer times` toggle only when the group has more than six options.

- [ ] **Step 4: Style the time chooser for mobile and keyboard use**

Add wrapping, touch-sized time buttons, a visible selected state and focus-visible outlines in `RankedOptionCard.css`. Keep existing card spacing and colour variables.

- [ ] **Step 5: Verify the grouped UI is GREEN**

Run: `cd frontend && npm test && npm run lint && npm run build`

Expected: all tests pass, lint exits 0, TypeScript succeeds and Vite produces `dist/`.

- [ ] **Step 6: Commit the interaction**

```bash
git add frontend/src/pages/ResultsPage.tsx frontend/src/results/RankedOptionCard.tsx frontend/src/results/RankedOptionCard.css
git commit -m "feat: choose times within grouped venue results"
```

### Task 3: Release evidence and production verification

**Files:**
- Modify: `docs/runbooks/assessment-release.md`

**Interfaces:**
- Consumes: the complete grouped-results implementation from Tasks 1–2.
- Produces: release verification notes for the current Render/GitHub deployment path.

- [ ] **Step 1: Run the full relevant verification suite**

Run: `cd frontend && npm test && npm run lint && npm run build`

Run: `cd backend && .venv/bin/pytest -q` when `.venv` exists; otherwise use the repository's documented pytest environment.

Expected: all frontend and backend checks pass.

- [ ] **Step 2: Record the release check**

Add a short runbook entry describing grouped venue/outcome cards, exact stored-time confirmation and the reported-session acceptance check.

- [ ] **Step 3: Commit the release evidence**

```bash
git add docs/runbooks/assessment-release.md
git commit -m "docs: record grouped recommendation verification"
```

- [ ] **Step 4: Perform branch review and integrate with the production branch**

Use the repository's normal finishing workflow after all checks pass. Push the reviewed commits to `origin/feature/production-pilot`, which is the Render source branch.

- [ ] **Step 5: Verify Render and the reported production session**

Wait for the deployment sourced from the new GitHub commit to become Live. Open `/sessions/59d96332-8d8e-469d-9047-133b1f57879a/results` and verify that Jurong Central Park is one group with eleven selectable times, Chinese Garden and Choa Chu Kang Park are separate groups, selecting a later time updates the card, and non-organisers still cannot confirm.
