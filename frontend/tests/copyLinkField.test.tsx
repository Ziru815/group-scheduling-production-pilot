import assert from 'node:assert/strict'
import test from 'node:test'

import React, { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { JSDOM } from 'jsdom'

import { CopyLinkField } from '../src/components/CopyLinkField.tsx'

const url = 'https://group-scheduling-app.onrender.com/join/token-123'
const message = `You're invited to “Weekend Picnic”\nJoin and mark when you're free: ${url}`

type Rendered = {
  container: HTMLElement
  root: Root
  window: Window
}

async function renderField(writeText: (text: string) => Promise<void>): Promise<Rendered> {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'https://group-scheduling-app.onrender.com/sessions/new',
  })
  const browserWindow = dom.window as unknown as Window

  Object.defineProperty(globalThis, 'window', { configurable: true, value: browserWindow })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: browserWindow.document })
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: browserWindow.navigator })
  Object.defineProperty(browserWindow.navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
  Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

  const container = browserWindow.document.getElementById('root')!
  const root = createRoot(container)
  await act(async () => {
    root.render(
      <CopyLinkField
        id="invite-link"
        label="Invite link"
        url={url}
        message={message}
        showQr
      />,
    )
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
  await act(async () => {
    rendered.root.unmount()
  })
  ;(rendered.window as unknown as { close: () => void }).close()
}

test('keeps the QR hidden until the organiser expands it', async () => {
  const rendered = await renderField(async () => undefined)
  try {
    assert.equal(rendered.container.querySelector('svg'), null)
    assert.doesNotMatch(rendered.container.textContent ?? '', /people nearby/i)
    assert.doesNotMatch(rendered.container.textContent ?? '', /online sharing/i)

    const toggle = button(rendered.container, 'Show QR code')
    assert.equal(toggle.getAttribute('aria-expanded'), 'false')
    await click(toggle)

    assert.ok(rendered.container.querySelector('svg'))
    assert.equal(rendered.container.querySelector('svg title')?.textContent, 'Invitation QR code')
    assert.match(rendered.container.textContent ?? '', /people nearby/i)
    assert.match(rendered.container.textContent ?? '', /online sharing/i)
    assert.equal(button(rendered.container, 'Hide QR code').getAttribute('aria-expanded'), 'true')

    await click(button(rendered.container, 'Hide QR code'))
    assert.equal(rendered.container.querySelector('svg'), null)
    assert.doesNotMatch(rendered.container.textContent ?? '', /people nearby/i)
    assert.doesNotMatch(rendered.container.textContent ?? '', /online sharing/i)
  } finally {
    await cleanup(rendered)
  }
})

test('copies the complete invitation message', async () => {
  const writes: string[] = []
  const rendered = await renderField(async (text) => {
    writes.push(text)
  })
  try {
    await click(button(rendered.container, 'Copy invitation message'))

    assert.deepEqual(writes, [message])
    assert.match(rendered.container.textContent ?? '', /Invitation message copied/)
  } finally {
    await cleanup(rendered)
  }
})

test('selects the raw link when invitation message copying fails', async () => {
  const rendered = await renderField(async () => {
    throw new Error('clipboard unavailable')
  })
  try {
    await click(button(rendered.container, 'Copy invitation message'))

    const input = rendered.container.querySelector<HTMLInputElement>('#invite-link')!
    assert.equal(input.selectionStart, 0)
    assert.equal(input.selectionEnd, url.length)
    assert.match(rendered.container.textContent ?? '', /copy it manually/i)
  } finally {
    await cleanup(rendered)
  }
})
