# Lab 4 Software Testing Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a submission-ready English PDF and matching automated tests that satisfy every Lab 4 black-box and white-box testing requirement for the current production code.

**Architecture:** Treat `RecommendationEngine.generate()` as the important control-class boundary for black-box testing, observing only requests, returned statuses, ranked combinations, and raised validation errors. Use `pre_routing_exclusion()` and `_ParticipantAvailability.status_for()` for white-box basis-path testing because their branches map directly to SRS feasibility and attendance rules. Keep production code unchanged unless a newly written test exposes a genuine defect.

**Tech Stack:** Python 3.13, pytest, existing recommender fixtures and mock router, Graphviz/DOT or equivalent vector flowcharts, ReportLab/PyPDF/Poppler for PDF generation and verification.

**Spec:** `/Users/gaoziru/Desktop/大二上/SC2006/Lab/Lab 4 Manual (3).pdf`

## Global Constraints

- Work on a new branch named `lab4/software-testing-report` based on the exact tree deployed from `feature/production-pilot` (`26cb622a8724018f7582225c640d5ac93e9ac8a5`).
- Do not modify production behaviour merely to make a test easier to write.
- Black-box cases must be derived from equivalence partitions and boundary values without relying on internal branch structure.
- White-box cases must state the control-flow graph, cyclomatic-complexity calculation, independent paths, and one executed test for every selected path.
- Every case must record an identifier, requirement, inputs/preconditions, expected result, actual result, and pass/fail outcome.
- The report must be written in English and delivered as a visually verified PDF.
- Keep the branch tidy: commit only focused test files, the final PDF, its concise README, and source flowcharts; do not commit secrets, caches, build directories, screenshots containing credentials, or bulky temporary logs.
- Preserve all existing backend and frontend behaviour and rerun the full verification suite before completion.

## Review Focus

- Duration boundary values 14, 15, 480, and 481 minutes must prove both valid limits and both invalid neighbours.
- A requested attendance threshold that is met, narrowly missed but still has two attendees, or cannot form a two-person group must produce three distinct run outcomes.
- A 60-minute journey must remain eligible while a 61-minute journey must be excluded.
- Missing or failed routing data must be reported as `DATA_UNAVAILABLE`, never converted into a zero-minute journey or a normal exclusion.
- `NO_RESPONSE`, `WITHDRAWN`, busy-overlap, full availability, and partial availability must remain mutually understandable in the attendance path tests.

---

### Task 1: Isolated Branch and Verified Baseline

**Files:**
- Create: isolated Git worktree for `lab4/software-testing-report`
- Verify: existing repository without modifying tracked production files

**Interfaces:**
- Consumes: remote branch `feature/production-pilot` at commit `26cb622a8724018f7582225c640d5ac93e9ac8a5`
- Produces: clean isolated checkout used by all later tasks

- [ ] **Step 1: Create the isolated worktree and branch from the production commit**

Run the repository's worktree workflow and verify `git status --short` is empty.

- [ ] **Step 2: Verify that the branch tree matches the deployed production tree**

Run: `git rev-parse HEAD^{tree}` and compare it with `git rev-parse 26cb622^{tree}`.

Expected: identical tree hashes before Lab 4 files are added.

- [ ] **Step 3: Run the baseline backend suite**

Run: `python -m pytest -q`

Expected: `264 passed` with no failures on the current verified environment.

- [ ] **Step 4: Run the baseline frontend verification**

Run: `npm test`, `npm run lint`, and `npm run build` from `frontend/`.

Expected: 21 frontend tests pass; lint and production build exit successfully.

### Task 2: Black-Box Test Design and Automation

**Files:**
- Create: `backend/tests/lab4/__init__.py`
- Create: `backend/tests/lab4/test_black_box_recommendation_engine.py`
- Reference: `backend/tests/recommender/conftest.py`
- Reference: `backend/app/recommender/engine.py`

**Interfaces:**
- Consumes: `RecommendationEngine.generate(request: RecommendationRequest) -> RecommendationResult`
- Produces: executable tests whose identifiers match the black-box report tables

- [ ] **Step 1: Write failing-or-unproven duration-boundary tests**

Add `BB-DUR-01` through `BB-DUR-04` for 14, 15, 480, and 481 minutes. Assert `ValueError` for invalid neighbours and a non-validation result for both valid limits.

- [ ] **Step 2: Run only the duration cases and record their initial result**

Run: `python -m pytest tests/lab4/test_black_box_recommendation_engine.py -k duration -vv`

Expected: every current requirement-conforming case passes; any failure is investigated before production code changes.

- [ ] **Step 3: Add attendance-threshold equivalence-partition tests**

Add cases for `OK`, `BEST_AVAILABLE_BELOW_THRESHOLD`, and `NO_TIMESLOT_MEETS_THRESHOLD`, asserting the public `RunStatus`, warning behaviour, and whether ranked output exists.

- [ ] **Step 4: Add venue, location, and routing partitions**

Add cases for a supporting venue, no supporting venue, no valid participant location, successful routing, provider-unavailable routing, and provider error. Assert only public result fields and public exceptions.

- [ ] **Step 5: Add journey-limit and weight boundaries**

Use deterministic test routers to prove 60 minutes is allowed and 61 minutes is excluded, and prove attendance weights 0 and 100 are accepted while -1 and 101 are rejected.

- [ ] **Step 6: Minimise the test set and document coverage relationships**

Remove only genuinely redundant cases; retain a mapping showing which equivalence class and boundary each remaining case covers.

- [ ] **Step 7: Run the complete black-box file**

Run: `python -m pytest tests/lab4/test_black_box_recommendation_engine.py -vv`

Expected: all named `BB-*` cases pass.

- [ ] **Step 8: Commit the black-box tests**

Commit message: `test: add Lab 4 black-box recommendation cases`

### Task 3: White-Box Basis-Path Test Design and Automation

**Files:**
- Create: `backend/tests/lab4/test_white_box_basis_paths.py`
- Create: `docs/lab4/cfg_pre_routing_exclusion.dot`
- Create: `docs/lab4/cfg_participant_availability.dot`
- Reference: `backend/app/recommender/feasibility.py`
- Reference: `backend/app/recommender/candidate_generation.py`

**Interfaces:**
- Consumes: `pre_routing_exclusion(combo, minimum_attendee_threshold, now) -> ExclusionReason | None`
- Consumes: `_ParticipantAvailability.status_for(start, end) -> AttendanceStatus`
- Produces: executed `WB-PR-*` and `WB-PA-*` cases plus two reviewable control-flow graphs

- [ ] **Step 1: Number the control-flow nodes for `pre_routing_exclusion()`**

Create a DOT graph that includes threshold, sports-category, minimum-group-size, booking-lead configuration, lead-time boundary, and normal-return decisions.

- [ ] **Step 2: Calculate cyclomatic complexity for the first method**

State both formulas, `V(G) = decisions + 1` and `V(G) = E - N + 2`, using the same node/edge interpretation shown in the graph.

- [ ] **Step 3: Write one path test for every independent path of the first method**

Cover below threshold, non-sports success, sports group-size failure, sports lead-time failure, and sports success, splitting compound-condition cases where required by the chosen graph interpretation.

- [ ] **Step 4: Number the control-flow nodes for `_ParticipantAvailability.status_for()`**

Create a DOT graph containing no response, withdrawn, busy overlap, full available coverage, and unavailable fallback.

- [ ] **Step 5: Calculate cyclomatic complexity for the second method**

Apply the same graph convention and cross-check both complexity formulas.

- [ ] **Step 6: Write one path test for every independent path of the second method**

Cover `NO_RESPONSE`, `WITHDRAWN`, busy-overlap `UNAVAILABLE`, fully covered `AVAILABLE`, and partial/no coverage `UNAVAILABLE`.

- [ ] **Step 7: Run the complete white-box file**

Run: `python -m pytest tests/lab4/test_white_box_basis_paths.py -vv`

Expected: all named `WB-*` cases pass and the executed paths equal the documented basis set.

- [ ] **Step 8: Commit the white-box tests and flowchart sources**

Commit message: `test: add Lab 4 basis-path coverage`

### Task 4: Execute Tests and Build Traceable Evidence

**Files:**
- Create: `docs/lab4/README.md`
- Generate temporarily: JUnit XML and verbose terminal output outside committed source

**Interfaces:**
- Consumes: all `BB-*`, `WB-PR-*`, and `WB-PA-*` tests
- Produces: exact expected/actual/pass data for the PDF and concise reproduction commands for GitHub

- [ ] **Step 1: Execute all Lab 4 tests with stable identifiers**

Run: `python -m pytest tests/lab4 -vv --junitxml=<temporary-path>/lab4-junit.xml`

Expected: every case passes and JUnit case names match the report identifiers.

- [ ] **Step 2: Extract actual outcomes into the report dataset**

For exception cases, record the observed exception type/message; for normal cases, record the observed status, exclusion reason, or attendance status rather than writing only `as expected`.

- [ ] **Step 3: Rerun the complete backend and frontend verification suites**

Expected: no regression relative to Task 1.

- [ ] **Step 4: Write the concise reproduction README**

Document the selected units, exact commands, environment, case-ID naming, and where the PDF is located; do not include credentials or machine-specific secret paths.

- [ ] **Step 5: Commit the evidence README**

Commit message: `docs: document Lab 4 testing reproduction`

### Task 5: Produce the English Submission PDF

**Files:**
- Create: `docs/lab4/Lab4_Software_Testing_Report.pdf`
- Use temporarily: report-generation source and rendered page images outside the committed repository

**Interfaces:**
- Consumes: the test-design mappings, DOT flowcharts, executed JUnit results, SRS requirement identifiers, and verified command summaries
- Produces: final submission-ready PDF

- [ ] **Step 1: Build the report structure**

Include title/version, scope and environment, black-box explanation, equivalence-class table, boundary-value table, minimised black-box case table, white-box explanation, two source excerpts, two control-flow graphs, complexity calculations, independent-path tables, executed result tables, regression summary, limitations, and conclusion.

- [ ] **Step 2: Populate every test row with traceable evidence**

Each row must contain case ID, requirement, preconditions/input, expected result, actual result, and pass/fail. Case IDs must exactly match the automated test names or their explicit markers.

- [ ] **Step 3: Render the PDF and inspect every page**

Use the PDF skill workflow to render all pages to images. Check tables for clipping, graph labels for legibility, headings for orphaning, page numbers, consistent fonts, and no exposed credentials or local-only secret values.

- [ ] **Step 4: Perform content cross-checks**

Verify that every equivalence class and boundary appears in at least one case, every independent path appears in exactly one or more white-box cases, both complexity formulas agree, all actual results come from the final run, and no result contradicts the current code or SRS mapping.

- [ ] **Step 5: Commit the final PDF**

Commit message: `docs: add Lab 4 software testing report`

### Task 6: Final Verification and GitHub Handoff

**Files:**
- Verify: all files added by Tasks 2–5
- Modify only if review discovers an inconsistency

**Interfaces:**
- Consumes: completed branch and rendered PDF
- Produces: pushed branch with reproducible, internally consistent Lab 4 deliverables

- [ ] **Step 1: Run final automated verification**

Run all Lab 4 tests, full backend tests, frontend tests, lint, and production build from a clean status.

- [ ] **Step 2: Audit the PDF against Lab 4 Manual sections 3.2.1–3.2.4**

Create a private checklist confirming one control class, equivalence classes, boundary values, two complex methods, basis paths, minimised test set, and documented input/expected/actual results.

- [ ] **Step 3: Cross-check repository and PDF identifiers**

Expected: no missing, duplicated, or mismatched `BB-*`, `WB-PR-*`, or `WB-PA-*` identifiers.

- [ ] **Step 4: Verify branch cleanliness and inspect the complete diff**

Run: `git status --short` and `git diff feature/production-pilot...HEAD --check`.

Expected: clean branch, no whitespace errors, no unrelated files, no secrets.

- [ ] **Step 5: Push the branch without changing production**

Push `lab4/software-testing-report` to GitHub. Do not merge it into `feature/production-pilot` unless the user later requests that action.

