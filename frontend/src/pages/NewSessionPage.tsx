import { useState, type FormEvent } from 'react'
import { isApiError } from '../api/client'
import { useActivityTypes } from '../api/hooks/activityTypes'
import { useCreateSession } from '../api/hooks/sessions'
import type { CreateSessionResponse } from '../api/types'
import { ChipGroup } from '../components/ChipGroup'
import { FormField } from '../components/FormField'
import { StatusMessage } from '../components/StatusMessage'
import { DEFAULT_TIMEZONE, DURATION_MAX_MINUTES, DURATION_MIN_MINUTES } from '../config'
import { nowLocalDateTime, timeZoneLabel, todayInZone } from '../lib/time'
import { InviteCreated } from '../sessions/InviteCreated'
import {
  EMPTY_FORM,
  FIELD_ORDER,
  pickFieldErrors,
  toCreateRequest,
  validateNewSession,
  type NewSessionErrors,
  type NewSessionField,
  type NewSessionForm,
} from '../sessions/newSessionForm'
import './NewSessionPage.css'

const fieldId = (f: NewSessionField | 'category') => `ns-${f}`

/**
 * New session (SRS §3.1, UC-01, FR-A1 to FR-A4). Anyone signed in can create a
 * Session and becomes its Organiser. On success, shows the invitation link.
 */
export function NewSessionPage() {
  // New sessions use the default timezone; the create request sends it explicitly.
  const timeZone = DEFAULT_TIMEZONE
  const activities = useActivityTypes()
  const create = useCreateSession()

  const [form, setForm] = useState<NewSessionForm>(EMPTY_FORM)
  const [errors, setErrors] = useState<NewSessionErrors>({})
  const [attempted, setAttempted] = useState(false)
  const [created, setCreated] = useState<CreateSessionResponse | null>(null)

  if (created) {
    return (
      <InviteCreated
        result={created}
        onCreateAnother={() => {
          setCreated(null)
          setForm(EMPTY_FORM)
          setErrors({})
          setAttempted(false)
          create.reset()
        }}
      />
    )
  }

  function apply(next: NewSessionForm) {
    setForm(next)
    // After the first submit attempt, errors update as the user fixes them.
    if (attempted) setErrors(validateNewSession(next, timeZone))
  }

  function update<K extends keyof NewSessionForm>(key: K, value: NewSessionForm[K]) {
    apply({ ...form, [key]: value })
  }

  function selectCategory(category: string) {
    const types = activities.data?.find((c) => c.category === category)?.types ?? []
    const keepType = types.some((t) => t.id === form.activityTypeId)
    apply({ ...form, category, activityTypeId: keepType ? form.activityTypeId : '' })
  }

  function focusFirstError(errs: NewSessionErrors) {
    const first = FIELD_ORDER.find((f) => errs[f])
    if (!first) return
    const el =
      first === 'activityTypeId'
        ? document.querySelector<HTMLInputElement>(
            form.category ? `input[name="${fieldId('activityTypeId')}"]` : `input[name="${fieldId('category')}"]`,
          )
        : document.getElementById(fieldId(first))
    el?.focus()
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setAttempted(true)
    const errs = validateNewSession(form, timeZone)
    setErrors(errs)
    if (Object.keys(errs).length) {
      focusFirstError(errs)
      return
    }
    create.mutate(toCreateRequest(form, timeZone), {
      onSuccess: (data) => {
        setCreated(data)
        window.scrollTo({ top: 0 })
      },
      onError: (err) => {
        // UC-01.EX.1: field-level errors from the server, shown inline.
        if (isApiError(err) && err.code === 'VALIDATION_FAILED') {
          const serverErrs = pickFieldErrors(err.fields)
          setErrors(serverErrs)
          focusFirstError(serverErrs)
        }
      },
    })
  }

  const selectedCategory = activities.data?.find((c) => c.category === form.category)
  const generalError =
    create.isError && !(isApiError(create.error) && create.error.code === 'VALIDATION_FAILED')
      ? create.error.message
      : null
  const today = todayInZone(timeZone)

  return (
    <form className="newsession" onSubmit={handleSubmit} noValidate>
      <FormField id={fieldId('name')} label="Session name" error={errors.name}>
        {(control) => (
          <input
            {...control}
            className="input"
            type="text"
            autoComplete="off"
            maxLength={80}
            placeholder="e.g. Weekend badminton"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
          />
        )}
      </FormField>

      {activities.isPending && <StatusMessage busy title="Loading activities…" />}
      {activities.isError && (
        <StatusMessage
          title="Couldn't load activities"
          action={
            <button type="button" className="btn-primary" onClick={() => void activities.refetch()}>
              Try again
            </button>
          }
        />
      )}
      {activities.data && (
        <>
          <ChipGroup
            name={fieldId('category')}
            legend="Activity category"
            options={activities.data.map((c) => ({ value: c.category, label: c.category }))}
            value={form.category}
            onChange={selectCategory}
            error={!form.category ? errors.activityTypeId : undefined}
          />
          {selectedCategory && (
            <ChipGroup
              name={fieldId('activityTypeId')}
              legend="Activity type"
              options={selectedCategory.types.map((t) => ({ value: t.id, label: t.name }))}
              value={form.activityTypeId}
              onChange={(v) => update('activityTypeId', v)}
              error={errors.activityTypeId}
            />
          )}
        </>
      )}

      <div className="newsession__row">
        <FormField id={fieldId('startDate')} label="Starts" error={errors.startDate}>
          {(control) => (
            <input
              {...control}
              className="input"
              type="date"
              min={today}
              value={form.startDate}
              onChange={(e) => update('startDate', e.target.value)}
            />
          )}
        </FormField>
        <FormField id={fieldId('endDate')} label="Ends" error={errors.endDate}>
          {(control) => (
            <input
              {...control}
              className="input"
              type="date"
              min={form.startDate || today}
              value={form.endDate}
              onChange={(e) => update('endDate', e.target.value)}
            />
          )}
        </FormField>
      </div>

      <fieldset className="newsession__group">
        <legend className="chips__legend">Times each day</legend>
        <div className="newsession__row">
          <FormField id={fieldId('dailyStartTime')} label="Earliest start" error={errors.dailyStartTime}>
            {(control) => (
              <input
                {...control}
                className="input"
                type="time"
                step={1800}
                value={form.dailyStartTime}
                onChange={(e) => update('dailyStartTime', e.target.value)}
              />
            )}
          </FormField>
          <FormField id={fieldId('dailyEndTime')} label="Latest end" error={errors.dailyEndTime}>
            {(control) => (
              <input
                {...control}
                className="input"
                type="time"
                step={1800}
                value={form.dailyEndTime}
                onChange={(e) => update('dailyEndTime', e.target.value)}
              />
            )}
          </FormField>
        </div>
        <p className="field__hint">People can only mark times inside this window.</p>
      </fieldset>

      <FormField
        id={fieldId('durationMinutes')}
        label="Duration (minutes)"
        hint={`Between ${DURATION_MIN_MINUTES} and ${DURATION_MAX_MINUTES} minutes`}
        error={errors.durationMinutes}
      >
        {(control) => (
          <input
            {...control}
            className="input"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="90"
            value={form.durationMinutes}
            onChange={(e) => update('durationMinutes', e.target.value)}
          />
        )}
      </FormField>

      <FormField
        id={fieldId('responseDeadline')}
        label="Response deadline"
        hint={`${timeZoneLabel(timeZone)}. Must be before the start date.`}
        error={errors.responseDeadline}
      >
        {(control) => (
          <input
            {...control}
            className="input"
            type="datetime-local"
            min={nowLocalDateTime(timeZone)}
            value={form.responseDeadline}
            onChange={(e) => update('responseDeadline', e.target.value)}
          />
        )}
      </FormField>

      <FormField id={fieldId('minimumAttendees')} label="Minimum attendees needed" error={errors.minimumAttendees}>
        {(control) => (
          <input
            {...control}
            className="input"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="4"
            value={form.minimumAttendees}
            onChange={(e) => update('minimumAttendees', e.target.value)}
          />
        )}
      </FormField>

      {generalError && (
        <p className="newsession__error" role="alert">
          {generalError}
        </p>
      )}

      <button type="submit" className="btn-primary" disabled={create.isPending || !activities.data}>
        {create.isPending ? 'Creating…' : 'Create and get invite link'}
      </button>
    </form>
  )
}
