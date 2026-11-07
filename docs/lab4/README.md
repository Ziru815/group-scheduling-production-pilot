# Lab 4 Software Testing Deliverable

**Work product:** Black-box and white-box test cases and executed results

**Author:** Group 1 — Software Testing

**Target version:** `feature/production-pilot` tree at `26cb622`

## Selected units

- **Black-box control boundary:** `RecommendationEngine.generate()` (`backend/app/recommender/engine.py`)
- **White-box method 1:** `pre_routing_exclusion()` (`backend/app/recommender/feasibility.py`)
- **White-box method 2:** `_ParticipantAvailability.status_for()` (`backend/app/recommender/candidate_generation.py`)

The black-box file observes only request inputs, returned result objects, and public validation errors. The white-box file follows the numbered paths in the two DOT control-flow graphs in this directory.

## Files

- `backend/tests/lab4/test_black_box_recommendation_engine.py` — 17 equivalence-class and boundary-value cases (`BB-*`)
- `backend/tests/lab4/test_white_box_basis_paths.py` — 12 basis-path cases (`WB-PR-*`, `WB-PA-*`)
- `docs/lab4/cfg_pre_routing_exclusion.dot` — control-flow graph for the first method
- `docs/lab4/cfg_participant_availability.dot` — control-flow graph for the second method
- `docs/lab4/Lab4_Software_Testing_Report.pdf` — submission report with expected and actual results

## Reproduce the assessment tests

From `backend/`, with the project dependencies installed:

```bash
python -m pytest tests/lab4 -vv
```

Expected result for this revision:

```text
29 passed
```

Run the full regression checks:

```bash
cd backend
python -m pytest -q

cd ../frontend
npm test
npm run lint
npm run build
```

Verified environment: Python 3.13.5, pytest 8.3.5, Node.js 22-compatible project toolchain. The test routers are deterministic substitutes at the external OneMap routing boundary; the recommendation engine, feasibility logic, availability logic, scoring, and result objects are real production code.

## Case-ID convention

- `BB-DUR-*` — session-duration boundaries
- `BB-THR-*` — attendance-threshold partitions
- `BB-VEN-*` — venue-support partition
- `BB-LOC-*` — valid-location partition
- `BB-RTE-*` — external-routing outcomes
- `BB-JRN-*` — maximum-journey boundary
- `BB-WGT-*` — attendance-weight boundaries
- `WB-PR-*` — independent paths through `pre_routing_exclusion()`
- `WB-PA-*` — independent paths through `_ParticipantAvailability.status_for()`

For the second white-box method, each `any(...)` expression is represented as one application-level boolean decision. Iterator implementation details inside Python are outside the control-flow graph's selected abstraction boundary; this convention is stated in the PDF and used consistently in both complexity formulas.
