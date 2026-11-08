import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useCalendarConnection, useConnectCalendar, useDisconnectCalendar } from '../api/hooks/calendar'
import type { CalendarConnectionStatus } from '../api/types'
import { InlineConfirm } from '../components/InlineConfirm'
import './CalendarSection.css'

const STATUS_COPY: Record<CalendarConnectionStatus, { label: string; tone: 'ok' | 'muted' | 'warn'; body: string }> = {
  CONNECTED: {
    label: 'Connected',
    tone: 'ok',
    body: 'You can import busy times on any availability grid. Confirmed plans are added to your calendar.',
  },
  DISCONNECTED: {
    label: 'Not connected',
    tone: 'muted',
    body: 'Optional. Connect to fill in your availability from your calendar instead of marking it by hand.',
  },
  DECLINED: {
    label: 'Not connected',
    tone: 'muted',
    body: "You didn't grant calendar access. That's fine: you can always mark your times by hand.",
  },
  EXPIRED: {
    label: 'Needs reconnecting',
    tone: 'warn',
    body: 'Google access has expired. Reconnect to keep importing busy times.',
  },
  ERROR: {
    label: 'Problem connecting',
    tone: 'warn',
    body: "Something went wrong with the connection to Google Calendar. Try connecting again.",
  },
}

const RETURN_COPY: Record<string, { label: string; tone: 'ok' | 'muted' | 'warn'; body: string }> = {
  declined: STATUS_COPY.DECLINED,
  unavailable: {
    label: 'Connection unavailable',
    tone: 'warn',
    body: "Google Calendar couldn't be connected right now. Try again later; manual availability still works.",
  },
  'wrong-account': {
    label: 'Different Google account',
    tone: 'warn',
    body: 'Reconnect using the same Google account you use to sign in to Group Scheduler.',
  },
  'missing-scopes': {
    label: 'Permissions incomplete',
    tone: 'warn',
    body: 'The required Calendar permissions were not granted. Reconnect to try again.',
  },
}

/**
 * Google Calendar connection (FR-B8). Separate from Google sign-in, and fully
 * optional: manual entry always works (FR-B8.1). Free/busy only (NFR-14).
 */
export function CalendarSection() {
  const connection = useCalendarConnection()
  const connect = useConnectCalendar()
  const disconnect = useDisconnectCalendar()
  const [params] = useSearchParams()
  const [confirming, setConfirming] = useState(false)
  const returnCopy = RETURN_COPY[params.get('calendar') ?? '']

  const status: CalendarConnectionStatus | undefined = connection.data?.status
  const copy = status ? (status === 'CONNECTED' ? STATUS_COPY.CONNECTED : returnCopy ?? STATUS_COPY[status]) : null
  const error = connection.error ?? connect.error ?? disconnect.error

  return (
    <section className="calsec" aria-labelledby="calsec-title">
      <div className="calsec__head">
        <h3 className="calsec__title" id="calsec-title">
          Google Calendar
        </h3>
        {copy && <span className={`calsec__badge calsec__badge--${copy.tone}`}>{copy.label}</span>}
      </div>

      {connection.isPending && <p className="calsec__body">Checking your calendar connection…</p>}
      {copy && <p className="calsec__body">{copy.body}</p>}

      <p className="calsec__privacy">
        We only see when you're busy, never event titles, descriptions or who's invited. We only ever add or remove events
        we created ourselves.
      </p>

      {error && (
        <p className="calsec__error" role="alert">
          {error.message}
        </p>
      )}

      {status === 'CONNECTED' ? (
        confirming ? (
          <InlineConfirm
            text="Disconnect Google Calendar? You can still mark your times by hand, and you can reconnect any time."
            confirmLabel="Disconnect"
            cancelLabel="Keep connected"
            busy={disconnect.isPending}
            busyLabel="Disconnecting…"
            danger
            onConfirm={() => disconnect.mutate(undefined, { onSuccess: () => setConfirming(false) })}
            onCancel={() => setConfirming(false)}
          />
        ) : (
          <button type="button" className="calsec__secondary" onClick={() => setConfirming(true)}>
            Disconnect
          </button>
        )
      ) : (
        status && (
          <button
            type="button"
            className="btn-primary"
            disabled={connect.isPending}
            onClick={() => connect.mutate('/profile')}
          >
            {connect.isPending ? 'Connecting…' : status === 'DISCONNECTED' || status === 'DECLINED' ? 'Connect Google Calendar' : 'Reconnect Google Calendar'}
          </button>
        )
      )}
    </section>
  )
}
