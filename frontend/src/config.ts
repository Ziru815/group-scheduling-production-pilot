/**
 * App-wide constants. Values marked TBD trace to SRS Appendix C and must be
 * revisited when the team or client closes the item.
 */

/**
 * Length of one cell in the availability grid, in minutes.
 * TBD-13: the Candidate Timeslot step is undecided; the grid uses this single
 * constant so it can change in one place.
 */
export const SLOT_MINUTES = 30

/**
 * Fallback only. Every Session carries its own timezone (SRS §6); times must be
 * shown in the Session's timezone, never the browser's.
 */
export const DEFAULT_TIMEZONE = 'Asia/Singapore'

/** FR-A1.1: permitted session duration range, in minutes. */
export const DURATION_MIN_MINUTES = 15
export const DURATION_MAX_MINUTES = 480

/** FR-D9.1: weighting snaps to 10% steps. */
export const WEIGHT_STEP_PERCENT = 10

// Mock-only code is gated with the build-time flag __MOCKS_ENABLED__ (see
// src/vite-env.d.ts), used inline so production builds drop it entirely.
