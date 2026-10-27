/** Static metadata attached to each route via `handle`. */
export type RouteHandle = {
  /** Header title. Pages may show a more specific heading in their body. */
  title: string
  /** Entry screen (Your sessions) has no back control (SRS §3.1). */
  hideBack?: boolean
}

export function isRouteHandle(value: unknown): value is RouteHandle {
  return typeof value === 'object' && value !== null && 'title' in value
}
