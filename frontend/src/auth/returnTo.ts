/**
 * Remembers which page to return to after Google sign-in.
 *
 * The real sign-in is a full-page round trip through Google, so in-memory
 * router state is lost. The path is kept in this tab's sessionStorage instead
 * of the backend's `next` parameter, so an invitation token in a /join/ path
 * never leaves the browser (SRS §3.4).
 */
const KEY = 'auth.return-to'

/** Only same-app absolute paths: blocks "//evil.com" and full URLs. */
export function isSafeInAppPath(path: unknown): path is string {
  return typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/signin')
}

export function saveReturnTo(path: string) {
  if (!isSafeInAppPath(path)) return
  try {
    sessionStorage.setItem(KEY, path)
  } catch {
    // Storage blocked: the user lands on /sessions after sign-in instead.
  }
}

export function consumeReturnTo(): string | null {
  try {
    const path = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    return isSafeInAppPath(path) ? path : null
  } catch {
    return null
  }
}
