import type { ApiErrorBody, ApiErrorCode } from './types'

/**
 * The only place in the app that calls `fetch`. Pages and components use the
 * hooks in src/api/hooks/, which call `api.*` here. Swapping MSW for the real
 * FastAPI backend changes nothing above this file.
 *
 * Auth is an httpOnly session cookie set by the backend after Google sign-in,
 * so every request is sent with credentials and no token is ever handled here.
 */

/** Empty by default: requests go to the same origin (Vite proxies /api in dev). */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

/**
 * Base for building absolute request URLs. A sandboxed frame (like the hosted
 * demo) can report its origin as "null", so fall back to a placeholder there;
 * in that case requests are answered in-page by the mock backend anyway.
 */
export function pageOrigin(): string {
  const origin = window.location.origin
  return origin.startsWith('http') ? origin : 'https://app.invalid'
}

export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode
  readonly fields: Record<string, string>

  constructor(status: number, code: ApiErrorCode, message: string, fields?: Record<string, string>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields ?? {}
  }

  /** Inline error for one form field (SRS §3.1: errors appear beneath the field). */
  fieldError(field: string): string | undefined {
    return this.fields[field]
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/** How a Request gets answered. The real network by default. */
export type Transport = (request: Request) => Promise<Response>

let transport: Transport = (req) => fetch(req)

/**
 * Dev only: lets the mock backend answer requests in-page (src/mocks/install.ts).
 * Production never calls this, so requests always go to the real network.
 */
export function setTransport(next: Transport) {
  transport = next
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await transport(
      new Request(new URL(`${API_BASE_URL}${path}`, pageOrigin()), {
        method,
        headers,
        credentials: 'include',
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
    )
  } catch {
    // Deliberately not including the URL or body: either may carry Access Data.
    throw new ApiError(0, 'NETWORK_ERROR', "Couldn't reach the server. Check your connection and try again.")
  }

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const data: unknown = text ? safeParse(text) : undefined

  if (!response.ok) {
    const err = isErrorBody(data) ? data.error : undefined
    throw new ApiError(
      response.status,
      err?.code ?? fallbackCode(response.status),
      err?.message ?? 'Something went wrong. Please try again.',
      err?.fields,
    )
  }

  return data as T
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

function isErrorBody(data: unknown): data is ApiErrorBody {
  return (
    typeof data === 'object' &&
    data !== null &&
    'error' in data &&
    typeof (data as ApiErrorBody).error?.code === 'string'
  )
}

function fallbackCode(status: number): ApiErrorCode {
  if (status === 401) return 'UNAUTHENTICATED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 422) return 'VALIDATION_FAILED'
  if (status === 503) return 'EXTERNAL_SERVICE_UNAVAILABLE'
  return 'UNKNOWN'
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
}

/**
 * Full-page redirects to backend endpoints (Google sign-in, Calendar consent).
 * These must be top-level navigations, not fetches, so the backend can set
 * cookies and bounce through Google's consent screen.
 */
export function redirectToBackend(path: string, next?: string) {
  const url = new URL(`${API_BASE_URL}${path}`, pageOrigin())
  if (next) url.searchParams.set('next', next)
  window.location.assign(url.toString())
}

/** React Query retry policy: never retry 4xx responses. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}
