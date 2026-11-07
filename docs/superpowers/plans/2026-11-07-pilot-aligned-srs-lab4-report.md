# Pilot-Aligned SRS and Lab 4 Testing Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce SRS v2.3, expanded automated testing evidence, and a polished Lab 4 report that all describe the unchanged `feature/production-pilot@26cb622` product behavior.

**Architecture:** Generate SRS v2.3 reproducibly from the preserved v2.2 DOCX, add characterization and basis-path tests without changing product code, and make the ReportLab report consume the resulting JUnit evidence. Keep the deployed Pilot tree immutable; all deliverables live on `lab4/software-testing-report` and identify the Pilot commit as the product baseline.

**Tech Stack:** Python 3.13, pytest 8.3, python-docx, ReportLab, pypdf, Poppler, Graphviz DOT, TypeScript/Vite frontend verification

**Spec:** `docs/superpowers/specs/2026-11-07-pilot-aligned-srs-lab4-report-design.md`

## Global Constraints

- Product source remains `feature/production-pilot@26cb622a8724018f7582225c640d5ac93e9ac8a5`; do not change application or deployment behavior.
- Preserve `docs/SRS Group Scheduling Application v2.2.docx`; create version 2.3 as a new artifact.
- Near-match recovery preserves the requested threshold, requires at least two attendees, labels the result `BEST_AVAILABLE_BELOW_THRESHOLD`, and produces no candidates below two.
- Resolve only Pilot configuration values needed by this scope: journey cap 60, default minimum attendance 2, shortlist 10, Timeslot step 30.
- Target 25 assessed black-box cases, 15 assessed white-box paths, and seven supplemental pre-routing regressions.
- Use two actual class methods for assessed basis-path work: `AvailabilityService._validate_intervals()` and `_ParticipantAvailability.status_for()`.
- Final report is English, portrait A4, approximately 12-15 pages, and retains the green/gold/cream visual identity.
- No secrets, tokens, private addresses, personal availability, or OAuth credentials may appear in artifacts.
- Publish only to `lab4/software-testing-report`; do not merge or modify `feature/production-pilot`.

## Review Focus

- Near-match threshold=3 with best attendance=2 must keep the public requested threshold at 3, rank only two-attendee options, and display an explicit warning; Task 2 adds the assertion.
- Threshold=1 must remain a valid explicit organiser value even though near-match recovery itself requires the System default minimum of two; Task 2 adds the boundary case.
- `AVAILABLE` routing with `minutes=None` must remain data-unavailable rather than a zero-minute journey; Task 2 adds the provider-contract case.
- Generator-loop CFG paths must include zero-iteration, short-circuit-false, later-iteration, and true-return behavior without double-counting `if any(...)`; Task 3 pins all nine paths and graph rank.
- SRS v2.3 must not leave stale v2.2 version text, unresolved entries for the four adopted Pilot constants, or a normal-flow statement that contradicts recovery; Task 1 runs extracted-text assertions and full-page visual inspection.

---

### Task 1: Generate and visually verify SRS version 2.3

**Files:**
- Create: `docs/srs/update_v2_3.py`
- Create: `docs/SRS Group Scheduling Application v2.3.docx`
- Create: `docs/SRS Group Scheduling Application v2.3.pdf`
- Verify unchanged: `docs/SRS Group Scheduling Application v2.2.docx`

**Interfaces:**
- Consumes: v2.2 DOCX paragraphs and tables; Pilot constants from `backend/app/recommender/config.py`.
- Produces: `update_document(source: Path, output: Path) -> None` and a v2.3 DOCX/PDF whose extracted text is the documentation oracle for Tasks 2-4.

- [ ] **Step 1: Add a structural check that fails on v2.2**

  In `docs/srs/update_v2_3.py`, add `assert_v2_3(document: Document) -> None` with literal checks for `Version 2.3`, `BEST_AVAILABLE_BELOW_THRESHOLD`, `NO_TIMESLOT_MEETS_THRESHOLD`, requested threshold preservation, actual attendance display, and resolved values 60/2/10/30.

- [ ] **Step 2: Run the check against v2.2 and verify RED**

  Run: bundled Python calling `assert_v2_3(Document("docs/SRS Group Scheduling Application v2.2.docx"))`.

  Expected: FAIL on the missing `Version 2.3`/near-match wording.

- [ ] **Step 3: Implement deterministic paragraph/table updates**

  Implement `update_document(source, output)` using python-docx. Update the cover version/date, revision-history table, product-function summary, UC-09 alternative flow, FR-D1, new FR-D1.1, new FR-E1.1, glossary/data-dictionary wording, configuration table, and Appendix C resolution state exactly as specified by the design. Preserve existing styles, images, section breaks, headers, footers, and v2.2 source.

- [ ] **Step 4: Generate v2.3 and verify structural GREEN**

  Run: bundled Python `docs/srs/update_v2_3.py`.

  Expected: v2.3 DOCX is created; `assert_v2_3` passes; a SHA-256 check proves v2.2 is unchanged.

- [ ] **Step 5: Render DOCX to PDF and every page to PNG**

  Use the bundled documents `render_docx.py` workflow and Poppler. Inspect the cover, revision history, table of contents, UC-09, FR-D1/FR-D1.1, FR-E1/FR-E1.1, glossary, data dictionary, configuration, and Appendix C pages at full size.

  Expected: no clipping, broken tables, missing figures, stale version text, or visibly stale TOC entry.

- [ ] **Step 6: Commit the SRS artifacts**

  ```bash
  git add docs/srs/update_v2_3.py \
    "docs/SRS Group Scheduling Application v2.3.docx" \
    "docs/SRS Group Scheduling Application v2.3.pdf"
  git commit -m "docs: align SRS with Pilot near-match recovery"
  ```

---

### Task 2: Expand Pilot-aligned black-box evidence to 25 cases

**Files:**
- Modify: `backend/tests/lab4/test_black_box_recommendation_engine.py`

**Interfaces:**
- Consumes: `RecommendationEngine.generate(request) -> RecommendationResult`, SRS v2.3 near-match oracle, existing deterministic `FixedRouter`.
- Produces: 25 uniquely named `BB-*` pytest cases and literal public outcomes for the report generator.

- [ ] **Step 1: Strengthen the existing near-match test**

  Extend `test_bb_thr_02_returns_best_available_when_requested_threshold_is_narrowly_missed` to assert `minimum_attendee_threshold == 3`, all ranked `attendee_count == 2`, status `BEST_AVAILABLE_BELOW_THRESHOLD`, and a warning containing requested 3 and actual 2.

- [ ] **Step 2: Add duration and weight valid-neighbour cases**

  Add tests for duration 16, duration 479, attendance weight 10, and attendance weight 90; each must return `RunStatus.OK` and ranked options while preserving the literal accepted value.

- [ ] **Step 3: Add Minimum-Attendee Threshold boundary cases**

  Add threshold 0 rejection with the exact public validation message and threshold 1 acceptance with one available Participant and a normal `RunStatus.OK` result.

- [ ] **Step 4: Add mixed-Venue and missing-duration routing cases**

  Add one request containing supporting and non-supporting Venues and assert only supporting Venue IDs enter the shortlist/ranking. Add a Router response with status AVAILABLE and `minutes=None` and assert DATA_UNAVAILABLE/no fabricated zero travel/no rank.

- [ ] **Step 5: Run the black-box file and verify 25 passing cases**

  Run: `cd backend && python -m pytest tests/lab4/test_black_box_recommendation_engine.py -q`.

  Expected: `25 passed`.

- [ ] **Step 6: Mutation-check the new assertions**

  Temporarily invert one literal expected value in each new input class, run the named test and observe the expected failure, then restore the correct assertion and rerun all 25. Do not commit the intentional mutations.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/tests/lab4/test_black_box_recommendation_engine.py
  git commit -m "test: expand Pilot black-box boundaries"
  ```

---

### Task 3: Replace assessed white-box scope with two class methods

**Files:**
- Create: `backend/tests/lab4/test_pre_routing_regressions.py`
- Modify: `backend/tests/lab4/test_white_box_basis_paths.py`
- Create: `docs/lab4/cfg_validate_intervals.dot`
- Modify: `docs/lab4/cfg_participant_availability.dot`

**Interfaces:**
- Consumes: `AvailabilityService._validate_intervals(item, intervals) -> list`, `_ParticipantAvailability.status_for(start, end) -> AttendanceStatus`.
- Produces: six `WB-IV-*` tests, nine `WB-PA-*` tests, seven supplemental `WB-PR-*` regressions, and CFG edge/path data used by Task 4.

- [ ] **Step 1: Preserve seven pre-routing paths as supplemental regressions**

  Move the existing `WB-PR-*` tests and only their helpers into `test_pre_routing_regressions.py`. Run the file and require seven passes before changing the assessed white-box file.

- [ ] **Step 2: Add six `_validate_intervals()` basis-path tests**

  Cover no intervals; one interval starting one minute before the Session; one ending one minute after; exact endpoints; one-minute overlap; and unsorted touching intervals. Assert literal ordered outputs or HTTP 422 status/detail for paths IV-01 through IV-06.

- [ ] **Step 3: Expand `status_for()` to nine logical basis paths**

  Cover active with no blocks; no response; withdrawn; BUSY starts exactly at slot end; BUSY ends exactly at slot start; one-minute BUSY overlap overriding full availability; AVAILABLE starts one minute late; AVAILABLE ends one minute early; and exact full AVAILABLE coverage.

- [ ] **Step 4: Encode both CFGs**

  Create DOT graphs with common exits and the fixed decision convention: IV has N=10/E=14/D=5/V=6; PA has N=15/E=22/D=8/V=9. Label every edge used by the path tables.

- [ ] **Step 5: Run the assessed and supplemental files**

  Run: `cd backend && python -m pytest tests/lab4/test_white_box_basis_paths.py tests/lab4/test_pre_routing_regressions.py -q`.

  Expected: `22 passed` (15 assessed plus seven supplemental).

- [ ] **Step 6: Commit**

  ```bash
  git add backend/tests/lab4/test_white_box_basis_paths.py \
    backend/tests/lab4/test_pre_routing_regressions.py \
    docs/lab4/cfg_validate_intervals.dot \
    docs/lab4/cfg_participant_availability.dot
  git commit -m "test: strengthen Lab 4 basis-path evidence"
  ```

---

### Task 4: Generate the compact rigorous Lab 4 report

**Files:**
- Modify: `docs/lab4/generate_report.py`
- Modify: `docs/lab4/README.md`
- Modify: `docs/lab4/Lab4_Software_Testing_Report.pdf`
- Generate: `.superpowers/sdd/2026-11-07-pilot-aligned-srs-lab4-report/lab4-junit.xml`

**Interfaces:**
- Consumes: 47-case JUnit XML, 40 assessment-case mappings, SRS v2.3 wording, two production source excerpts, and both CFG/path datasets.
- Produces: deterministic 12-15-page portrait-A4 PDF and `verify_basis_graph(nodes, edges, paths) -> int` assertions.

- [ ] **Step 1: Generate fresh 47-case JUnit evidence**

  Run all `backend/tests/lab4` tests with `--junitxml` at the task-specific path.

  Expected: 47 passed; JUnit contains 25 `BB-*`, six `WB-IV-*`, nine `WB-PA-*`, and seven supplemental `WB-PR-*` names.

- [ ] **Step 2: Replace report case datasets and graph verification**

  Update the generator to map exactly 40 assessed IDs to JUnit names, report the seven supplemental regressions separately, and implement `verify_basis_graph()` to assert declared edge membership, coverage, and rational path-vector rank 6/9.

- [ ] **Step 3: Rebuild report sections**

  Add the requirement audit, Pilot source/evidence baseline, SRS v2.3 near-match trace, 25 black-box rows over three compact pages, two class-method source excerpts/CFGs/path tables, execution evidence, limitations, and conclusion. Remove all `pre_routing_exclusion()` claims from the two-method assessment while retaining its supplemental-test count.

- [ ] **Step 4: Add structural assertions**

  Require 12-15 pages, 40 unique assessment IDs, exact JUnit mapping, totals 25/15/7/47, formulas `14 - 10 + 2 = 6` and `22 - 15 + 2 = 9`, Manual 3.2.1-3.2.4, near-match status/warning, Pilot SHA `26cb622`, and absence of secrets/placeholders.

- [ ] **Step 5: Generate twice and verify deterministic output**

  Run the generator twice with a one-second separation.

  Expected: both runs pass and produce the same SHA-256.

- [ ] **Step 6: Render and visually inspect every report page**

  Render all pages at 130 DPI. Inspect a contact sheet and every full-size page, especially wide case tables, both CFGs, repeated headers, source excerpts, evidence summary, and footer numbering.

  Expected: no clipping, overlap, unreadable text, orphan headings, or avoidable half-empty result pages.

- [ ] **Step 7: Update reproduction documentation and commit**

  Document SRS generation, 47-case JUnit generation, report generation, full verification commands, and artifact locations.

  ```bash
  git add docs/lab4/generate_report.py docs/lab4/README.md \
    docs/lab4/Lab4_Software_Testing_Report.pdf
  git commit -m "docs: publish Pilot-aligned Lab 4 report"
  ```

---

### Task 5: Full verification, review, and branch publication

**Files:**
- Verify: all Task 1-4 outputs
- Verify unchanged: application source relative to `26cb622`

**Interfaces:**
- Consumes: complete branch from Tasks 1-4.
- Produces: a clean local and remote `lab4/software-testing-report` tree with no product-code differences from the Pilot baseline.

- [ ] **Step 1: Prove no product code changed**

  Compare `backend/app`, `frontend/src`, deployment files, and database migrations to `26cb622`.

  Expected: no differences introduced by this plan.

- [ ] **Step 2: Run full verification**

  Run the 47 Lab 4 tests, full backend suite, frontend tests, lint, production build, SRS generator/assertions, report generator twice, and extracted-text audits.

  Expected: all commands exit 0; only the already-known third-party Starlette/anyio deprecation warning may remain.

- [ ] **Step 3: Review the complete branch diff**

  Inspect all changed files against the design and run `git diff --check` plus a secret/placeholder scan. Critical or Important findings must be fixed before publication.

- [ ] **Step 4: Update the existing GitHub branch**

  Publish `lab4/software-testing-report` with a lease; do not modify `feature/production-pilot`.

- [ ] **Step 5: Verify local/remote identity**

  Compare local `HEAD^{tree}` with the remote commit tree SHA.

  Expected: exact match.
