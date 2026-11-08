import type { VenueCategory } from '../api/types'

export function venueCategoryLabel(category: VenueCategory): string {
  if (category === 'PARK') return 'Park'
  if (category === 'SPORTS_FACILITY') return 'Sports facility'
  return 'Venue'
}

export function venueOfficialLinkLabel(category: VenueCategory): string {
  return category === 'PARK' ? 'View official park information' : 'View official venue information'
}

export function venueAvailabilityGuidance(category: VenueCategory): string {
  if (category === 'PARK') {
    return 'Public access, reservation and live availability are not guaranteed. Check NParks for current closures, opening conditions and park rules before you go.'
  }
  if (category === 'SPORTS_FACILITY') {
    return 'Court or pitch booking and live availability are not guaranteed. Check ActiveSG for current closures and booking details.'
  }
  return 'Opening hours, reservation and live availability are not guaranteed. Check with the venue before you go.'
}
