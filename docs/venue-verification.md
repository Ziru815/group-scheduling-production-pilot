# Public venue verification register

This register explains the evidence behind the production venue allowlist.
The data.gov.sg Sport Facilities dataset supplies the source identity, postal
code, coordinates, and facility labels. An official ActiveSG page must also
identify the location as a public badminton facility before the app can mark it
`VERIFIED_PUBLIC`. A school hall qualifies only when its official ActiveSG page
contains a public badminton booking entry.

Verification evidence is activity-scoped. The twelve venues added on
2026-10-30 declare `verified_activities: ["Badminton"]`, so any basketball or
football rows sharing the same dataset venue remain unavailable until those
activities receive their own review. Older entries without this field preserve
their existing multi-sport behaviour.

Verification means that the venue is a real public facility and that the
dataset identity matched on the date shown. It does **not** mean that a court is
available now, that a booking will succeed, or that prices and opening hours
have been checked. Users must confirm temporary closures and booking details on
ActiveSG.

| Dataset source identity | App display name | Postal code | Official evidence | Verified on |
| --- | --- | --- | --- | --- |
| Bishan Sport Centre | Bishan Sport Hall | 579783 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/bishan-sport-hall) | 2026-10-28 |
| Clementi Sport Centre | Clementi Sport Centre | 129907 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/clementi-sport-centre) | 2026-10-28 |
| Delta Sport Centre | Delta Sport Hall | 158790 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/delta-sport-hall) | 2026-10-28 |
| Heartbeat@Bedok | Heartbeat @ Bedok ActiveSG Sport Hall | 469662 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/heartbeat-bedok-activesg-sport-hall) | 2026-10-28 |
| Hougang Sports Centre | Hougang Sport Hall | 538832 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/hougang-sport-hall) | 2026-10-28 |
| Pasir Ris Sport Centre | Pasir Ris Sport Hall | 519640 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/pasir-ris-sport-hall) | 2026-10-28 |
| Sengkang Sport Centre | Sengkang Sport Hall | 544964 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/sengkang-sport-hall) | 2026-10-28 |
| Yishun Sport Hall | Yishun Sport Hall | 769130 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/yishun-sport-hall) | 2026-10-28 |
| Bukit Gombak Sport Hall | Bukit Gombak Sport Hall | 659088 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/bukit-gombak-sport-hall) | 2026-10-30 |
| Senja-Cashew Sport Hall | Senja-Cashew Sport Hall | 679910 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/senja-cashew-sport-hall) | 2026-10-30 |
| Woodlands Sport Hall | Woodlands Sport Hall | 738620 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/woodlands-sport-hall) | 2026-10-30 |
| Yio Chu Kang Sport Hall | Yio Chu Kang Sport Hall | 569780 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/yio-chu-kang-sport-hall) | 2026-10-30 |
| Admiralty Primary School | Admiralty Primary School Hall | 738907 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/admiralty-primary-school-hall) | 2026-10-30 |
| Greendale Primary School | Greendale Primary School Hall | 828848 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/greendale-primary-school-hall) | 2026-10-30 |
| North Vista Secondary School | North Vista Secondary School Hall | 545081 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/north-vista-secondary-school-hall) | 2026-10-30 |
| Junyuan Secondary School | Junyuan Secondary School Hall | 528933 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/junyuan-secondary-school-hall) | 2026-10-30 |
| Dunman High School | Dunman High School Hall | 436895 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/dunman-high-school-hall) | 2026-10-30 |
| Boon Lay Secondary School | Boon Lay Secondary School Hall | 648354 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/boon-lay-secondary-school-hall) | 2026-10-30 |
| Frontier Primary School | Frontier Primary School Hall | 648200 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/frontier-primary-school-hall) | 2026-10-30 |
| Queenstown Primary School | Queenstown Primary School Hall | 149303 | [ActiveSG](https://www.activesgcircle.gov.sg/facilities/queenstown-primary-school-hall) | 2026-10-30 |

## Explicit exclusion

Toa Payoh Sport Centre is not in the allowlist. Its official ActiveSG page says
the entire facility is closed for redevelopment from 31 October 2023 to 2030.
The implementation plan originally named it as a candidate, but a current
official closure is stronger evidence than that older planning assumption.

## Maintenance procedure

1. Match the exact data.gov.sg `VenueName` and six-digit `PostalCode`.
2. Confirm an official ActiveSG or agency page for the same public facility.
3. Recompute the source key from the normalized source name and postal code.
4. Record the official evidence URL and verification date in
   `backend/app/data/verified_public_sports_venues.json`.
5. Record every activity covered by that evidence in `verified_activities`.
   Do not infer support for other activities from rows sharing the same venue.
6. A school hall must have an official ActiveSG badminton facility page with a
   public booking entry. A raw school dataset row is not sufficient evidence.
7. Do not add condominiums, uniformed-service sites, unnamed rows, or any venue
   known to be under long-term closure.
