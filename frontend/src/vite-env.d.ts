/// <reference types="vite/client" />

/**
 * Build-time flags, replaced by Vite's `define` (see vite.config.ts) so the
 * bundler can drop mock-only code from production builds.
 * - __MOCKS_ENABLED__: the in-page mock backend runs (dev server, or the demo build).
 * - __DEMO__: the self-contained demo build (`npm run build:demo`).
 */
declare const __MOCKS_ENABLED__: boolean
declare const __DEMO__: boolean

interface ImportMetaEnv {
  /** Backend origin, e.g. "https://api.example.com". Empty = same origin. */
  readonly VITE_API_BASE_URL?: string
  /** Set to "false" to turn MSW off and talk to the real backend in dev. */
  readonly VITE_USE_MOCKS?: string
  /** Where the dev server proxies /api when mocks are off. */
  readonly VITE_API_PROXY_TARGET?: string
  /** Enable the backend's explicit local demo-login endpoints. */
  readonly VITE_DEMO_AUTH?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
