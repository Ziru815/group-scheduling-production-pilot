import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router'
import { isApiError, shouldRetry } from './api/client'
import { IDENTITY_CHANGE_STORAGE_KEY, resetForNewIdentity } from './api/hooks/me'
import { queryKeys } from './api/queryKeys'
import { router } from './app/router'
import { AuthProvider } from './auth/AuthProvider'
import './styles/global.css'

/**
 * A 401 from any request means the session cookie expired. Re-check /api/me;
 * when that also returns 401 the auth guard sends the user to sign in.
 * (Not for /api/me itself, which would loop.)
 */
function onUnauthenticated(error: unknown, queryKey?: readonly unknown[]) {
  if (!isApiError(error) || error.status !== 401) return
  if (queryKey?.[0] === queryKeys.me[0]) return
  void queryClient.invalidateQueries({ queryKey: queryKeys.me })
}

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: (error, query) => onUnauthenticated(error, query.queryKey) }),
  mutationCache: new MutationCache({ onError: (error) => onUnauthenticated(error) }),
  defaultOptions: {
    queries: { staleTime: 30_000, retry: shouldRetry, refetchOnWindowFocus: true },
  },
})

// All tabs share the backend's httpOnly session cookie. Keep their React Query
// caches in lockstep when the DEV persona (or signed-in account) changes.
window.addEventListener('storage', (event) => {
  if (event.key === IDENTITY_CHANGE_STORAGE_KEY) void resetForNewIdentity(queryClient)
})

/** The mock backend runs in dev (unless VITE_USE_MOCKS=false) and in the demo build only. */
async function enableMocking() {
  if (!__MOCKS_ENABLED__) return
  // Must run before MSW loads (see sandboxShim.ts).
  const { shimBlockedStorage } = await import('./mocks/sandboxShim')
  shimBlockedStorage()
  const { installMockTransport } = await import('./mocks/install')
  installMockTransport()
}

void enableMocking().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
})
