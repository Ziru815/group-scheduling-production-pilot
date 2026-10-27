/**
 * Mock builds only. In a fully sandboxed frame (like the hosted demo), merely
 * touching `localStorage`, `sessionStorage` or `document.cookie` throws.
 * MSW's cookie store does that as soon as it loads, which would stop the app
 * from starting. When the browser blocks them, swap in throwaway in-memory
 * versions so the mock backend can run. Nothing here is used by real builds.
 */

function isBlocked(read: () => unknown): boolean {
  try {
    read()
    return false
  } catch {
    return true
  }
}

function memoryStorage(): Storage {
  const data = new Map<string, string>()
  return {
    get length() {
      return data.size
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, String(value)),
  }
}

export function shimBlockedStorage() {
  for (const name of ['localStorage', 'sessionStorage'] as const) {
    if (isBlocked(() => window[name])) {
      Object.defineProperty(window, name, { value: memoryStorage(), configurable: true })
    }
  }
  if (isBlocked(() => document.cookie)) {
    Object.defineProperty(document, 'cookie', { get: () => '', set: () => {}, configurable: true })
  }
}
