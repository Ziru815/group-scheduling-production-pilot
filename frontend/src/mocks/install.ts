import { getResponse } from 'msw'
import { pageOrigin, setTransport } from '../api/client'
import { handlers } from './handlers'

declare global {
  interface Window {
    /** Dev console helper: call the mock API directly, e.g. `await (await __mockFetch('/api/me')).json()`. */
    __mockFetch?: (path: string, init?: RequestInit) => Promise<Response>
  }
}

async function answer(request: Request): Promise<Response> {
  const response = await getResponse(handlers, request)
  // The handlers include a catch-all for /api/*, so this is only a safety net.
  return response ?? Response.json({ error: { code: 'NOT_MOCKED', message: 'No mock handler.' } }, { status: 501 })
}

/**
 * Dev only. Routes every API request from src/api/client.ts to the MSW
 * handlers inside the page, with no service worker and no network. Works in
 * every browser, including embedded preview panes that block service workers.
 *
 * Trade-off: mocked calls don't show in the browser's Network tab. Use
 * `__mockFetch` in the console to poke the mock API instead.
 */
export function installMockTransport() {
  setTransport(answer)
  window.__mockFetch = (path, init) => answer(new Request(new URL(path, pageOrigin()), init))
}
