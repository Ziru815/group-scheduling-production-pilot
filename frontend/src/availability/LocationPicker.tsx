import { useState, type KeyboardEvent } from 'react'
import { isApiError } from '../api/client'
import { useLocationSearch } from '../api/hooks/myResponse'
import type { LocationCandidate, LocationInputType } from '../api/types'
import './LocationPicker.css'

/** A match the participant picked from the search results. */
export interface PickedLocation {
  inputType: LocationInputType
  input: string
  candidateId: string
  label: string
}

type Props = {
  /** Newly picked location this session, if any. */
  picked: PickedLocation | null
  /** Label of the location already saved on the response (edit mode). */
  savedLabel: string | null
  onPick: (location: PickedLocation | null) => void
  error?: string
  disabled?: boolean
}

const ID = 'loc-query'

/**
 * Starting location (UC-08, FR-B2, FR-B3, FR-B3.1). The backend geocodes via
 * OneMap and returns matches to pick from. The address is private: only ever
 * shown back to its owner (NFR-13), and sent in a POST body, never a URL.
 */
export function LocationPicker({ picked, savedLabel, onPick, error, disabled }: Props) {
  const search = useLocationSearch()
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(!picked && !savedLabel)

  const current = picked?.label ?? savedLabel
  const result = search.data
  const noMatches = result?.status === 'RECEIVED' && result.candidates.length === 0
  const unavailable = result && result.status !== 'RECEIVED'
  const queryError = isApiError(search.error) ? search.error.fieldError('query') : undefined

  function runSearch() {
    const q = query.trim()
    if (!q) return
    search.mutate({ query: q })
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    // Enter searches instead of submitting the whole form.
    if (e.key === 'Enter') {
      e.preventDefault()
      runSearch()
    }
  }

  function choose(c: LocationCandidate) {
    onPick({ inputType: result!.inputType, input: query.trim(), candidateId: c.candidateId, label: c.label })
    setEditing(false)
    search.reset()
  }

  const hintId = `${ID}-hint`
  const errorId = `${ID}-error`
  const shownError = error ?? queryError

  if (!editing && current) {
    return (
      <div className="loc">
        <span className="field__label">Starting location</span>
        <div className="loc__chosen">
          <span className="loc__tick" aria-hidden="true">✓</span>
          <span className="loc__label">{current}</span>
          {!disabled && (
            <button type="button" className="loc__change" onClick={() => setEditing(true)}>
              Change
            </button>
          )}
        </div>
        <p className="field__hint">Only used to estimate travel time. Never shown to anyone else.</p>
      </div>
    )
  }

  return (
    <div className="loc">
      <label className="field__label" htmlFor={ID}>
        Starting location
      </label>
      <div className="loc__row">
        <input
          id={ID}
          className="input"
          type="text"
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Home address or postal code"
          value={query}
          disabled={disabled}
          aria-invalid={Boolean(shownError || noMatches)}
          aria-describedby={[hintId, shownError || noMatches || unavailable ? errorId : ''].filter(Boolean).join(' ')}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          className="loc__find"
          onClick={runSearch}
          disabled={disabled || search.isPending || !query.trim()}
        >
          {search.isPending ? 'Finding…' : 'Find'}
        </button>
      </div>
      <p className="field__hint" id={hintId}>
        Only used to estimate travel time. Never shown to anyone else.
      </p>

      {noMatches && (
        <p className="field__error" id={errorId}>
          We couldn't find that address. Check it, or try your postal code.
        </p>
      )}
      {unavailable && (
        <div className="loc__unavailable" id={errorId} role="alert">
          <span>Address lookup is unavailable right now.</span>
          <button type="button" className="loc__retry" onClick={runSearch}>
            Try again
          </button>
        </div>
      )}
      {search.isError && !queryError && (
        <p className="field__error" id={errorId}>
          {search.error.message}
        </p>
      )}
      {shownError && !noMatches && (
        <p className="field__error" id={errorId}>
          {shownError}
        </p>
      )}

      {result && result.candidates.length > 0 && (
        <fieldset className="loc__results">
          <legend className="loc__results-legend">Pick your address</legend>
          {result.candidates.map((c) => (
            <button key={c.candidateId} type="button" className="loc__option" onClick={() => choose(c)}>
              {c.label}
            </button>
          ))}
        </fieldset>
      )}

      {current && (
        <button
          type="button"
          className="loc__cancel"
          onClick={() => {
            setEditing(false)
            search.reset()
          }}
        >
          Keep {picked ? 'the address I picked' : 'my saved address'}
        </button>
      )}
    </div>
  )
}
