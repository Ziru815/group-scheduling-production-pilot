# Islandwide Badminton Venue Expansion Design

**Date:** 2026-10-30

**Status:** Proposed for approval

## 1. Goal

Expand the production badminton catalogue from eight verified public venues to
twenty verified venues distributed across Singapore. The recommendation engine
will continue to shortlist the ten venues nearest the active participants'
geographic centroid, so different groups receive different local candidates
without increasing the routing fan-out beyond the existing default.

## 2. Scope

This phase changes only the badminton venue catalogue and its verification
documentation. It does not change the shortlist algorithm, the default shortlist
size of ten, scoring, OneMap routing, activity selection, or the Football,
Basketball, Bowling, Picnic, and Board Games catalogues.

Participant starting locations remain unrestricted Singapore addresses or
six-digit postal codes resolved by OneMap. They are not selected from a fixed
list.

## 3. Approaches considered

Three approaches were considered:

1. **Add only conventional ActiveSG sport halls.** This has the simplest
   verification story, but the official source contains too few such halls to
   close the far-west and north-east coverage gaps.
2. **Curate sport halls plus officially bookable ActiveSG school halls.** This
   keeps the trust boundary narrow while adding public badminton facilities in
   underserved parts of the island. This is the recommended approach and the
   one specified below.
3. **Admit every raw badminton record from data.gov.sg.** This would create the
   largest catalogue, but it would also expose schools without public booking,
   condominiums, private organisations, duplicates, and stale records. It is
   rejected because it weakens the production verification boundary.

## 4. Source and verification policy

Every added venue must satisfy both of these conditions:

1. The Sport Singapore Sport Facilities dataset on data.gov.sg contains a
   matching venue name, six-digit postal code, Singapore coordinates, and a
   `Badminton Court` facility row.
2. An official ActiveSG facility page lists badminton for the same venue. For a
   school hall, the page must be part of ActiveSG's public badminton facility
   catalogue and expose an ActiveSG badminton booking entry. The application
   must not infer public access from the school name alone.

The catalogue remains an evidence-backed location catalogue, not a live court
availability feed. The UI must continue to avoid claims that a court is
currently available or that a booking will succeed.

Runtime scraping is out of scope. Verification is a release-time curation step;
production continues to ingest venue identities from data.gov.sg and enrich
addresses through OneMap.

## 5. Proposed catalogue

The existing eight venues remain. The following twelve venues are added to
close the largest geographic gaps:

| Coverage area | Dataset source name | Display name | Postal code | Official evidence |
| --- | --- | --- | --- | --- |
| West | Bukit Gombak Sport Hall | Bukit Gombak Sport Hall | 659088 | https://www.activesgcircle.gov.sg/facilities/bukit-gombak-sport-hall |
| North-west | Senja-Cashew Sport Hall | Senja-Cashew Sport Hall | 679910 | https://www.activesgcircle.gov.sg/facilities/senja-cashew-sport-hall |
| North | Woodlands Sport Hall | Woodlands Sport Hall | 738620 | https://www.activesgcircle.gov.sg/facilities/woodlands-sport-hall |
| Central-north | Yio Chu Kang Sport Hall | Yio Chu Kang Sport Hall | 569780 | https://www.activesgcircle.gov.sg/facilities/yio-chu-kang-sport-hall |
| North | Admiralty Primary School | Admiralty Primary School Hall | 738907 | https://www.activesgcircle.gov.sg/facilities/admiralty-primary-school-hall |
| North-east | Greendale Primary School | Greendale Primary School Hall | 828848 | https://www.activesgcircle.gov.sg/facilities/greendale-primary-school-hall |
| North-east | North Vista Secondary School | North Vista Secondary School Hall | 545081 | https://www.activesgcircle.gov.sg/facilities/north-vista-secondary-school-hall |
| East | Junyuan Secondary School | Junyuan Secondary School Hall | 528933 | https://www.activesgcircle.gov.sg/facilities/junyuan-secondary-school-hall |
| South-east | Dunman High School | Dunman High School Hall | 436895 | https://www.activesgcircle.gov.sg/facilities/dunman-high-school-hall |
| Far west | Boon Lay Secondary School | Boon Lay Secondary School Hall | 648354 | https://www.activesgcircle.gov.sg/facilities/boon-lay-secondary-school-hall |
| Far west | Frontier Primary School | Frontier Primary School Hall | 648200 | https://www.activesgcircle.gov.sg/facilities/frontier-primary-school-hall |
| South-central | Queenstown Primary School | Queenstown Primary School Hall | 149303 | https://www.activesgcircle.gov.sg/facilities/queenstown-primary-school-hall |

Together with the current catalogue, this provides multiple candidates in the
west, north, north-east, east, central, and south-central parts of Singapore.

## 6. Data and application flow

The existing `verified_public_sports_venues.json` remains the production trust
boundary. Each new row records the deterministic data.gov.sg source key,
dataset source name, postal code, ActiveSG display name, official evidence URL,
verification date, and `verified_activities: ["Badminton"]`. This activity-level
scope prevents a multi-sport school record from exposing basketball or football
before those catalogues are separately reviewed.

On the next venue sync:

1. the data.gov.sg adapter loads and normalizes the complete source dataset;
2. the allowlist marks the twenty approved records `VERIFIED_PUBLIC` and limits
   the twelve new records to verified badminton links;
3. OneMap enriches only those twenty records with display addresses;
4. production recommendations filter to active, verified venues supporting
   badminton; and
5. the existing centroid shortlist selects the nearest ten before routing.

No database migration or frontend change is required.

## 7. Failure handling

- A missing or renamed data.gov.sg source row must reduce the verified count in
  the dry run and block release until the mapping is reviewed.
- A broken ActiveSG evidence URL must block release of that entry.
- OneMap address enrichment failure may use the existing honest fallback label
  `<venue>, Singapore <postal>`; it must not deactivate an otherwise verified
  venue.
- No school hall is admitted solely because it appears in the raw government
  dataset. An official ActiveSG badminton facility page is mandatory.

## 8. Verification and rollout

The change is data and documentation only, so adding an artificial unit test
that asserts an exact venue count would test the configuration text rather than
user-visible behaviour. Existing catalogue and recommendation tests remain the
regression gate. Release evidence consists of:

1. all backend tests passing;
2. frontend lint and production build passing;
3. `python -m scripts.sync_venues --dry-run` reporting twenty verified venues;
4. an idempotent production `--apply` sync;
5. live recommendations from a west-side and east-side test group returning
   different nearby venues; and
6. the branch being pushed to GitHub before Render deployment verification.
