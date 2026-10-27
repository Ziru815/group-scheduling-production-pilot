import type { ReactNode } from 'react'
import './StatusMessage.css'

type Props = {
  /** Show a spinner (loading states). */
  busy?: boolean
  title?: string
  children?: ReactNode
  /** Optional action, e.g. a Retry button or a Link. */
  action?: ReactNode
  /** Centre in the whole viewport instead of the content area. */
  fullPage?: boolean
}

/** Loading, empty and error states, shown in place (SRS §3.1: no modal errors). */
export function StatusMessage({ busy, title, children, action, fullPage }: Props) {
  return (
    <div
      className={fullPage ? 'status status--full' : 'status'}
      role={busy ? 'status' : undefined}
      aria-live="polite"
    >
      {busy && <span className="status__spinner" aria-hidden="true" />}
      {title && <p className="status__title">{title}</p>}
      {children && <div className="status__body">{children}</div>}
      {action && <div className="status__action">{action}</div>}
    </div>
  )
}
