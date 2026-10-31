# SRS v2.2 Implementation Traceability

## Implemented end to end

| SRS area | Implementation |
|---|---|
| FR-A1 to FR-A5 | Session create, invitation, edit, deadline and threshold validation, cancellation, role checks, and shared status. |
| FR-B1 to FR-B7 | Join, click or drag interval payloads, signed location candidates, transport mode, edit, retained withdrawal, organiser response status, and owner-only location responses. |
| FR-C1 to FR-C6 | Daily Candidate Timeslot enumeration, four-state attendance, activity filtering, centroid shortlist, category-aware constraints, and twenty reviewed Picnic parks from `DATA_GOV_SG_NPARKS_PARKS`. Picnic evidence: `nparks_geojson_adapter.py`, `park_catalog.py`, `test_park_catalog.py`, and `test_picnic_web_integration.py`. |
| FR-D1 to FR-D10 | Pre-routing feasibility, bounded provider routing, journey cap, both Travel Objectives, normalized attendance and travel scores, 10 percent weights, deterministic ranking, and persisted evidence. Park regressions prove sports-only group-size/booking rules do not exclude parks; the three-origin integration test proves deterministic ranks. |
| FR-E1 to FR-E5 | Ranked detail, per-Participant travel time and mode, attendance lists, organiser-only confirmation, and confirmed shared page. |
| NFR-3, NFR-8, NFR-9, NFR-11, NFR-13, NFR-15, NFR-16 | Explicit provider-unavailable results with no zero-minute/straight-line substitute, live-provider separation from labelled mocks, backend-only SQL access, revision checks, privacy-safe DTOs, strict provider ports, source-isolated atomic park sync, and production activity gating with `ACTIVITY_UNSUPPORTED`. Covered by `test_engine.py`, `test_picnic_web_integration.py`, `test_activity_availability.py`, and `venueGuidance.test.ts`. |
| NFR-5 and NFR-6 | Existing mobile-first React flows retained; frontend build and lint pass. |

## Implemented with a configured provider boundary

| SRS area | Status |
|---|---|
| FR-B3 and FR-D2 | Live OneMap geocoding and routing adapters are wired when credentials are configured. Demo mode uses labelled mock results and is never presented as NFR-8-compliant live scoring. |
| FR-B8 to FR-B10 and FR-E6 | Calendar connection state, free or busy response shape, tentative-hold records, cleanup, confirmed-event records, and graceful unavailable behavior are wired. Live Google Calendar calls remain disabled until the project supplies an approved OAuth credential vault and production consent configuration. |
| NFR-7, NFR-14 | Google is the only Calendar provider and the intended scopes are kept separate from sign-in. Production OAuth Calendar credentials are not stored in the application database. |
| NFR-17 | Provider implementations use documented interfaces. The NParks Parks dataset id is pinned in `nparks_geojson_adapter.py`; poll/download host validation, GeoJSON limits, schema checks, exact allowlist identity matching, and manual dry-run/apply operations are covered by `test_nparks_geojson_adapter.py`, `test_sync_parks.py`, and the release runbook. |

## Explicit SRS open items

The following values remain configuration defaults because SRS Appendix C leaves them unresolved: maximum journey time, default minimum attendees, shortlist size, public-transport provider, Candidate Timeslot step, score normalization, and tie-break order. Mall data source, hosting region, participant limit, backup operations, and production Calendar credential storage also require deployment or stakeholder decisions.

Current proposed defaults are documented in `backend/app/core/config.py` and `backend/app/recommender/config.py` and can be changed without editing the scoring pipeline.

