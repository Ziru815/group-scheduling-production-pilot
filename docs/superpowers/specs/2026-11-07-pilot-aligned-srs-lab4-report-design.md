# Pilot-Aligned SRS and Lab 4 Testing Report Design

## Intent

Treat the deployed `feature/production-pilot` product behavior as the approved product baseline. Update the SRS, automated testing evidence, and Lab 4 report so that they describe and verify that baseline consistently. Borrow the strongest audit and basis-path techniques from the separate Strict report without importing its old repository, commit, test totals, or failure verdict.

## Authoritative Baselines

- Product source: `feature/production-pilot` at `26cb622a8724018f7582225c640d5ac93e9ac8a5`.
- Deployed product: the existing Render-hosted Pilot website; no production behavior or deployment configuration is changed by this work.
- Documentation source: `docs/SRS Group Scheduling Application v2.2.docx`.
- Testing/report branch: `lab4/software-testing-report`.

## Goals

- Publish SRS version 2.3 that formally specifies the Pilot's labelled near-match recommendation recovery.
- Preserve the Session's requested Minimum-Attendee Threshold while allowing a clearly labelled recovery result when no Timeslot meets it but at least two Participants can attend the best Timeslot.
- Keep the no-recommendation outcome when fewer than two Participants can attend any Timeslot.
- Close only the configuration decisions that are already encoded in the approved Pilot and required by the test oracle: maximum journey 60 minutes, default minimum attendance 2, Venue shortlist size 10, and Candidate Timeslot step 30 minutes.
- Strengthen the Lab 4 evidence without reproducing the Strict report's 23-page bulk.
- Use two actual class methods for the assessed white-box basis-path work.
- Retain exact input, expected output, actual output, and pass/fail evidence for every assessed case.
- Keep the final report readable, visually polished, and tied to the exact Pilot source commit.

## Non-goals

- Do not change application, database, frontend, deployment, OAuth, OneMap, Calendar, or Render behavior.
- Do not import claims from `softwarelab3/2006-SCEE-P2@1493c82`.
- Do not copy the Strict report's 49-pass/1-fail verdict, 62-test baseline, or statement that no frontend tests exist.
- Do not resolve unrelated SRS TBDs unless the approved Pilot already provides the exact value needed by this testing scope.
- Do not inflate the report with per-case JSON dumps when the same evidence is already reproducible through JUnit and committed automated tests.

## Approaches Considered

### 1. Minimal alignment

Update the near-match SRS wording and lightly revise the existing 8-page report. This is fast and low risk, but it leaves the white-box "two methods" wording debatable and provides less visible evidence than the Strict report.

### 2. Pilot-aligned hybrid - selected

Update the SRS, expand meaningful black-box boundaries, use two class methods for basis-path testing, add an explicit requirement audit and reproduction evidence, and produce a compact 12-15-page report. This offers the strongest balance of course compliance, product truth, readability, and effort.

### 3. Full Strict-scale regeneration

Recreate approximately 50 cases plus per-case JSON and opcode traces. This is defensible but unnecessarily large for Lab 4 and would reproduce extensive empty space and evidence detail that the committed tests and JUnit already provide.

## SRS Version 2.3 Changes

Create `docs/SRS Group Scheduling Application v2.3.docx` from version 2.2 and preserve version 2.2 unchanged. Render and visually verify a companion PDF for review and repository visibility.

### Revision history and product summary

- Add a 7 November 2026 revision-history row for version 2.3.
- Update the feasibility/scoring product-function summary to mention a labelled near-match recovery after the normal threshold search fails.

### UC-09 recovery flow

Replace the current single no-candidate alternative with two explicit outcomes:

1. If at least one Timeslot meets the requested Minimum-Attendee Threshold, continue with normal candidate generation and scoring.
2. If none meets it but the best-attended Timeslot has at least the System default minimum of two Participants, continue using only Timeslots at that best attendance count, return `BEST_AVAILABLE_BELOW_THRESHOLD`, preserve the requested threshold, and display the requested and actual attendance values as a warning.
3. If the best attendance is below two, return `NO_TIMESLOT_MEETS_THRESHOLD`, make no routing calls, and produce no candidate set.

### Functional requirements

- Keep FR-D1 as the normal rule: below-threshold Combinations do not enter normal scoring.
- Add FR-D1.1 for the controlled, labelled recovery path. Its output is a near-match ranked list, not a normal threshold-met result.
- Add FR-E1.1 requiring the results page to identify a near-match result and show requested versus actual attendance.
- Clarify that the Session's stored threshold is never lowered by recovery.

### Glossary, data dictionary, and configuration

- Add or amend the Near-Match Recommendation and Minimum-Attendee Threshold definitions.
- Record the public recommendation-run outcomes used by the Pilot: normal result, labelled below-threshold recovery, and no qualifying Timeslot.
- Update the relevant data-dictionary/derived-rule wording without inventing a new per-Combination feasibility enum that the code does not expose.
- Resolve Pilot configuration values used by the report: 60-minute individual journey cap, default minimum attendance 2, shortlist size 10, and 30-minute Timeslot step. Mark the corresponding Appendix C entries resolved while leaving unrelated TBDs unchanged.

## Automated Test Design

### Black-box control boundary

Continue testing `RecommendationEngine.generate()` through public requests, returned result objects, and validation exceptions. Production internals are not used as black-box oracles; expected results come from SRS v2.3 and the public Pilot contract.

Retain the existing 17 cases and add eight targeted cases borrowed conceptually from the Strict report:

- valid neighbours inside the duration limits: 16 and 479 minutes;
- valid neighbours inside the weight domain: 10% and 90%;
- Minimum-Attendee Threshold boundary: 0 rejected and 1 accepted;
- mixed supporting/non-supporting Venues retain only supporting Venues;
- routing status AVAILABLE with no duration remains data-unavailable rather than becoming a zero-minute journey.

The existing near-match case must additionally prove that the requested threshold remains 3 while the actual recommended attendance is 2 and the result is explicitly labelled `BEST_AVAILABLE_BELOW_THRESHOLD`.

Target: 25 assessed black-box cases.

### White-box methods

Use two actual class methods from the Pilot tree:

1. `AvailabilityService._validate_intervals()` - explicit loop, range, short-circuit, ordering, and overlap decisions; expected V(G)=6 with six independent paths.
2. `_ParticipantAvailability.status_for()` - record-state precedence plus BUSY/AVAILABLE generator decisions; use the explicit logical CFG convention from the Strict report; expected V(G)=9 with nine independent paths.

The CFG convention is fixed rather than left to interpretation. `_validate_intervals()` has five decisions: next interval, start before Session, end after Session, next adjacent pair, and overlap; therefore D+1=6. For `status_for()`, expand each `any(generator)` into an iterator-next decision plus its two short-circuit comparisons. Count `record_status is None`, `record_status is WITHDRAWN`, BUSY next-item, `bs < end`, `start < be`, AVAILABLE next-item, `as_ <= start`, and `end <= ae`; do not count the outer `if any(...)` again. This yields D=8, N=15, E=22, and V(G)=9.

Keep the seven existing `pre_routing_exclusion()` path tests as supplemental regressions, but do not count them as either of the two assessed method CFGs.

Target execution totals:

- 25 assessed black-box cases;
- 15 assessed white-box basis paths;
- 7 supplemental pre-routing regressions;
- 47 Lab 4 tests in the combined JUnit run, with 40 mapped assessment cases.

### Evidence and graph checks

- Maintain exact one-to-one mapping between every report case ID and its JUnit test name.
- Verify N/E/D/V(G) calculations in code.
- Verify that every declared basis path uses only declared CFG edges and that the selected path-edge vectors have rank V(G).
- Record literal observed outputs rather than writing only "as expected".
- Keep the deterministic Router boundary so OneMap availability cannot make unit evidence flaky.

## Final Report Structure

Produce a portrait-A4 report of approximately 12-15 pages using the established green/gold/cream design:

1. Cover and exact source baseline.
2. Requirement-by-requirement Lab 4 audit and scope.
3. Black-box equivalence classes, boundaries, and minimisation rationale.
4. Three compact pages of black-box cases and observed results.
5. White-box selection, source excerpts, and graph convention.
6. CFG and six basis paths for `_validate_intervals()`.
7. CFG and nine basis paths for `status_for()`.
8. Execution totals, JUnit/evidence index, SRS v2.3 traceability, limitations, and conclusion.

Tables may split only with repeated headers. Graph pages may use intentional whitespace, but ordinary result pages must not reproduce the Strict report's half-empty five-case layout.

## Reproducibility and Versioning

- The report identifies `feature/production-pilot@26cb622` as the unchanged product baseline.
- The testing/report branch contains the added tests, SRS v2.3, generator, JUnit mapping, and final report.
- The generator remains byte-for-byte deterministic for unchanged input.
- README reproduction commands must run the Lab 4 suite and regenerate the report from repository files.
- No private tokens, OAuth credentials, addresses, or Participant availability data may appear in committed artifacts.

## Verification

- Render every SRS v2.3 DOCX/PDF page and every report PDF page to PNG and inspect at full size.
- Require 25/25 assessed black-box cases and 15/15 assessed white-box cases to pass.
- Require all seven supplemental pre-routing regressions to pass.
- Run the full backend suite, frontend tests, lint, and production build.
- Any failure in those full-project checks blocks a clean completion claim and branch publication. If a failure is proven unrelated and pre-existing, document it and stop for a separate product decision rather than changing Pilot code inside this documentation/testing task.
- Assert all 40 assessment IDs, both CFG formulas, all Manual 3.2.1-3.2.4 tokens, the near-match SRS wording, and absence of placeholders or secrets in the final report.
- Generate the report twice and require identical SHA-256 hashes.
- Publish only to `lab4/software-testing-report`; do not alter or merge `feature/production-pilot` without a separate decision.

## Acceptance Criteria

- SRS v2.3, automated tests, and the report describe the same Pilot near-match behavior with no contradiction.
- The product and deployed website remain unchanged.
- The final report is more rigorous than the current 8-page version but materially shorter and easier to mark than the 23-page Strict version.
- Every claim is reproducible from the final branch and tied to the Pilot source baseline.
