# Recommender and external-API adapters

Person 3's part of the backend: candidate generation, feasibility, scoring, the OneMap adapter, mock data and tests. It implements SRS v2.2 Sections 4.3 and 4.4 (FR-C1 to FR-C6, FR-D1 to FR-D10) and the "Recommender" and "Adapters" boxes of Appendix E.

The engine has no database, HTTP-route or FastAPI code in it. It takes a snapshot of one Session and returns every Combination with its outcome. Person 2's service layer loads the snapshot from the database and saves the result. This split is what lets the engine be tested on its own and keeps it independent of the database and of any one provider (C6, C7, NFR-15, NFR-16).

## Quick start

From the `backend` folder:

```bash
pip install -r requirements/recommender.txt
python -m pytest tests/recommender        # 49 tests, no network needed
python -m app.mock_data.demo              # run the mock Session end to end
```

To route with the real OneMap API instead of the mock, register for a OneMap account and then:

```bash
set ONEMAP_EMAIL=you@example.com          # PowerShell: $env:ONEMAP_EMAIL="..."
set ONEMAP_PASSWORD=...
python -m app.mock_data.demo --onemap
```

Never commit OneMap credentials. They belong in the backend's environment configuration (SRS 3.4, 5.5).

## What is where

| File | What it does | SRS |
| --- | --- | --- |
| `recommender/types.py` | Engine inputs and outputs; enum values match Appendix B.3 | B.3 |
| `recommender/config.py` | Journey cap, shortlist size, timeslot step and other settings, with TBD placeholders | B.4 |
| `recommender/candidate_generation.py` | Timeslot enumeration, attendance, Venue filter, centroid and nearest-N shortlist | FR-C1 to FR-C6 |
| `recommender/feasibility.py` | Threshold, group size, booking lead time, journey cap | FR-D1, FR-D3 to FR-D5 |
| `recommender/scoring.py` | Weight snapping, attendance and travel scores, Combined Score, ranking and tie-break | FR-D6 to FR-D10 |
| `recommender/engine.py` | `RecommendationEngine.generate()` runs UC-09/UC-10; `rescore()` handles re-weighting | UC-09, UC-10 |
| `recommender/geo.py` | Straight-line distance and centroid, used for shortlisting only | FR-C4, NFR-8 |
| `adapters/ports.py` | `Geocoder`, `Router`, `VenueSource` interfaces | C6, NFR-15 |
| `adapters/onemap.py` | OneMap token, search (geocoding) and routing | FR-B3, FR-D2 |
| `adapters/mock.py` | Offline router, geocoder and JSON Venue source | |
| `mock_data/` | 16 mock Venues, a 9-person mock Session, the loader and the demo | |
| `tests/recommender/` | Tests for every requirement above, the adapter and an NFR-1 scale check | |

## How one run works

`RecommendationEngine.generate(request)`:

1. Enumerates Candidate Timeslots and each Participant's attendance (FR-C1, FR-C2). NO_RESPONSE and WITHDRAWN are kept apart from UNAVAILABLE. A calendar BUSY block that overlaps a slot makes the person unavailable for it.
2. If no Timeslot reaches the Minimum-Attendee Threshold, it stops with `NO_TIMESLOT_MEETS_THRESHOLD` and makes no routing calls (UC-09 alternative flow).
3. Filters Venues by activity and keeps the N nearest the centroid of active, validly geocoded Participants (FR-C3, FR-C4).
4. Pairs every Timeslot with every shortlisted Venue.
5. Excludes on threshold, group size and booking lead time before any routing (FR-D1, FR-D4, FR-D5, C8).
6. Routes each needed (Participant, Venue) pair once, concurrently. A run is capped at Participants × N calls, not Participants × Combinations (SRS 5.1).
7. Marks a Combination `DATA_UNAVAILABLE` if any attendee's route failed, which is different from being excluded (NFR-3). It then applies the journey cap (FR-D3).
8. Scores and ranks the feasible Combinations (FR-D7 to FR-D10).

`engine.rescore(result, travel_objective=..., attendance_weight_percent=...)` re-ranks an existing result when the Organiser changes the objective or weighting (FR-D6, FR-D9), without any new routing calls.

## Integration notes for Person 2 (backend and database)

**Building the request.** Read the Session, its Participants, their current Availability Records and intervals, and the Venue catalogue **in one transaction**, and build a `RecommendationRequest`. Pass `now` explicitly. All datetimes must be timezone-aware.

**Withdrawal during a run (NFR-11).** Record a revision number for the Session (bumped on every response change) when you take the snapshot. Before saving the result, check that the revision is unchanged. If it changed, discard the result and mark recommendations outdated. That way no withdrawal that has completed can appear in saved scores.

**Saving the result.** `RecommendationResult` maps one-to-one onto the Appendix B.3 tables:

| Result field | Table |
| --- | --- |
| `timeslots[*]` | CandidateTimeslot (`start`, `end`, `available_count`) |
| `timeslots[*].attendance` | TimeslotAttendance |
| `shortlist[*]` | VenueShortlistEntry (`straight_line_distance_km`, `rank`); mark entries from earlier runs INVALIDATED |
| `combinations[*]` | Combination (`feasibility`, `exclusion_reason`, scores, `rank`) |
| `combinations[*].travel` | TravelEstimate (`minutes`, `status`, `journey_limit_exceeded`) |

You can skip saving `BELOW_THRESHOLD` Combinations if the table gets large. They are never shown and are cheap to recompute.

**Re-weighting.** Load the saved Combinations and TravelEstimates, call `rescore()` and save the new scores and ranks. Don't call `generate()` again for a weight or objective change.

**Wiring in ApplicationStartup.** Create one `OneMapAdapter(email=..., password=...)` at start-up, share it, and close it on shutdown with `await adapter.aclose()`. The same object is both the `Geocoder` used by availability submission (UC-08) and the `Router` given to `RecommendationEngine`. For local development without credentials, use `MockRouter()` and `MockGeocoder(load_places())`, for example behind a `USE_MOCK_PROVIDERS=1` setting.

**Geocoding (UC-08).** `await geocoder.geocode(text)` returns `VALID` with a list of matches for the Participant to choose from, `INVALID` when nothing matched (FR-B3.1: show the inline error), or `UNAVAILABLE` when OneMap is down (NFR-3: show "unavailable" and let them retry).

**Venue catalogue.** `VenueSource` is the interface for the data.gov.sg loader. `JsonVenueSource` reads `mock_data/venues.json` until that loader exists.

## Notes for Person 1 (frontend)

For each entry on the Best Matches screen, the API can return the following fields from a ranked `Combination`:
- `venue.name`, `venue.address` and `venue.location` for the map pin
- `timeslot.start` and `timeslot.end`
- `combined_score`, `attendee_count`, `total_travel_minutes`, `max_travel_minutes`
- each `travel` entry's participant, `transport_mode` and `minutes`

The attendance list comes from `timeslot.attendance` (FR-E1 to FR-E3). Starting locations are never part of a Combination (NFR-13).

Don't return `result.centroid` to the client. With one or two Participants it is effectively someone's starting location.

## Placeholders and open decisions

These values are needed to run, but the SRS leaves them open. They live in `RecommenderConfig` and are easy to change once decided.

| Setting | Placeholder | SRS |
| --- | --- | --- |
| Maximum individual journey time | 60 min | TBD-1 |
| Shortlist size N | 10 | TBD-2 |
| Default Minimum-Attendee Threshold | 2 | TBD-2 |
| Timeslot step | 30 min | TBD-13 |

These design choices still need group sign-off:

- **Score formulas (TBD-15).**
  - Attendance score = attendees ÷ Participants with an active response.
  - Travel score = 1 − (travel value ÷ journey cap).
  - Under MIN_TOTAL the travel value is the *mean* journey per attendee, so options with more attendees aren't penalised twice.
  - Scores are absolute, not min-max normalised, so an option's score doesn't change just because other options were added or removed.
- **Tie-break (TBD-9).** In order: more attendees, then shorter longest journey, then earlier start, then nearer Venue, then VenueID.
- **FR-D3 as written.** One attendee over the journey cap removes the whole Combination. In the mock Session, Gopal (travelling from NTU) knocks out every Sunday option. An alternative is to treat him as not attending that option instead; this needs an SRS change.
- **Public-transport departure time.** Routing is once per (Participant, Venue) pair, so the earliest Timeslot that pair is needed for is used as the departure time.
- **Optimal group size (TBD-4)** is carried on each Venue but not used in scoring yet.

## Not done here

- **LTA DataMall adapter.** It is only needed if OneMap's public-transport routing proves insufficient (TBD-3). It would be another `Router` implementation; the engine would not change.
- **data.gov.sg Venue loader.** The `VenueSource` interface is ready for it.
- **Live check of OneMap response fields.** The parsers follow OneMap's documented fields (`route_summary.total_time`; `plan.itineraries[].duration`) and are isolated in `_parse_route_minutes`. Run `demo --onemap` once with real credentials to confirm them.
