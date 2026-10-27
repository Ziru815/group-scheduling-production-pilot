/**
 * Plain hyperlink to Google Maps for a public Venue location (FR-E1 "map
 * pin"). The user opens it; no map API is called from the client (SRS §2.1,
 * api-contract.md open question 18).
 */
export function mapsLink(lat: number, lng: number) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
}
