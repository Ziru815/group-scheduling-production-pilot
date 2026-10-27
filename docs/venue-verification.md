# Public venue verification register

This register explains the evidence behind the first production venue allowlist.
The data.gov.sg Sport Facilities dataset supplies the source identity, postal
code, coordinates, and facility labels. An official ActiveSG page must also
identify the location as a public sport centre or sport hall before the app can
mark it `VERIFIED_PUBLIC`.

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
5. Do not add schools, condominiums, uniformed-service sites, unnamed rows, or
   any venue known to be under long-term closure.
