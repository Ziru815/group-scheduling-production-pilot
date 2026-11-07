# Lab 4 Software Testing Deliverable

**Work product:** black-box and white-box test cases, control-flow graphs, executed results and traceability

**Author:** Group 1 — Software Testing

**Production baseline:** `feature/production-pilot` at `26cb622a8724018f7582225c640d5ac93e9ac8a5`

**Requirements oracle:** `docs/SRS Group Scheduling Application v2.3.docx`

## Assessed scope

- **Black-box control boundary:** `RecommendationEngine.generate()` — 25 equivalence-class and boundary-value cases.
- **White-box method 1:** `AvailabilityService._validate_intervals()` — six basis paths; `N=10`, `E=14`, `V(G)=6`.
- **White-box method 2:** `_ParticipantAvailability.status_for()` — nine basis paths; `N=15`, `E=22`, `V(G)=9` under the documented expanded short-circuit convention.
- **Supplemental evidence:** seven `pre_routing_exclusion()` regressions, reported separately and not counted as either assessed white-box method.

The fresh Lab 4 result is **47 passed**: 40 assessed cases plus seven supplemental regressions.

## Files

- `backend/tests/lab4/test_black_box_recommendation_engine.py` — 25 `BB-*` cases.
- `backend/tests/lab4/test_white_box_basis_paths.py` — six `WB-IV-*` and nine `WB-PA-*` assessed paths.
- `backend/tests/lab4/test_pre_routing_regressions.py` — seven supplemental `WB-PR-*` cases.
- `docs/lab4/cfg_validate_intervals.dot` — interval-validation CFG.
- `docs/lab4/cfg_participant_availability.dot` — participant-attendance CFG.
- `docs/lab4/generate_report.py` — deterministic ReportLab generator with JUnit, graph-rank, SRS and PDF structural checks.
- `docs/lab4/Lab4_Software_Testing_Report.pdf` — 12–15 page submission report.
- `docs/srs/update_v2_3.py` — deterministic SRS v2.3 generator/verifier.
- `docs/SRS Group Scheduling Application v2.3.docx` and `.pdf` — Pilot-aligned SRS artifacts.

## 1. Generate or verify SRS v2.3

From the repository root, using a Python environment with `python-docx` and `lxml`:

```bash
python docs/srs/update_v2_3.py \
  "docs/SRS Group Scheduling Application v2.2.docx" \
  "docs/SRS Group Scheduling Application v2.3.docx"

python docs/srs/update_v2_3.py \
  "docs/SRS Group Scheduling Application v2.3.docx"
```

The source v2.2 file is retained unchanged. The generated v2.3 documents the Pilot's labelled best-available recovery and adopted values 60 / 2 / 10 / 30.

## 2. Generate fresh 47-case JUnit evidence

```bash
mkdir -p .superpowers/sdd/2026-11-07-pilot-aligned-srs-lab4-report
cd backend
python -m pytest tests/lab4 -q \
  --junitxml=../.superpowers/sdd/2026-11-07-pilot-aligned-srs-lab4-report/lab4-junit.xml
cd ..
```

Expected result:

```text
47 passed
```

The JUnit file must contain exactly 25 `test_bb_*`, six `test_wb_iv_*`, nine `test_wb_pa_*` and seven `test_wb_pr_*` names with no failures or errors.

## 3. Generate the deterministic PDF report

The generator requires `reportlab`, `pypdf`, `python-docx` and `lxml`:

```bash
python docs/lab4/generate_report.py
```

Expected result: a portrait-A4 PDF with 12–15 pages, exactly 40 unique assessed case IDs, the seven supplemental regressions, verified graph edge coverage/path-vector ranks, Manual 3.2.1–3.2.4 traceability and the SRS v2.3 near-match evidence.

To verify deterministic output, run the generator twice and compare SHA-256 hashes:

```bash
python docs/lab4/generate_report.py
shasum -a 256 docs/lab4/Lab4_Software_Testing_Report.pdf
python docs/lab4/generate_report.py
shasum -a 256 docs/lab4/Lab4_Software_Testing_Report.pdf
```

## 4. Reproduce all verification

```bash
cd backend
python -m pytest -q

cd ../frontend
npm test
npm run lint
npm run build
```

Verified baseline results:

- backend: 311 passed; one third-party deprecation warning;
- frontend Node/UI tests: 21 passed;
- lint: passed;
- production build: passed, 152 modules transformed.

The test router is a deterministic substitute only at the external OneMap provider port. All recommendation, candidate-generation, feasibility, routing-adaptation, scoring and result logic under assessment is real production code.

## Case-ID convention

- `BB-DUR-*` — duration boundaries.
- `BB-THR-*` — threshold partitions and Pilot near-match recovery.
- `BB-VEN-*` — activity/venue support.
- `BB-LOC-*` — valid-origin partition.
- `BB-RTE-*` — provider outcomes and malformed responses.
- `BB-JRN-*` — maximum-journey boundary.
- `BB-WGT-*` — score-weight boundaries and valid neighbours.
- `WB-IV-*` — independent paths through `_validate_intervals()`.
- `WB-PA-*` — independent paths through `status_for()`.
- `WB-PR-*` — supplemental pre-routing regressions.
