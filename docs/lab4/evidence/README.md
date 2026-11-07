# Lab 4 execution evidence

This directory contains the committed, reproducible execution evidence used by
`docs/lab4/Lab4_Software_Testing_Report.pdf`.

## Verified source state

- Product baseline under test: `feature/production-pilot` at
  `26cb622a8724018f7582225c640d5ac93e9ac8a5`.
- Test-oracle alignment commit: the parent of this evidence commit.
- Requirements oracle: `docs/SRS Group Scheduling Application v2.3.docx`.
- Production recommendation constants exercised by the Lab 4 harness:
  journey cap `60`, default attendance `2`, shortlist `10`, timeslot step
  `15` minutes.

## Evidence files

- `lab4-junit.xml` — machine-readable results for 48 unique Lab 4 tests.
- `backend-lab4.txt` — human-readable Lab 4 pytest summary.
- `backend-full.txt` — full backend regression summary.
- `frontend-test.txt` — Node and UI test output.
- `frontend-lint.txt` — frontend lint output.
- `frontend-build.txt` — production build output.

The 48 Lab 4 tests comprise 40 assessed cases (25 black-box plus 15 white-box)
and eight supplemental guards (seven pre-routing regressions plus the
production 15-minute-step configuration guard).

## Reproduction

Run these commands from the repository root in environments with the backend
and frontend dependencies installed:

```bash
cd backend
python -m pytest -q tests/lab4 \
  --junitxml=../docs/lab4/evidence/lab4-junit.xml
python -m pytest -q

cd ../frontend
npm test
npm run lint
npm run build
```

Expected summaries for this evidence commit:

- Lab 4: `48 passed`.
- Full backend: `312 passed, 1 warning` (third-party Starlette deprecation).
- Frontend: `21 passed`.
- Lint: passed.
- Build: passed; `152 modules transformed`.

The OneMap routing provider is replaced only at the external provider port with
a deterministic test double. Candidate generation, feasibility, scoring,
ranking, result statuses and validation are production implementation code.

