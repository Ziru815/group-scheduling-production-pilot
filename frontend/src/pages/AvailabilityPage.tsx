import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { isApiError } from '../api/client'
import { useMyResponse, useSaveResponse, useWithdrawResponse } from '../api/hooks/myResponse'
import { useSession } from '../api/hooks/sessions'
import { TRANSPORT_MODES, type MyResponse, type SessionDetail, type TimeInterval, type TransportMode } from '../api/types'
import { AvailabilityGrid } from '../availability/AvailabilityGrid'
import { CalendarImport } from '../availability/CalendarImport'
import { clearDraft, peekDraft, saveDraft } from '../availability/draft'
import { LocationPicker, type PickedLocation } from '../availability/LocationPicker'
import {
  buildGrid,
  coveredSlots,
  formatDurationMinutes,
  formatSelectedDuration,
  overlappedSlots,
  slotKey,
  slotsToIntervals,
  type SlotKey,
} from '../availability/slots'
import { ChipGroup } from '../components/ChipGroup'
import { TRANSPORT_LABELS } from '../sessions/labels'
import { InlineConfirm } from '../components/InlineConfirm'
import { StatusMessage } from '../components/StatusMessage'
import { formatDateTime, timeZoneLabel } from '../lib/time'
import './AvailabilityPage.css'

/**
 * Availability entry (SRS §3.1; UC-06 submit, UC-07 edit/withdraw, UC-08
 * location and transport; FR-B1 to FR-B8). Reached from the invitation link
 * (after joining) or from Your sessions. The Organiser responds here too.
 */
export function AvailabilityPage() {
  const { id } = useParams()
  const session = useSession(id)
  const mine = useMyResponse(id)

  if (session.isPending || mine.isPending) return <StatusMessage busy title="Loading…" />

  const error = session.error ?? mine.error
  if (error) {
    const missing = isApiError(error) && error.status === 404
    return (
      <StatusMessage
        title={missing ? "We couldn't find that session" : "Couldn't load your response"}
        action={
          missing ? (
            <Link className="btn-primary" to="/sessions">
              Back to your sessions
            </Link>
          ) : (
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                void session.refetch()
                void mine.refetch()
              }}
            >
              Try again
            </button>
          )
        }
      >
        {missing ? "It may have been removed, or you haven't joined it." : error.message}
      </StatusMessage>
    )
  }

  return <AvailabilityForm key={session.data!.id} session={session.data!} mine={mine.data!} />
}

type Errors = Partial<Record<'intervals' | 'transportMode' | 'location' | 'general', string>>
type Confirm = 'unavailable' | 'edit' | 'withdraw' | null

function AvailabilityForm({ session, mine }: { session: SessionDetail; mine: MyResponse }) {
  const grid = useMemo(() => buildGrid(session), [session])
  const [params] = useSearchParams()
  const calendarReturn = params.get('calendar')
  const calendarOauthResult =
    calendarReturn === 'connected' ||
    calendarReturn === 'declined' ||
    calendarReturn === 'unavailable' ||
    calendarReturn === 'wrong-account' ||
    calendarReturn === 'missing-scopes'
      ? calendarReturn
      : null

  // Restore selections stashed before a Google Calendar redirect, if we just came back.
  const [draft] = useState(() => (calendarOauthResult ? peekDraft(session.id) : null))
  useEffect(() => clearDraft(session.id), [session.id])

  const record = mine.record
  const [selected, setSelected] = useState<Set<SlotKey>>(() =>
    draft ? new Set(draft.slots) : coveredSlots(grid, record?.intervals.filter((i) => i.type === 'AVAILABLE') ?? []),
  )
  const [busy, setBusy] = useState<Set<SlotKey>>(() => new Set())
  const [calendarAssisted, setCalendarAssisted] = useState(record?.submissionSource === 'CALENDAR_ASSISTED')
  const [transportMode, setTransportMode] = useState<TransportMode | ''>(
    draft?.transportMode || record?.transportMode || '',
  )
  const [picked, setPicked] = useState<PickedLocation | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const save = useSaveResponse(session.id)
  const withdraw = useWithdrawResponse(session.id)

  const closed = session.isClosed
  const isSubmitted = mine.responseStatus === 'SUBMITTED'
  const savedLabel = record?.location.label ?? null
  const deadline = formatDateTime(session.responseDeadline, session.timezone)

  function changeSlots(next: Set<SlotKey>) {
    setSelected(next)
    setNotice(null)
    setErrors((e) => ({ ...e, intervals: undefined }))
    if (confirm === 'unavailable' && next.size > 0) setConfirm(null)
  }

  function handleBusy(intervals: TimeInterval[]) {
    const busyCells = overlappedSlots(grid, intervals)
    setBusy(busyCells)
    // FR-B8 prefill: with nothing marked yet, start from every non-busy cell.
    if (selected.size === 0) {
      const prefill = new Set<SlotKey>()
      grid.dates.forEach((_, d) =>
        grid.rowMinutes.forEach((_, r) => {
          const key = slotKey(d, r)
          if (!busyCells.has(key)) prefill.add(key)
        }),
      )
      changeSlots(prefill)
      setCalendarAssisted(true)
    }
  }

  function validate(): Errors {
    const e: Errors = {}
    const intervals = slotsToIntervals(grid, selected)
    const hasLongEnoughBlock = intervals.some(
      (interval) => new Date(interval.end).getTime() - new Date(interval.start).getTime() >= session.durationMinutes * 60_000,
    )
    if (selected.size > 0 && !hasLongEnoughBlock) {
      e.intervals = `Select at least ${formatDurationMinutes(session.durationMinutes)} continuously so the full activity can fit.`
    }
    if (!transportMode) e.transportMode = 'Choose how you would travel.'
    if (!picked && !savedLabel) e.location = 'Find your home address or postal code and pick a match.'
    return e
  }

  function focusFirst(e: Errors) {
    const target = e.intervals
      ? document.querySelector<HTMLElement>('[data-cell]')
      : e.location
        ? document.getElementById('loc-query')
        : e.transportMode
          ? document.querySelector<HTMLElement>('input[name="avail-transport"]')
          : null
    target?.focus()
  }

  function doSave() {
    save.mutate(
      {
        intervals: slotsToIntervals(grid, selected),
        calendarAssisted,
        transportMode: transportMode as TransportMode,
        // Omitted on an edit when unchanged: the saved location is kept (contract #14).
        location: picked ? { inputType: picked.inputType, input: picked.input, candidateId: picked.candidateId } : undefined,
        confirmUnavailable: selected.size === 0,
      },
      {
        onSuccess: () => {
          setConfirm(null)
          setPicked(null)
          setErrors({})
          setNotice(isSubmitted ? 'Changes saved.' : `Thanks! Your availability is in. You can change it until ${deadline}.`)
          window.scrollTo({ top: 0 })
        },
        onError: (err) => {
          setConfirm(null)
          if (isApiError(err) && err.code === 'VALIDATION_FAILED') {
            const f = err.fields
            const next: Errors = { intervals: f.intervals, transportMode: f.transportMode, location: f.location }
            if (!next.intervals && !next.transportMode && !next.location) next.general = err.message
            setErrors(next)
            focusFirst(next)
          } else if (isApiError(err) && err.code === 'SESSION_CLOSED') {
            setErrors({ general: 'Responses for this session have closed, so your changes weren’t saved.' })
          } else {
            setErrors({ general: err.message })
          }
        },
      },
    )
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const errs = validate()
    setErrors(errs)
    if (Object.keys(errs).length) {
      focusFirst(errs)
      return
    }
    // UC-06.AC.1: confirm they mean "unavailable" before saving an empty grid.
    if (selected.size === 0 && confirm !== 'unavailable') return setConfirm('unavailable')
    // UC-07 step 3: confirm before changing a submitted response.
    if (isSubmitted && selected.size > 0 && confirm !== 'edit') return setConfirm('edit')
    doSave()
  }

  function doWithdraw() {
    withdraw.mutate(undefined, {
      onSuccess: () => {
        setConfirm(null)
        setNotice(`You've withdrawn your response. You can respond again until ${deadline}.`)
        window.scrollTo({ top: 0 })
      },
      onError: (err) => {
        setConfirm(null)
        setErrors({ general: err.message })
      },
    })
  }

  return (
    <form className="avail" onSubmit={handleSubmit} noValidate>
      <header className="avail__head">
        <h2 className="avail__name">{session.name}</h2>
        <p className="avail__meta">
          {session.activityType.name} · organised by {session.myRole === 'ORGANISER' ? 'you' : session.organiserName}
        </p>
        <p className="avail__meta">
          {closed && session.status === 'ACTIVE' ? 'Responses closed' : 'Responses close'} {deadline}
        </p>
        <ResponseBadge mine={mine} timeZone={session.timezone} />
      </header>

      <ClosedBanner session={session} deadline={deadline} />

      {notice && (
        <p className="avail__notice" role="status">
          {notice}
        </p>
      )}

      {!closed && (
        <CalendarImport
          sessionId={session.id}
          returnPath={`/sessions/${session.id}/availability`}
          onBusy={handleBusy}
          beforeRedirect={() => saveDraft(session.id, { slots: [...selected], transportMode })}
          oauthResult={calendarOauthResult}
        />
      )}

      <section className="avail__section">
        <div className="avail__gridhead">
          <h3 className="avail__label" id="avail-grid-label">
            {closed ? 'Your times' : 'Tap or drag to mark when you’re free'}
          </h3>
          {!closed && selected.size > 0 && (
            <button type="button" className="avail__clear" onClick={() => changeSlots(new Set())}>
              Clear
            </button>
          )}
        </div>
        <AvailabilityGrid
          grid={grid}
          selected={selected}
          busy={busy}
          onChange={changeSlots}
          disabled={closed}
          invalid={Boolean(errors.intervals)}
          describedBy={`avail-grid-hint${errors.intervals ? ' avail-grid-error' : ''}`}
        />
        <p className="field__hint" id="avail-grid-hint">
          {selected.size ? `${formatSelectedDuration(selected.size)} selected` : 'No times selected'} · times in{' '}
          {timeZoneLabel(session.timezone)} · needs one continuous {formatDurationMinutes(session.durationMinutes)} block
        </p>
        {errors.intervals && (
          <p className="field__error" id="avail-grid-error">
            {errors.intervals}
          </p>
        )}
      </section>

      <LocationPicker
        picked={picked}
        savedLabel={savedLabel}
        onPick={(loc) => {
          setPicked(loc)
          setNotice(null)
          setErrors((e) => ({ ...e, location: undefined }))
        }}
        error={errors.location}
        disabled={closed}
      />

      {closed ? (
        record && (
          <p className="avail__readonly">
            Travelling by <strong>{TRANSPORT_LABELS[record.transportMode]}</strong>
          </p>
        )
      ) : (
        <ChipGroup
          name="avail-transport"
          legend="Preferred transport"
          options={TRANSPORT_MODES.map((m) => ({ value: m, label: TRANSPORT_LABELS[m] }))}
          value={transportMode}
          onChange={(v) => {
            setTransportMode(v as TransportMode)
            setNotice(null)
            setErrors((e) => ({ ...e, transportMode: undefined }))
          }}
          error={errors.transportMode}
        />
      )}

      {errors.general && (
        <p className="avail__error" role="alert">
          {errors.general}
        </p>
      )}

      {confirm && (
        <InlineConfirm
          text={CONFIRM_COPY[confirm].text}
          confirmLabel={CONFIRM_COPY[confirm].yes}
          cancelLabel={CONFIRM_COPY[confirm].no}
          danger={CONFIRM_COPY[confirm].danger}
          busy={save.isPending || withdraw.isPending}
          onConfirm={confirm === 'withdraw' ? doWithdraw : doSave}
          onCancel={() => setConfirm(null)}
        />
      )}

      {!closed && !confirm && (
        <div className="avail__actions">
          <button type="submit" className="btn-primary" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : isSubmitted ? 'Save changes' : 'Submit availability'}
          </button>
          {isSubmitted && (
            <button type="button" className="avail__withdraw" onClick={() => setConfirm('withdraw')}>
              Withdraw my response
            </button>
          )}
        </div>
      )}
    </form>
  )
}

function ResponseBadge({ mine, timeZone }: { mine: MyResponse; timeZone: string }) {
  if (mine.responseStatus === 'SUBMITTED' && mine.record) {
    return (
      <span className="avail__badge avail__badge--ok">
        Submitted {formatDateTime(mine.record.submittedAt, timeZone)}
      </span>
    )
  }
  if (mine.responseStatus === 'WITHDRAWN') return <span className="avail__badge avail__badge--warn">Withdrawn</span>
  return <span className="avail__badge">Not submitted yet</span>
}

function ClosedBanner({ session, deadline }: { session: SessionDetail; deadline: string }) {
  if (session.status === 'CANCELLED') {
    // FR-A5.1
    return <p className="avail__closed">The organiser cancelled this session. Responses are no longer needed.</p>
  }
  if (session.status === 'CONFIRMED') {
    return (
      <p className="avail__closed">
        This session is confirmed. <Link to={`/sessions/${session.id}/confirmed`}>See the final plan</Link>
      </p>
    )
  }
  if (session.isClosed) {
    // UC-07.EX.1
    return <p className="avail__closed">Responses closed on {deadline}. Your response can no longer be changed.</p>
  }
  return null
}

const CONFIRM_COPY: Record<Exclude<Confirm, null>, { text: string; yes: string; no: string; danger?: boolean }> = {
  unavailable: {
    text: "You haven't marked any times. Submit anyway to tell the organiser you're unavailable?",
    yes: 'Submit as unavailable',
    no: 'Go back',
  },
  edit: {
    text: 'Save changes to your response? The organiser may need to refresh the suggested options.',
    yes: 'Save changes',
    no: 'Cancel',
  },
  withdraw: {
    text: "Withdraw your response? You won't be counted for any time. You can respond again before the deadline.",
    yes: 'Withdraw',
    no: 'Keep my response',
    danger: true,
  },
}
