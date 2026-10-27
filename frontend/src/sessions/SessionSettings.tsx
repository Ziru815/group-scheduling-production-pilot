import { useState, type FormEvent } from 'react'
import { isApiError } from '../api/client'
import { useUpdateSession } from '../api/hooks/sessions'
import type { SessionDetail } from '../api/types'
import { FormField } from '../components/FormField'
import { DURATION_MAX_MINUTES, DURATION_MIN_MINUTES } from '../config'
import { rowLabel } from '../availability/slots'
import { formatDateTime, formatIsoDate, localTimeToMinutes, timeZoneLabel } from '../lib/time'
import {
  FIELD_ORDER,
  formFromSession,
  pickFieldErrors,
  toUpdateRequest,
  validateNewSession,
  type NewSessionErrors,
  type NewSessionField,
  type NewSessionForm,
} from './newSessionForm'
import './SessionSettings.css'

const fid = (f: NewSessionField) => `edit-${f}`

/**
 * UC-02 Manage Session: shows the Session's settings and lets the Organiser
 * change dates, daily window, duration, deadline or minimum attendees.
 * Invalid changes leave everything as it was (UC-02.EX.1).
 */
export function SessionSettings({ session, onSaved }: { session: SessionDetail; onSaved: (message: string) => void }) {
  const [editing, setEditing] = useState(false)
  const editable = session.status === 'ACTIVE'

  if (!editing) {
    const dates =
      session.startDate === session.endDate
        ? formatIsoDate(session.startDate)
        : `${formatIsoDate(session.startDate)} – ${formatIsoDate(session.endDate)}`
    return (
      <section className="ssettings" aria-labelledby="ssettings-title">
        <div className="ssettings__head">
          <h3 className="ssettings__title" id="ssettings-title">
            Session details
          </h3>
          {editable && (
            <button type="button" className="ssettings__edit" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
        </div>
        <dl className="ssettings__list">
          <Row label="Activity" value={session.activityType.name} />
          <Row label="Dates" value={dates} />
          <Row
            label="Times each day"
            value={`${rowLabel(localTimeToMinutes(session.dailyStartTime))} – ${rowLabel(localTimeToMinutes(session.dailyEndTime))}`}
          />
          <Row label="Duration" value={`${session.durationMinutes} min`} />
          <Row label="Minimum attendees" value={String(session.minimumAttendees)} />
          <Row label="Response deadline" value={formatDateTime(session.responseDeadline, session.timezone)} />
        </dl>
      </section>
    )
  }

  return (
    <EditForm
      session={session}
      onDone={(message) => {
        setEditing(false)
        if (message) onSaved(message)
      }}
    />
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="ssettings__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function EditForm({ session, onDone }: { session: SessionDetail; onDone: (message?: string) => void }) {
  const tz = session.timezone
  const [original] = useState(() => formFromSession(session))
  const [form, setForm] = useState<NewSessionForm>(original)
  const [errors, setErrors] = useState<NewSessionErrors>({})
  const update = useUpdateSession(session.id)

  function set<K extends keyof NewSessionForm>(key: K, value: NewSessionForm[K]) {
    const next = { ...form, [key]: value }
    setForm(next)
    if (Object.keys(errors).length) setErrors(validateNewSession(next, tz, original))
  }

  function focusFirst(errs: NewSessionErrors) {
    const first = FIELD_ORDER.find((f) => errs[f])
    if (first) document.getElementById(fid(first))?.focus()
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const errs = validateNewSession(form, tz, original)
    setErrors(errs)
    if (Object.keys(errs).length) return focusFirst(errs)

    const changes = toUpdateRequest(form, original, tz)
    if (Object.keys(changes).length === 0) return onDone()

    update.mutate(changes, {
      onSuccess: (saved) =>
        onDone(
          saved.recommendationsStale
            ? 'Session details saved. The ranked options are now out of date: update them when you’re ready.'
            : 'Session details saved.',
        ),
      onError: (err) => {
        if (isApiError(err) && err.code === 'VALIDATION_FAILED') {
          const serverErrs = pickFieldErrors(err.fields)
          setErrors(serverErrs)
          focusFirst(serverErrs)
        }
      },
    })
  }

  const generalError =
    update.isError && !(isApiError(update.error) && update.error.code === 'VALIDATION_FAILED')
      ? update.error.message
      : null

  const text = (f: NewSessionField, label: string, opts: { hint?: string; numeric?: boolean } = {}) => (
    <FormField id={fid(f)} label={label} hint={opts.hint} error={errors[f]}>
      {(control) => (
        <input
          {...control}
          className="input"
          type="text"
          inputMode={opts.numeric ? 'numeric' : undefined}
          value={form[f]}
          onChange={(e) => set(f, e.target.value)}
        />
      )}
    </FormField>
  )

  const typed = (f: NewSessionField, label: string, type: string, opts: { hint?: string } = {}) => (
    <FormField id={fid(f)} label={label} hint={opts.hint} error={errors[f]}>
      {(control) => (
        <input
          {...control}
          className="input"
          type={type}
          step={type === 'time' ? 1800 : undefined}
          value={form[f]}
          onChange={(e) => set(f, e.target.value)}
        />
      )}
    </FormField>
  )

  return (
    <form className="ssettings ssettings--editing" onSubmit={handleSubmit} noValidate aria-labelledby="ssettings-edit-title">
      <h3 className="ssettings__title" id="ssettings-edit-title">
        Edit session details
      </h3>
      {text('name', 'Session name')}
      <div className="ssettings__pair">
        {typed('startDate', 'Starts', 'date')}
        {typed('endDate', 'Ends', 'date')}
      </div>
      <div className="ssettings__pair">
        {typed('dailyStartTime', 'Earliest start', 'time')}
        {typed('dailyEndTime', 'Latest end', 'time')}
      </div>
      {text('durationMinutes', 'Duration (minutes)', {
        hint: `Between ${DURATION_MIN_MINUTES} and ${DURATION_MAX_MINUTES} minutes`,
        numeric: true,
      })}
      {typed('responseDeadline', 'Response deadline', 'datetime-local', {
        hint: `${timeZoneLabel(tz)}. Must be before the start date.`,
      })}
      {text('minimumAttendees', 'Minimum attendees needed', { numeric: true })}

      {generalError && (
        <p className="ssettings__error" role="alert">
          {generalError}
        </p>
      )}
      <div className="ssettings__actions">
        <button type="submit" className="btn-primary" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </button>
        <button type="button" className="ssettings__cancel" onClick={() => onDone()} disabled={update.isPending}>
          Cancel
        </button>
      </div>
    </form>
  )
}
