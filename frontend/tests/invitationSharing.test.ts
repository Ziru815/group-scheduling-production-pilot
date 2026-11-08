import assert from 'node:assert/strict'
import test from 'node:test'

import { buildInvitationMessage } from '../src/sessions/invitationSharing.ts'

const invitationUrl = 'https://group-scheduling-app.onrender.com/join/token-123'

test('formats a complete single-day invitation in the Session timezone', () => {
  const message = buildInvitationMessage({
    name: 'Weekend Picnic',
    activityName: 'Picnic',
    startDate: '2026-11-07',
    endDate: '2026-11-07',
    responseDeadline: '2026-11-06T13:00:00Z',
    timezone: 'Asia/Singapore',
    invitationUrl,
  })

  assert.equal(
    message,
    [
      'You\'re invited to “Weekend Picnic”',
      'Activity: Picnic',
      'Dates: Sat, 7 Nov',
      'Respond by: Fri, 6 Nov, 9:00 pm',
      `Join and mark when you're free: ${invitationUrl}`,
    ].join('\n'),
  )
})

test('formats the complete date range for a multi-day invitation', () => {
  const message = buildInvitationMessage({
    name: 'After-class Badminton',
    activityName: 'Badminton',
    startDate: '2026-11-07',
    endDate: '2026-11-08',
    responseDeadline: '2026-11-06T21:30:00+08:00',
    timezone: 'Asia/Singapore',
    invitationUrl,
  })

  assert.equal(
    message,
    [
      'You\'re invited to “After-class Badminton”',
      'Activity: Badminton',
      'Dates: Sat, 7 Nov – Sun, 8 Nov',
      'Respond by: Fri, 6 Nov, 9:30 pm',
      `Join and mark when you're free: ${invitationUrl}`,
    ].join('\n'),
  )
})
