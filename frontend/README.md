# Group Scheduling Application: frontend

React + TypeScript + Vite client for the SC2006 Group Scheduling Application.
Mobile-first: every screen must work at a 375px viewport (SRS NFR-6).

## Stack

- React 19, TypeScript, Vite
- react-router (routing), TanStack Query (server state)
- MSW (mock backend while the FastAPI backend is being built)

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build
npm run lint
```

> **Path gotcha:** don't run this from a folder whose path contains a colon (`:`),
> e.g. `Uni 26:27/`. npm adds `node_modules/.bin` to `PATH`, which is
> colon-separated, so `npm run` can't find `tsc`/`vite`, and Vite's dev server
> refuses to serve files from that path.

## Mock backend (MSW)

`npm run dev` starts with a mock API in the browser, so no backend is needed.
The mock follows `docs/api-contract.md`, which is the contract for the backend team.

- You start signed in as **Wei Jie** (organiser of "Weekend badminton").
- **Switch persona** with the yellow `DEV · <name>` pill above the bottom nav. For example,
  Amirah is a participant in "Weekend badminton" (try `/sessions/s-badminton/status`
  as each). Signing out there or on Profile takes you to `/signin`, where you pick
  who to sign in as. The signed-in persona survives reloads (this tab only).
- Mock data lives in memory and **resets on every page reload**.
- Test invitation links: `/join/mock-karaoke-invite` (not joined yet),
  `/join/mock-picnic-invite` (cancelled), anything else is invalid.
- Location search: a query containing `offline` simulates OneMap being down;
  `zzz` returns no matches.
- To use the real backend instead: create `.env.local` with `VITE_USE_MOCKS=false`
  (see `.env.example`). `/api` is then proxied to `http://localhost:8000`.
- Mocks are dev-only: production builds contain no mock code.
- The mock runs inside the page (no service worker), so it works in any browser,
  including embedded preview panes. Mocked calls don't appear in the Network tab.

## Structure

```
src/
  api/          types.ts (wire types), client.ts (only place fetch is called), hooks/ (one per resource)
  app/          router, app shell (header + bottom nav), route metadata
  auth/         AuthProvider (GET /api/me), RequireAuth, RequireOrganiser, return-to-after-sign-in
  dev/          dev-only persona switcher (mocks only, not in production builds)
  pages/        one component per screen (SRS §3.1)
  components/   shared UI
  lib/          helpers (time.ts: timezone-aware formatting)
  mocks/        MSW handlers + in-memory mock db (dev only)
  styles/       design tokens + global CSS
  config.ts     app constants (SLOT_MINUTES, duration limits, …)
```

## Rules

- Pages never call `fetch` directly; all data goes through `src/api/`.
- No client-side calls to external APIs (OneMap, Google, …); only the backend talks to them (SRS §2.1).
- Every route except `/signin` is behind `RequireAuth`; organiser-only screens also use
  `RequireOrganiser`. These only hide UI; the backend enforces the same rules.
- Never render another participant's address (NFR-13). Never log the invitation token (SRS §3.4);
  it's only ever sent to the API in POST bodies, never in API URLs.
- Show times in the Session's timezone, not the browser's.
