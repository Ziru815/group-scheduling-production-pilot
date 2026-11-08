# Picnic Park Catalogue and Production Reliability Design

## Intent

The production application currently exposes Picnic, Board Games, and Bowling as selectable activities, but only Badminton, Basketball, and Football have verified public venues. A user can therefore create a non-sport Session and collect responses, then reach recommendation generation with no production-grade venue candidates. That is misleading in a product intended to behave like a normal public website.

This change will complete the Picnic path as a real Timeslot × Park recommendation flow and will stop advertising incomplete Leisure paths. Picnic will use an official NParks dataset identity, a curated route-ready meeting point, existing OneMap travel routing, and the existing deterministic scoring engine. Recommendation requests will continue to use only persisted catalogue rows; data.gov.sg will never be called in the interactive request path.

## Goals

- Make Picnic a complete production activity from Session creation through confirmation and Calendar export.
- Publish twenty verified, geographically distributed, picnic-suitable public parks.
- Keep the existing time, attendance, centroid shortlist, OneMap routing, journey cap, scoring, ranking, confirmation, privacy, and Calendar behavior unchanged.
- Tag Picnic venues as `PARK` and associate them only with the Picnic activity.
- Preserve the last successful park catalogue when data.gov.sg, the download URL, OneMap enrichment, or the database is unavailable.
- Remove Board Games and Bowling from the production creation catalogue until each has verified venue support.
- Make venue provenance and the absence of live reservation guarantees clear to users.
- Add automated evidence for SRS FR-C3 to FR-C5, FR-D1 to FR-D10, NFR-3, NFR-8, NFR-15, NFR-16, and NFR-17 as they apply to Picnic.

## Non-goals

- Board Games, Bowling, malls, restaurants, karaoke, or other Leisure venue catalogues.
- Live park capacity, crowding, opening-hours, weather, shelter, event-permit, barbecue-pit, or reservation availability.
- Automatic inclusion of every NParks polygon.
- Booking, payment, or permit assistance.
- A new map UI or changes to the recommendation formula.
- Calling data.gov.sg or NParks while a user opens or generates recommendations.
- Replacing OneMap as the routing provider.

## Constraints

- The official NParks Parks and Nature Reserves dataset is GeoJSON containing names, stable-looking source codes, and Polygon or MultiPolygon boundaries. Its geometry does not identify a safe public entrance or meeting point.
- Nature reserves, small playgrounds, incidental managed green areas, and closed or unsuitable sites must not be treated as picnic venues merely because they occur in the source.
- Production venue rows must remain activity-scoped and verified before the repository exposes them.
- A Park must not inherit Sports Facility minimum-group-size or advance-booking rules.
- Existing sports catalogue sync and the sixty verified sport-activity relationships must not be changed by a park-source failure.
- Exact participant starting locations remain private. Only the existing backend routing layer may use them.
- The current Render deployment runs migrations, seeds reference activities, optionally synchronises venues, and then starts the application. The park sync must fit that deployment model without increasing interactive latency.
- Public data API access works without a key at lower limits. An optional `DATA_GOV_SG_API_KEY`, sent only as `x-api-key`, may be configured later; no client-side key is permitted.

## Approaches Considered

### Static curated park list

Store twenty park names and meeting points without fetching the official dataset. This has the smallest runtime surface and is easy to test, but it weakens source freshness and makes the data.gov.sg provenance less defensible.

### Official dataset plus curated verified meeting points

Fetch the official NParks dataset during an explicit catalogue sync, match a curated allowlist by source identity, and persist only twenty reviewed parks with safe route-ready meeting points. This keeps official identity and update evidence while avoiding unsafe polygon-centroid navigation. It adds one source adapter and one atomic sync path but keeps user requests independent of the upstream API.

This is the selected approach because it best fits the SRS provider boundary and the user's reliability-first goal.

### Fully automatic import of every NParks geometry

Automatically turn every polygon into a Picnic venue. This creates a larger catalogue, but it would include unsuitable areas and would require guessing route points. The apparent completeness would reduce product reliability, so this approach is rejected.

## Source and Verification Model

The upstream source is the data.gov.sg dataset `d_77d7ec97be83d44f61b85454f844382f`, NParks Parks and Nature Reserves. A new adapter will:

1. Call the official dataset poll-download endpoint with bounded timeout and retry behavior.
2. Send `x-api-key` only when the optional server-side key is configured.
3. validate the poll response and download URL before following it;
4. cap the accepted download size and reject non-JSON content;
5. require a GeoJSON FeatureCollection and the expected identity fields;
6. parse Polygon and MultiPolygon features without treating their centroids as route destinations;
7. reject blank names, missing source codes, duplicate identities, invalid geometry, and coordinates outside Singapore; and
8. return a complete typed snapshot or fail without performing database writes.

A new `verified_public_picnic_parks.json` file will contain twenty reviewed entries. Each entry will include:

- the official NParks source code and source name;
- the canonical display name;
- a human-readable meeting-point label and address;
- a route-ready latitude and longitude for a public entrance or unmistakable meeting point;
- an official NParks evidence URL;
- the verification date; and
- a coarse coverage region used only by verification tests.

The allowlist is an assertion that the park is a real public NParks-managed location and that its chosen meeting point is appropriate for routing. It is not an assertion of present opening, capacity, reservation, or picnic-space availability.

The twenty entries must provide credible islandwide coverage. Automated verification will require representation in west, north, north-east, central/south, and east regions, and will reject duplicate route points. The exact park selection and meeting points are builder calls, provided each entry satisfies the published evidence and coverage rules.

## Catalogue Persistence and Atomicity

Park rows will use a separate data-source identifier, `DATA_GOV_SG_NPARKS_PARKS`, so park and sports synchronisation cannot deactivate each other's records.

The park synchroniser will:

1. load and validate the complete official snapshot;
2. load and validate the complete curated allowlist;
3. require every curated source identity to be present in the official snapshot;
4. construct exactly twenty verified `PARK` venues linked as `SUPPORTED` to Picnic;
5. perform all inserts, updates, links, and park-source deactivations in one transaction; and
6. commit only after the full batch succeeds.

If polling, download, schema validation, identity matching, or database persistence fails, no park rows or links change. The previous successful park catalogue remains active. Existing sports rows are never touched by the park transaction.

The sync command will support `--dry-run` and `--apply`, print aggregate counts only, and never print credentials or user data. Venue changes will invalidate active recommendation revisions so organisers regenerate against the new catalogue.

Production park synchronisation is an explicit one-time maintenance operation,
not part of the web service start command and not a deploy-blocking hook. After
the new image is live, an operator uses the paid Render service's Dashboard
Shell to run `--dry-run`, reviews the counts, and then runs `--apply`. A failed
sync therefore cannot take the existing website offline. The same command can
be repeated later because the apply operation is idempotent.

## Activity Availability

Production activity creation must expose only activities backed by at least one active verified venue relationship. This is enforced on the server response used by the New Session page, rather than by a frontend-only list.

- Picnic becomes selectable after the park catalogue is successfully applied.
- Board Games and Bowling remain in reference data for existing records but are omitted from the production creation catalogue while they have no verified venues.
- Existing Sessions retain their stored activity names and remain readable.
- Existing active Board Games or Bowling Sessions become read-only except that
  the organiser may cancel them. Existing responses and confirmed plans remain
  readable, but joining, response submission or editing, recommendation
  generation, and confirmation are rejected with an explicit unsupported-
  activity response. This avoids asking participants to complete a flow that
  cannot produce a verified venue recommendation.
- Attempts to create a new Session with an inactive or unsupported activity are rejected server-side with an explicit validation response.
- Development mock mode may continue to expose its labelled mock activities and venues.

This makes incomplete Leisure work dormant without deleting schema rows or pretending that time-only scheduling satisfies the venue requirements.

## Recommendation and User Experience

Picnic uses the existing recommendation pipeline unchanged:

1. enumerate Candidate Timeslots;
2. calculate availability and attendance;
3. calculate the participant geographic centroid privately on the backend;
4. filter to verified Picnic parks;
5. shortlist the nearest configured number of parks;
6. route each attendee to each shortlisted park through OneMap;
7. apply the journey cap and requested attendance threshold;
8. calculate attendance and travel scores with the Session weights;
9. rank deterministically; and
10. allow organiser confirmation and Calendar event creation.

Park combinations do not apply Sports Facility minimum-group-size, optimal-group-size, or advance-booking exclusions. The Session's own Minimum Attendee Threshold still applies.

Result and confirmation views will show:

- the park name;
- the chosen meeting-point label and address;
- an existing map link using the route-ready point;
- venue category `Park`;
- `NParks via data.gov.sg` as the data source;
- source last-updated or last-synchronised information; and
- a concise disclaimer that the application does not confirm current access, reservation, or availability.

No exact participant location is added to any public or shared response.

## Failure Behavior

- If data.gov.sg is unavailable during a sync, the command fails and leaves the last-good database state untouched.
- If one of the twenty curated parks disappears from the official snapshot, the sync fails rather than silently shrinking the public catalogue.
- If OneMap routing is unavailable during recommendation generation, the existing routing-unavailable state is shown; no straight-line or zero-minute substitute is created.
- If no feasible Picnic combination remains after travel or attendance constraints, the existing explicit empty or near-match behavior is used.
- If a client submits an unsupported Leisure activity ID, the backend returns a field-level validation error rather than creating a dead-end Session.
- Data-source failures are logged without access tokens, API keys, participant addresses, or coordinates.

## Performance

The data.gov.sg GeoJSON download occurs only in the explicit catalogue-sync command. Interactive recommendations query indexed SQL rows and shortlist at most the configured venue limit before routing, so adding twenty parks does not change the asymptotic recommendation workload or add an upstream catalogue dependency to page loads.

The adapter will use a bounded timeout, a small retry budget for 429 and 5xx responses, and a download-size ceiling. The sync will be run during controlled deployment or maintenance, not on every application startup unless explicitly enabled.

## Testing and Verification

Automated tests will cover:

- poll-download success, optional API-key header, timeout, 429, 5xx, malformed JSON, unsafe download URL, oversized response, and schema drift;
- Polygon and MultiPolygon parsing, duplicate identities, invalid coordinates, and incomplete snapshots;
- allowlist integrity, exactly twenty entries, evidence URLs, unique meeting points, Singapore coordinate bounds, and five-region coverage;
- atomic insert, idempotent reapply, update, park-only deactivation, and rollback preserving last-good rows;
- sports catalogue isolation when park sync fails;
- Picnic `PARK` activity linkage and the absence of Sports Facility group-size and booking-window exclusions;
- server-side omission and rejection of unsupported Leisure activities in production;
- preservation of mock-mode activity behavior;
- end-to-end Picnic recommendation from three geographically separated participant origins;
- OneMap unavailable behavior, deterministic ranking, confirmation, and Calendar event projection; and
- frontend rendering, provenance, disclaimer, map link, mobile width, loading, empty, and failure states.

Before deployment, the complete backend suite, frontend lint, and frontend production build must pass. A production smoke test will create a Picnic Session, submit at least two distinct Singapore starting locations, generate multiple park recommendations, confirm one, and verify the shared confirmation page without exposing participant addresses.

## Rollout and Recovery

1. Deploy code and schema-compatible changes with Picnic still absent if no verified park rows exist.
2. From the Render Dashboard Shell, run the park sync in dry-run mode and record source, accepted, curated, and rejected counts.
3. From the same deployed image and environment, run the atomic apply against production.
4. Confirm the activity catalogue now shows Outdoors → Picnic and does not show Leisure.
5. Complete the production Picnic smoke test.
6. Record source evidence and verification results in the venue register and SRS traceability document.

Rollback is code rollback plus preservation of existing database rows. If a park catalogue must be withdrawn, its source rows can be marked inactive in one controlled transaction; existing confirmed plans remain readable. The sports catalogue and existing Sessions are unaffected.

## Builder Calls

The builder may choose the exact twenty parks, meeting points, module boundaries, and test-fixture shapes, provided they satisfy the official-source, coverage, atomicity, privacy, and routing requirements above. The builder may also choose a conservative HTTPS download-host allowlist after observing the official poll response in development. No new third-party library should be added unless the standard library and existing dependencies cannot safely parse and validate the required GeoJSON structure.
