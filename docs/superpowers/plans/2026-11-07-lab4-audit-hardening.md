# Lab 4 Audit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an auditable, production-aligned Lab 4 testing PDF with durable execution evidence and readable complete CFG/path documentation.

**Architecture:** Keep the product baseline immutable. Harden the test harness and SRS oracle first, commit durable execution evidence second, then generate the report against that immutable evidence commit.

**Tech Stack:** Python, pytest, ReportLab, OOXML, Git/GitHub, React/Vite test scripts

**Spec:** `docs/superpowers/specs/2026-11-07-lab4-audit-hardening-design.md`

## Global Constraints

- Do not modify production or deployment implementation paths.
- Keep 25 assessed black-box and 15 assessed white-box cases; count configuration guards as supplemental.
- Use deployed values 60 / 2 / 10 / 15 for journey cap, default attendance, shortlist and timeslot step.
- Keep SRS v2.2 byte-for-byte unchanged.
- Use stable `docs/lab4/evidence/` paths and immutable GitHub evidence links.
- Generate and visually inspect every final PDF and DOCX page.

## Review Focus

- The Lab 4 helper must actually produce consecutive candidate starts 15 minutes apart.
- No report wording may promote an unverified `1493c82` reference over the Render-deployed branch.
- Actual Output cells must contain observed literals rather than assertion descriptions.
- Every path must include entry, exit and explicit branch outcomes.
- JUnit failures, errors, skips or duplicate names must still block report generation.

---

### Task 1: Align the test oracle with production configuration

**Files:**
- Modify: `backend/tests/lab4/test_black_box_recommendation_engine.py`
- Modify: `backend/tests/lab4/test_pre_routing_regressions.py`
- Modify: `docs/srs/test_update_v2_3.py`
- Modify: `docs/srs/update_v2_3.py`
- Regenerate: `docs/SRS Group Scheduling Application v2.3.docx`
- Regenerate: `docs/SRS Group Scheduling Application v2.3.pdf`

**Interfaces:**
- Consumes: deployed settings values 60 / 2 / 10 / 15.
- Produces: a production-aligned Lab 4 harness and verified SRS v2.3.

- [ ] **Step 1: Write failing production-step and SRS regression tests**
- [ ] **Step 2: Run the focused tests and verify the 30-versus-15 mismatch fails**
- [ ] **Step 3: Configure the harness and SRS generator with the deployed 15-minute step**
- [ ] **Step 4: Run focused and full Lab 4 tests**
- [ ] **Step 5: Regenerate and verify SRS v2.3 while preserving v2.2**
- [ ] **Step 6: Commit the production-oracle alignment**

### Task 2: Publish durable execution evidence

**Files:**
- Create: `docs/lab4/evidence/lab4-junit.xml`
- Create: `docs/lab4/evidence/backend-lab4.txt`
- Create: `docs/lab4/evidence/backend-full.txt`
- Create: `docs/lab4/evidence/frontend-test.txt`
- Create: `docs/lab4/evidence/frontend-lint.txt`
- Create: `docs/lab4/evidence/frontend-build.txt`
- Create: `docs/lab4/evidence/README.md`
- Modify: `docs/lab4/README.md`

**Interfaces:**
- Consumes: Task 1's production-aligned tests.
- Produces: an immutable evidence commit SHA consumed by Task 3.

- [ ] **Step 1: Execute Lab 4 tests with JUnit and capture plain-text output**
- [ ] **Step 2: Execute full backend and frontend verification and capture outputs**
- [ ] **Step 3: Document exact reproduction commands and evidence meanings**
- [ ] **Step 4: Commit evidence and record its immutable SHA**

### Task 3: Harden report content and CFG presentation

**Files:**
- Modify: `docs/lab4/test_generate_report.py`
- Modify: `docs/lab4/generate_report.py`
- Modify: `docs/lab4/cfg_validate_intervals.dot`
- Modify: `docs/lab4/cfg_participant_availability.dot`
- Regenerate: `docs/lab4/Lab4_Software_Testing_Report.pdf`

**Interfaces:**
- Consumes: Task 2 evidence commit SHA and stable evidence paths.
- Produces: the final auditable PDF.

- [ ] **Step 1: Write failing structural guards for exact outputs, full paths, stable evidence and traceability**
- [ ] **Step 2: Verify the guards fail on the current report generator**
- [ ] **Step 3: Replace placeholder outputs, expand paths and add named authors/baseline evidence**
- [ ] **Step 4: Redraw CFGs with separated branch labels and readable routing**
- [ ] **Step 5: Generate the PDF and make all structural guards green**
- [ ] **Step 6: Commit the report hardening**

### Task 4: Verify, review and publish

**Files:**
- Update: `Lab4_Software_Testing_Report_FINAL.pdf`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: verified local/GitHub branch and direct submission PDF.

- [ ] **Step 1: Run the full backend, frontend, Lab 4 and document test suites**
- [ ] **Step 2: Render every SRS and report page to PNG and inspect at 100%**
- [ ] **Step 3: Run independent review and address all critical/important findings**
- [ ] **Step 4: Push `lab4/software-testing-report` without merging the production branch**
- [ ] **Step 5: Verify local and remote trees match and copy the final PDF to the delivery path**

