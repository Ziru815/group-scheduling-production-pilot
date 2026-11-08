import assert from 'node:assert/strict'
import test from 'node:test'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React, { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import { MemoryRouter, Route, Routes } from 'react-router'

import { queryKeys } from '../src/api/queryKeys.ts'
import type { CreateSessionResponse, ResponseStatusList, SessionDetail } from '../src/api/types.ts'
import { ResponseStatusPage } from '../src/pages/ResponseStatusPage.tsx'
import { InviteCreated } from '../src/sessions/InviteCreated.tsx'

const invitationUrl = 'https://group-scheduling-app.onrender.com/join/token-123'
const expectedMessage = [
  'You\'re invited to “Weekend Picnic”',
  'Activity: Picnic',
  'Dates: Sat, 7 Nov – Sun, 8 Nov',
  'Respond by: Fri, 6 Nov, 9:00 pm',
  `Join and mark when you're free: ${invitationUrl}`,
].join('\n')

const session: SessionDetail = {
  id: 'session-123',
  name: 'Weekend Picnic',
  activityType: { id: 'picnic', name: 'Picnic', category: 'Outdoors' },
  activitySupported: true,
  organiserName: 'Ziru',
  status: 'ACTIVE',
  myRole: 'ORGANISER',
  myResponseStatus: 'SUBMITTED',
  startDate: '2026-11-07',
  endDate: '2026-11-08',
  dailyStartTime: '09:00',
  dailyEndTime: '18:00',
  timezone: 'Asia/Singapore',
  durationMinutes: 120,
  responseDeadline: '2026-11-06T13:00:00Z',
  minimumAttendees: 2,
  travelObjective: 'MINIMIZE_MAX',
  attendanceWeightPercent: 60,
  isClosed: false,
  recommendationsStale: false,
  hasRecommendations: false,
  confirmed: null,
}

const responses: ResponseStatusList = {
  participants: [
    {
      participantId: 'organiser-123',
      displayName: 'Ziru',
      role: 'ORGANISER',
      responseStatus: 'SUBMITTED',
      updatedAt: '2026-11-01T09:00:00+08:00',
    },
  ],
  counts: { SUBMITTED: 1, NOT_SUBMITTED: 0, WITHDRAWN: 0 },
  refreshedAt: '2026-11-01T09:00:00+08:00',
}

type Rendered = { container: HTMLElement; root: Root; window: Window }

async function render(element: ReactNode, writes: string[]): Promise<Rendered> {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'https://group-scheduling-app.onrender.com/sessions',
  })
  const browserWindow = dom.window as unknown as Window
  Object.defineProperty(globalThis, 'window', { configurable: true, value: browserWindow })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: browserWindow.document })
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: browserWindow.navigator })
  Object.defineProperty(browserWindow.navigator, 'clipboard', {
    configurable: true,
    value: { writeText: async (text: string) => void writes.push(text) },
  })
  Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

  const container = browserWindow.document.getElementById('root')!
  const root = createRoot(container)
  await act(async () => {
    root.render(element)
  })
  return { container, root, window: browserWindow }
}

function button(container: HTMLElement, label: string): HTMLButtonElement {
  const match = Array.from(container.querySelectorAll('button')).find(
    (candidate) => candidate.textContent?.trim() === label,
  )
  assert.ok(match, `expected a “${label}” button`)
  return match
}

async function click(element: HTMLElement) {
  await act(async () => {
    element.click()
  })
}

async function cleanup(rendered: Rendered) {
  await act(async () => rendered.root.unmount())
  ;(rendered.window as unknown as { close: () => void }).close()
}

test('new Session success shares the complete invitation and offers a QR code', async () => {
  const writes: string[] = []
  const result: CreateSessionResponse = { session, invitationUrl }
  const rendered = await render(
    <MemoryRouter>
      <InviteCreated result={result} onCreateAnother={() => undefined} />
    </MemoryRouter>,
    writes,
  )
  try {
    await click(button(rendered.container, 'Copy invitation message'))
    assert.deepEqual(writes, [expectedMessage])
    assert.ok(button(rendered.container, 'Show QR code'))
  } finally {
    await cleanup(rendered)
  }
})

test('organiser response status shares the same complete invitation', async () => {
  const writes: string[] = []
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(queryKeys.session(session.id), session)
  queryClient.setQueryData(queryKeys.invitationLink(session.id), { invitationUrl })
  queryClient.setQueryData(queryKeys.responseStatus(session.id), responses)

  const rendered = await render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/sessions/${session.id}/status`]}>
        <Routes>
          <Route path="/sessions/:id/status" element={<ResponseStatusPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
    writes,
  )
  try {
    await click(button(rendered.container, 'Copy invitation message'))
    assert.deepEqual(writes, [expectedMessage])
    assert.ok(button(rendered.container, 'Show QR code'))
  } finally {
    await cleanup(rendered)
    queryClient.clear()
  }
})
