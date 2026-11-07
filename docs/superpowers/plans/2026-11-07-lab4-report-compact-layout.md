# Lab 4 Report Compact Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the complete Lab 4 Software Testing Report as a polished, compact portrait-A4 submission with substantially less avoidable whitespace and no loss of assessed content.

**Architecture:** Promote the existing ReportLab generator into the documented Lab 4 folder, then adjust graph geometry, section flow, and page-break policy while preserving the existing case data and verification assertions. Regenerate the PDF, validate its text and case mapping programmatically, render every page through Poppler, and iterate from visual evidence.

**Tech Stack:** Python 3.13, ReportLab, pypdf, pytest JUnit XML, Poppler `pdftoppm`

**Spec:** `docs/superpowers/specs/2026-11-07-lab4-report-compact-layout-design.md`

## Global Constraints

- Preserve all 17 black-box cases and all 12 white-box cases without renaming identifiers.
- Preserve both CFG node/edge counts and complexity results: 13/18/7 and 11/14/5.
- Preserve Manual 3.2.1-3.2.4 evidence and every input/expected/actual/result field.
- Keep portrait A4, English content, and the established green/gold/cream visual identity.
- Do not change application code, automated test behaviour, or observed test results.
- Prefer 9-10 pages, but do not sacrifice readability to hit an exact count.

## Review Focus

- A wide test table may become unreadably small after compaction; the rendered A4 page must keep every cell legible and repeat headers after a split.
- A reduced CFG may cause node labels or arrows to overlap; every graph node, label, and branch marker must remain distinguishable.
- Removing forced breaks may leave an isolated heading or caption; no heading may be stranded at a page bottom.
- A compact conclusion may accidentally remove limitations or Manual traceability; both must remain directly visible.
- Generator and PDF may drift from JUnit evidence; final validation must require exact equality of all 29 mapped test names.

---

### Task 1: Create the compact reproducible report generator

**Files:**
- Create: `docs/lab4/generate_report.py`
- Modify: `docs/lab4/README.md`
- Modify: `docs/lab4/Lab4_Software_Testing_Report.pdf`

**Interfaces:**
- Consumes: `.superpowers/sdd/2026-11-07-lab4-software-testing-report/lab4-junit.xml`, the two production method sources, and the existing case datasets.
- Produces: `build_story() -> list`, `main() -> None`, and a portrait-A4 PDF whose extracted text contains the required case IDs, formulas, and Manual requirements.

- [ ] **Step 1: Add structural assertions before changing layout**

  Add generator checks asserting 29 unique report case IDs, exact JUnit test-name equality, both complexity formulas, Manual tokens 3.2.1-3.2.4, and a final page count between 9 and 10.

- [ ] **Step 2: Run the current layout against the new page-count check**

  Run: bundled Python `docs/lab4/generate_report.py`.

  Expected: FAIL because the current report is 12 pages.

- [ ] **Step 3: Implement compact page flow**

  Reduce both CFG drawing heights, tighten only nonessential spacing, remove forced page breaks that create single-purpose pages, keep major-method transitions intentional, and allow long tables to split with repeated headers.

- [ ] **Step 4: Regenerate and verify structural GREEN**

  Run: bundled Python `docs/lab4/generate_report.py`.

  Expected: PASS; report is 9-10 pages and every structural assertion succeeds.

- [ ] **Step 5: Document reproducible generation**

  Update `docs/lab4/README.md` with the generator command, required bundled dependencies, output path, and verification expectations.

- [ ] **Step 6: Commit**

  ```bash
  git add docs/lab4/generate_report.py docs/lab4/README.md docs/lab4/Lab4_Software_Testing_Report.pdf
  git commit -m "docs: compact Lab 4 testing report"
  ```

---

### Task 2: Render and visually refine every page

**Files:**
- Modify: `docs/lab4/generate_report.py`
- Modify: `docs/lab4/Lab4_Software_Testing_Report.pdf`
- Render: `.superpowers/sdd/2026-11-07-lab4-report-compact-layout/tmp/pdfs/page-*.png`

**Interfaces:**
- Consumes: Task 1's structurally valid PDF.
- Produces: a fully rendered page set with no clipping, overlap, broken table, isolated heading, unreadable graph label, or avoidable large blank region.

- [ ] **Step 1: Render the complete PDF**

  Run Poppler `pdftoppm -png` into the task-specific `tmp/pdfs/` directory.

  Expected: one PNG per PDF page, with no renderer errors.

- [ ] **Step 2: Inspect a contact sheet and every full-size page**

  Check page balance, table legibility, graph arrows, captions, section transitions, headers, footers, and page numbers. Record every visible defect before editing.

- [ ] **Step 3: Correct all visible defects in one bounded pass**

  Adjust only spacing, sizing, break policy, and graph geometry. Do not change case facts, calculations, or outcomes.

- [ ] **Step 4: Regenerate, rerender, and re-inspect**

  Expected: zero visual defects and no page with a large avoidable blank region; the cover may retain intentional whitespace.

- [ ] **Step 5: Commit visual refinements if changed**

  ```bash
  git add docs/lab4/generate_report.py docs/lab4/Lab4_Software_Testing_Report.pdf
  git commit -m "docs: refine Lab 4 report pagination"
  ```

---

### Task 3: Cross-check content and publish the revised branch

**Files:**
- Verify: `backend/tests/lab4/test_black_box_recommendation_engine.py`
- Verify: `backend/tests/lab4/test_white_box_basis_paths.py`
- Verify: `docs/lab4/Lab4_Software_Testing_Report.pdf`
- Verify: `docs/lab4/README.md`

**Interfaces:**
- Consumes: Task 2's visually approved PDF and the existing automated tests.
- Produces: a clean `lab4/software-testing-report` branch whose remote tree exactly matches the reviewed local tree.

- [ ] **Step 1: Run Lab 4 and full regression verification**

  Run the 29 Lab 4 tests, full backend pytest suite, frontend tests, lint, and production build.

  Expected: 29/29 Lab 4, 293/293 backend, 21/21 frontend, lint exit 0, build exit 0.

- [ ] **Step 2: Reopen and audit PDF text**

  Assert page count, 29 unique case IDs, exact JUnit mapping, both formulas, all Manual tokens, PASS totals, and absence of secrets or placeholders.

- [ ] **Step 3: Inspect the complete branch diff**

  Run: `git diff 26cb622..HEAD --check`, `git status --short`, and inspect all changed paths.

  Expected: no whitespace errors, unrelated files, credentials, or application changes.

- [ ] **Step 4: Update the existing remote branch without touching production**

  Publish `lab4/software-testing-report`; do not merge or modify `feature/production-pilot`.

- [ ] **Step 5: Verify remote/local content identity**

  Compare the remote branch tree SHA with local `HEAD^{tree}`.

  Expected: exact match.
