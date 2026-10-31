import assert from 'node:assert/strict'
import test from 'node:test'

import * as venueGuidance from '../src/results/venueGuidance.ts'

const { venueAvailabilityGuidance, venueCategoryLabel } = venueGuidance

test('park guidance is honest about public access and NParks conditions', () => {
  const guidance = venueAvailabilityGuidance('PARK')

  assert.match(guidance, /public access/i)
  assert.match(guidance, /not guaranteed/i)
  assert.match(guidance, /NParks/i)
  assert.match(guidance, /closure|rules/i)
  assert.doesNotMatch(guidance, /is booked|is available/i)
  assert.equal(venueCategoryLabel('PARK'), 'Park')
})

test('sports guidance retains ActiveSG booking language without making a live claim', () => {
  const guidance = venueAvailabilityGuidance('SPORTS_FACILITY')

  assert.match(guidance, /ActiveSG/i)
  assert.match(guidance, /booking/i)
  assert.match(guidance, /not guaranteed/i)
  assert.doesNotMatch(guidance, /is booked|is available/i)
  assert.equal(venueCategoryLabel('SPORTS_FACILITY'), 'Sports facility')
})

test('official information labels are specific to parks', () => {
  const officialLinkLabel = (
    venueGuidance as typeof venueGuidance & {
      venueOfficialLinkLabel?: (category: 'PARK' | 'SPORTS_FACILITY' | 'MALL') => string
    }
  ).venueOfficialLinkLabel

  assert.equal(typeof officialLinkLabel, 'function')
  assert.equal(officialLinkLabel?.('PARK'), 'View official park information')
  assert.equal(officialLinkLabel?.('SPORTS_FACILITY'), 'View official venue information')
  assert.equal(officialLinkLabel?.('MALL'), 'View official venue information')
})
