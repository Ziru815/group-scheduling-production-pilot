import { useState } from 'react'
import { isApiError } from '../api/client'
import { useCalendarConnection, useConnectCalendar, useImportCalendarBusy } from '../api/hooks/calendar'
import type { TimeInterval } from '../api/types'
import './CalendarImport.css'

type Props = {
  sessionId: string
  /** Where Google should send the user back to after consent (no token!). */
  returnPath: string
  /** Called with busy blocks once imported. */
  onBusy: (busy: TimeInterval[]) => void
  /** Called right before a full-page redirect, to stash unsaved selections. */
  beforeRedirect: () => void
  /** True when we just came back from Google having declined (FR-B8.1). */
  declined: boolean
  disabled?: boolean
}

/**
 * Optional "Import busy times from Google Calendar" (FR-B8). Medium priority:
 * manual entry always works without it (FR-B8.1). Free/busy only (NFR-14).
 */
export function CalendarImport({ sessionId, returnPath, onBusy, beforeRedirect, declined, disabled }: Props) {
  const connection = useCalendarConnection()
  const connect = useConnectCalendar()
  const importBusy = useImportCalendarBusy(sessionId)
  const [message, setMessage] = useState<{ tone: 'ok' | 'warn'; text: string } | null>(
    declined ? { tone: 'warn', text: "Calendar access wasn't granted. You can still mark your times by hand." } : null,
  )

  function runImport() {
    setMessage(null)
    importBusy.mutate(undefined, {
      onSuccess: (res) => {
        if (res.status !== 'RECEIVED') {
          // NFR-3: say it's unavailable rather than silently showing nothing.
          setMessage({ tone: 'warn', text: "Google Calendar didn't respond, so busy times are unavailable. Mark your times by hand or try again." })
          return
        }
        onBusy(res.busy)
        setMessage({
          tone: 'ok',
          text: res.busy.length
            ? `Imported ${res.busy.length} busy block${res.busy.length === 1 ? '' : 's'}. Check the grid and adjust if needed.`
            : 'No busy times in this date range.',
        })
      },
      onError: (err) => {
        if (isApiError(err) && err.code === 'CALENDAR_NOT_CONNECTED') {
          void connection.refetch()
          setMessage({ tone: 'warn', text: 'Your calendar is no longer connected. Connect it again to import.' })
        } else {
          setMessage({ tone: 'warn', text: err.message })
        }
      },
    })
  }

  function handleClick() {
    if (connection.data?.status === 'CONNECTED') {
      runImport()
      return
    }
    beforeRedirect()
    connect.mutate(returnPath, { onSuccess: runImport })
  }

  const busy = importBusy.isPending || connect.isPending || connection.isPending
  const label = connect.isPending
    ? 'Connecting…'
    : importBusy.isPending
      ? 'Importing…'
      : 'Import busy times from Google Calendar'

  return (
    <div className="calimport">
      <button type="button" className="calimport__btn" onClick={handleClick} disabled={disabled || busy}>
        <CalendarIcon />
        {label}
      </button>
      {message && (
        <p className={`calimport__msg calimport__msg--${message.tone}`} role="status">
          {message.text}
        </p>
      )}
    </div>
  )
}

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="3.5" y="5" width="17" height="15" rx="2" />
      <path d="M3.5 10h17M8 3v4M16 3v4" strokeLinecap="round" />
    </svg>
  )
}
