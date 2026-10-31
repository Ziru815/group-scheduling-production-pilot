# OneMap renewal and official venue links design

## Intent

Make the public pilot reliable beyond the lifetime of one manually issued
OneMap token, and make each recommendation actionable by linking users to the
already-reviewed official page for that exact sports venue or park.

The change is for the existing public Render deployment and its real Google
users. It must preserve the current privacy boundary, ranking behavior,
venue-availability disclaimers, and organiser-only confirmation rule.

## Current state and problem

- Render currently has `ONEMAP_TOKEN`, `ONEMAP_EMAIL`, and
  `ONEMAP_PASSWORD` configured.
- `OneMapAdapter._get_token()` returns the fixed token whenever one exists,
  so the refreshable email/password path is never used. OneMap tokens last
  about three days; an expired fixed token can therefore disable geocoding and
  routing even though refresh credentials are present.
- The reviewed sports and Picnic allowlists already store one exact official
  HTTPS `verification_url` per supported venue/activity. Catalogue sync saves
  that value in `VenueActivity.source_reference`.
- The public `VenueSummary` contract does not expose that reviewed URL, so the
  result and confirmation pages can only offer Google Maps and provenance
  text.

## Goals

1. Prefer refreshable OneMap credentials whenever a complete email/password
   pair is configured.
2. Keep a fixed OneMap token as the supported mode only when refreshable
   credentials are incomplete or absent.
3. Recover once from an unexpectedly rejected cached refresh token without
   requiring an application restart.
4. Expose only a reviewed, activity-specific official venue URL through the
   backend contract.
5. Show the official link in both expanded ranked results and the confirmed
   plan.
6. Preserve the existing statement that the application does not book a venue
   and does not know live availability.

## Non-goals

- Live court, field, hall, or park availability.
- Booking or reservation inside Group Scheduler.
- Scraping ActiveSG or NParks pages.
- Adding generic search links when a reviewed exact URL is unavailable.
- Changing recommendation scores, shortlist logic, venue counts, or stored
  Combination identities.
- Updating assessment documents or adding final-plan sharing in this change.

## Constraints

- OneMap credentials and tokens remain backend-only.
- No new external provider, frontend dependency, or database migration.
- The public API may return only HTTPS links on the reviewed ActiveSG or NParks
  host families.
- The link is optional so historical/demo data continues to render safely.
- Recommendation grouping must not merge venue projections that differ in
  official link metadata.

## Approaches considered

### 1. Refreshable credentials first and reuse reviewed exact URLs — chosen

Change the adapter's credential selection in code, project the existing
activity evidence URL, and show it on both user-facing venue screens.

This fixes the root cause, survives future environment edits, produces exact
venue links, and adds no external dependency. It touches the backend adapter,
web contract, frontend contract, grouping semantics, and two screens, so it
requires coordinated tests.

### 2. Render-only token removal and generic category homepages

Deleting `ONEMAP_TOKEN` would activate the current refresh path, and the UI
could link every sport to an ActiveSG homepage and every park to an NParks
homepage. This is faster but fragile: adding a fixed token later reintroduces
the outage, and users still have to search for the venue.

### 3. Live availability or booking integration

This would be more ambitious, but there is no approved stable provider
contract in the project. It would add significant correctness and maintenance
risk and could mislead users about availability, contrary to the SRS boundary.

## OneMap token behavior

`OneMapAdapter` will treat a complete `email + password` pair as the primary
authentication mode even if a fixed token is also supplied.

- With complete refresh credentials, `_get_token()` returns a still-valid
  cached dynamic token or obtains and caches a new token from OneMap.
- With no complete refresh credential pair, `_get_token()` uses the configured
  fixed token as today.
- A partial credential pair does not disable a usable fixed token.
- When OneMap rejects a dynamically acquired token with 401/403, the adapter
  clears that cached token, obtains one fresh token, and retries the idempotent
  GET once. A second rejection becomes the existing labelled provider-
  unavailable outcome; it never loops.
- A fixed-token-only 401/403 remains provider-unavailable. The application
  does not attempt to invent credentials or route results.
- The existing async token lock continues to prevent a burst of concurrent
  refresh requests.

The production environment does not need a secret deletion: once the new
code is deployed, the existing complete email/password pair wins and the
existing fixed token is ignored.

## Official URL contract

The backend will derive an optional `officialUrl` for the session activity
from the matching supported `VenueActivity.source_reference` row.

Projection rules:

1. The row must match the venue and the session's activity type.
2. Its support status must be `SUPPORTED`.
3. The reference must be an HTTPS URL.
4. Sports links must use `activesgcircle.gov.sg` or a subdomain; park links
   must use `nparks.gov.sg` or a subdomain.
5. Anything else projects as `null`, never as a clickable value.

`VenueSummary` gains:

```text
officialUrl: string | null
```

Recommendation and confirmed-plan projections use the same helper and the
same activity context. This deliberately reuses `VenueActivity` instead of
adding a venue column: official evidence is activity-specific and already
updated atomically by both catalogue sync paths.

## Frontend behavior

- Expanded result cards keep the existing “Open in Google Maps” link and add
  an external official-information link when `officialUrl` is non-null.
- The confirmed plan shows the same link in its Where section.
- Sports copy is “View official venue information”; park copy is “View
  official park information”.
- Both links open a new tab with `noopener noreferrer`.
- No official link is rendered for historical/demo/unreviewed data.
- Existing guidance remains visible: the application does not claim booking,
  reservation, opening status, or live availability.
- `officialUrl` participates in the semantic venue key used by grouped result
  cards so groups never hide inconsistent public metadata.

## Failure handling and security

- OneMap auth, network, rate-limit, and provider failures continue to return
  explicit unavailable results; there is no straight-line or zero-minute
  fallback.
- A malformed or non-approved source reference is omitted from the API.
- The browser receives no OneMap secret or authentication detail.
- Official pages are informational outbound links only and cannot mutate the
  Group Scheduler session.

## Verification

Backend tests will prove:

- complete refresh credentials take precedence over a simultaneous fixed
  token;
- fixed-token-only configuration still works;
- a rejected dynamic token is refreshed and retried at most once;
- concurrent refresh remains locked;
- reviewed sport and park URLs project for the matching activity;
- unsupported, non-HTTPS, and non-approved-host references project as null;
- recommendation and confirmed-plan payloads carry the same official URL.

Frontend tests and checks will prove:

- `officialUrl` is part of the typed contract and grouping semantics;
- the category-specific link wording is deterministic;
- existing grouping, selection, and venue-guidance tests remain green;
- lint and the production build pass.

Production acceptance will verify:

1. A real address search still returns OneMap candidates after the deployment.
2. A Picnic result opens the exact reviewed NParks page.
3. A sports result opens the exact reviewed ActiveSG page.
4. The confirmed-plan page exposes the same official link without implying a
   booking.
5. `/health` and `/ready` remain healthy and the existing result grouping and
   organiser-only confirmation behavior remain intact.

## Rollback

The change has no schema migration. Rolling back the application commit
restores the old token precedence and hides the optional links without
altering stored venues, activities, recommendations, or confirmed plans.

## Builder decisions

The builder may choose helper names, query placement, CSS class names, and the
exact unit-test fixtures as long as the contract, allowlist rules, visible
copy, and acceptance behavior above remain unchanged.
