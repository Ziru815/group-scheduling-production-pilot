# Islandwide Basketball and Football Venue Expansion Design

**Date:** 2026-10-30

**Status:** Approved by the user's instruction to expand both sports using the
existing verified-venue approach

## 1. Intent

Expand the production Basketball and Football catalogues from one
activity-verified venue each to twenty activity-verified venues each. The
result should look and behave like a real islandwide service for the course
demonstration while preserving the current public URL, recommendation flow,
OneMap routing, and GitHub deployment history.

## 2. Goals and non-goals

Goals:

- provide twenty verified Basketball venues and twenty verified Football
  venues distributed across Singapore;
- require a matching current data.gov.sg Sport Facilities record and an
  official ActiveSG facility listing for every new venue;
- scope every new record to only the activity covered by its evidence;
- retain the existing nearest-ten shortlist so routing cost does not grow with
  the catalogue; and
- deploy through the existing GitHub `feature/production-pilot` branch so the
  current Render URL remains unchanged.

Non-goals:

- importing every raw government record;
- claiming live availability, guaranteed booking, current price, or opening
  hours;
- changing scoring, shortlist size, OneMap behavior, frontend screens, Google
  login, Calendar integration, or the `main` branch; and
- expanding Badminton, Bowling, Picnic, or Board Games in this phase.

An anti-goal is a larger but less trustworthy catalogue containing private,
closed, renamed, or non-public facilities.

## 3. Approaches considered

1. **Import every raw Basketball and Football record.** This is the fastest
   way to show large numbers, but the source contains private facilities,
   unnamed records, duplicates, and schools without demonstrated public
   access. It is rejected.
2. **Import every ActiveSG/data.gov.sg intersection.** Current evidence yields
   28 Basketball and 113 Football intersections. This is defensible, but it
   creates unnecessary maintenance and makes a first release harder to audit.
3. **Curate twenty islandwide venues per activity.** Keep the current verified
   venue for each activity and add nineteen geographically distributed,
   officially listed candidates. This is the selected approach: it is large
   enough for realistic local recommendations and small enough to revalidate
   before the demonstration.

## 4. Verification policy

Every added venue must satisfy all of the following:

1. A normalized data.gov.sg Sport Facilities record has the exact six-digit
   postal code, Singapore coordinates, and the requested activity
   (`Basketball Court`, `Football Field`, or `Soccer Field`).
2. ActiveSG lists the same facility and postal code in its Basketball or
   Football facility catalogue and provides an official facility page.
3. The facility page does not announce a current long-term closure.
4. The allowlist record uses a deterministic source key and declares exactly
   one of `verified_activities: ["Basketball"]` or
   `verified_activities: ["Football"]`.

The selected new Basketball and Football identities are deliberately
disjoint, and neither set reuses the existing Badminton-only identities. This
keeps the current one-URL evidence schema unambiguous: each new allowlist row's
official URL proves the one activity it exposes.

## 5. Basketball catalogue

The existing verified Basketball venue, Clementi Sport Centre, remains. Add
the following nineteen official matches:

| Area | data.gov.sg source identity | Postal | App display name | ActiveSG evidence |
| --- | --- | --- | --- | --- |
| North | Ahmad Ibrahim Primary School | 768643 | Ahmad Ibrahim Primary School Hall | `ahmad-ibrahim-primary-school-hall` |
| North | Bukit Canberra Sport Centre | 756973 | Bukit Canberra Sport Hall | `bukit-canberra-sport-hall` |
| North | Northbrooks Secondary School | 768692 | Northbrooks Secondary School Hall | `northbrooks-secondary-school-hall` |
| North | Woodgrove Secondary School | 738990 | Woodgrove Secondary School Hall | `woodgrove-secondary-school-hall` |
| North-east | Bishan Clubhouse | 579780 | Bishan Clubhouse | `bishan-clubhouse` |
| Central | Bukit Merah Secondary School | 159050 | Bukit Merah Secondary School Hall | `bukit-merah-secondary-school-hall` |
| Central | Fairfield Methodist School (Primary) | 139648 | Fairfield Methodist Primary School Hall | `fairfield-methodist-primary-school-hall` |
| Central | MOE HQ (Evans Road) | 259366 | MOE (Evans) Sport Hall | `moe-evans-sport-hall` |
| Central | Nan Hua High School | 129956 | Nan Hua High School Hall | `nan-hua-high-school-hall` |
| Central | Queenstown Secondary School | 148800 | Queenstown Secondary School Hall | `queenstown-secondary-school-hall` |
| East | Bedok Green Secondary School | 469722 | Bedok Green Secondary School Hall | `bedok-green-secondary-school-hall` |
| East | Our Tampines Hub | 528523 | Our Tampines Hub - Team Sports Hall | `tampines-sport-hall` |
| East | Tanjong Katong Primary School | 437259 | Tanjong Katong Primary School Hall | `tanjong-katong-primary-school-hall` |
| East | Telok Kurau Primary School | 479239 | Telok Kurau Primary School Hall | `telok-kurau-primary-school-hall` |
| East | Victoria School | 448880 | Victoria School Hall | `victoria-school-hall` |
| West | Choa Chu Kang Stadium | 689236 | Choa Chu Kang Sport Hall | `choa-chu-kang-sport-hall` |
| West | Jurong West Stadium | 648965 | Jurong West Sport Hall | `jurong-west-sport-hall` |
| West | Juying Secondary School | 649038 | Juying Secondary School Hall | `juying-secondary-school-hall` |
| West | West Spring Primary School | 679946 | West Spring Primary School Hall | `west-spring-primary-school-hall` |

## 6. Football catalogue

The existing verified Football venue, Hougang Sport Hall, remains. Add the
following nineteen official matches:

| Area | data.gov.sg source identity | Postal | App display name | ActiveSG evidence |
| --- | --- | --- | --- | --- |
| West | Sport Village @ Jurong Town | 619618 | ActiveSG Sport Village @ Jurong Town | `activesg-sport-village-jurong-town` |
| West | Bukit Gombak Stadium | 659081 | Bukit Gombak Stadium | `bukit-gombak-stadium` |
| West | Westwood Secondary School | 648350 | Westwood Secondary School Field | `westwood-secondary-school-field` |
| West | Jurong East Stadium | 609517 | Jurong East Stadium | `jurong-east-stadium` |
| North | Anderson Secondary School | 569206 | Anderson Secondary School Field | `anderson-secondary-school-field` |
| North | Canberra Primary School | 757714 | Canberra Primary School Field | `canberra-primary-school-field` |
| North | Woodlands Stadium | 738597 | Woodlands Stadium | `woodlands-stadium` |
| North | Yishun Stadium | 769131 | Yishun Stadium | `yishun-stadium` |
| North-east | Bishan Stadium | 579784 | Bishan Stadium | `bishan-stadium` |
| North-east | Bowen Secondary School | 547529 | Bowen Secondary School Field | `bowen-secondary-school-field` |
| North-east | Horizon Primary School | 828819 | Horizon Primary School Field | `horizon-primary-school-field` |
| North-east | Punggol Cove Primary School | 828674 | Punggol Cove Primary School Field | `punggol-cove-primary-school-field` |
| East | Bedok South Secondary School | 468585 | Bedok South Secondary School Field | `bedok-south-secondary-school-field` |
| East | Junyuan Primary School | 528906 | Junyuan Primary School Field | `junyuan-primary-school-field` |
| East | East Spring Secondary School | 529231 | East Spring Secondary School Field | `east-spring-secondary-school-field` |
| East | Meridian Secondary School | 518901 | Meridian Secondary School Field | `meridian-secondary-school-field` |
| Central | Bartley Secondary School | 538403 | Bartley Secondary School Field | `bartley-secondary-school-field` |
| Central | Bendemeer Primary School | 339948 | Bendemeer Primary School Field | `bendemeer-primary-school-field` |
| Central | Blangah Rise Primary School | 109100 | Blangah Rise Primary School Field | `blangah-rise-primary-school-field` |

## 7. Data flow and rollout

No application code or database migration is required. The existing
`verified_public_sports_venues.json` remains the trust boundary. After the
thirty-eight records are added, a normal venue sync will ingest 58 verified
venues in total while exposing exactly twenty Basketball and twenty Football
links. The nearest-ten shortlist continues to limit downstream OneMap routing.

Release verification requires official-page revalidation, the existing
allowlist and catalogue tests, a live dry run showing 58 verified identities,
an idempotent production apply, and geographic smoke tests for both sports.
