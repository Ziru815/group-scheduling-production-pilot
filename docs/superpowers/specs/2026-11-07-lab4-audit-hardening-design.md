# Lab 4 Audit Hardening Design

## Intent

Revise the Lab 4 software-testing submission so that a lecturer can trace every compliance claim to the deployed Pilot configuration, an exact executed result, a complete basis path, and durable repository evidence. The submitted PDF remains concise and professional; the product and deployment implementation remain unchanged.

## Goals

- Keep `feature/production-pilot` commit `26cb622a8724018f7582225c640d5ac93e9ac8a5` as the tested production baseline because `render.yaml` deploys that branch.
- Align the test harness and SRS v2.3 with the deployed 15-minute timeslot step.
- Record v2.3 as the approved as-built testing baseline, with a named testing-workstream approver and revision history.
- Replace prose placeholders in Actual Output with exact observed strings, statuses, values and ordered endpoints.
- Show every basis path from entry to common exit and state the shared fixtures explicitly.
- Redraw both CFGs so decision labels and True/False branches are readable without crossings through nodes.
- Commit durable JUnit and command-output evidence and cite an immutable evidence commit in the report.
- Identify Ziru Gao and Group 1 Software Testing on the cover.

## Non-goals

- Do not change `backend/app`, `frontend/src`, `render.yaml`, migrations, or deployed behaviour.
- Do not switch the report to an unverified `1493c82` baseline.
- Do not claim that automated unit tests replace live integration checks for Google OAuth, OneMap, PostgreSQL or Render.
- Do not inflate the report with complete raw logs; provide compact summaries plus repository evidence.

## Constraints

- Lab 4 Manual sections 3.2.1-3.2.4 remain the assessment oracle.
- The report must preserve 25 assessed black-box cases and 15 assessed white-box basis paths.
- A production-configuration guard may be supplemental and must be counted separately.
- SRS v2.2 remains unchanged.
- Final PDF and DOCX/PDF SRS artifacts must be deterministic, render cleanly and contain no temporary `.superpowers` evidence paths.

## Approaches

### A. Prose-only patch

Keep all existing tests and only reword the PDF. This is fast but leaves the 30-minute test-harness default inconsistent with the deployed 15-minute configuration and does not create independently verifiable evidence.

### B. Evidence-first hardening — chosen

First make the Lab 4 harness exercise the deployed configuration, then generate durable evidence, and finally regenerate the SRS and report from those verified facts. This costs several focused commits but directly addresses the academic and technical risks without touching product code.

### C. Rewrite the report and test suite

Rebuild the submission from scratch. This would discard already verified equivalence classes, boundary cases and path-rank checks, increasing risk without improving the underlying assessment.

## Design

1. Add a supplemental guard that observes 15-minute candidate starts through the real recommendation engine. Update the Lab 4 harness to instantiate `RecommenderConfig` with the same values supplied by the deployed integration service: journey 60, minimum attendance 2, shortlist 10 and step 15.
2. Update the v2.3 generator and regression checks from a 30-minute to a 15-minute timeslot step. The revision row names Ziru Gao as the testing-workstream approver while retaining the project group identity.
3. Run the Lab 4, full backend and frontend verification commands and save their outputs under `docs/lab4/evidence/`. Save JUnit XML at a stable path and commit this evidence before generating the final report.
4. Regenerate the report with the immutable evidence commit SHA and repository URLs. Replace all placeholder Actual Output prose, expand the six interval and nine participant paths from entry to exit, and document common fixtures.
5. Improve the two CFG drawings using wider decision spacing, separate branch channels and explicit T/F labels. Allow an extra page if necessary rather than shrinking text.
6. Run structural guards, full suites, deterministic generation and complete visual inspection before publishing the branch and copying the final submission PDF to the simple delivery path.

## Success Criteria

- The production-configuration guard fails with the old harness and passes after the harness uses 15 minutes.
- Generated SRS v2.3 contains 15-minute wording and no adopted 30-minute wording.
- The report contains no `exact public message`, `exact range detail`, `literal ascending endpoints`, `loop valid intervals`, or `.superpowers/sdd` strings.
- Every white-box path starts at `N1` and ends at the common exit.
- The evidence directory contains JUnit XML and backend/frontend command summaries cited by an immutable GitHub commit.
- All backend, frontend, Lab 4 and document-guard tests pass.
- All rendered report and SRS pages are visually clean.

