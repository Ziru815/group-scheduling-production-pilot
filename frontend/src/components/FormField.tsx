import type { ReactNode } from 'react'
import './FormField.css'

/** Props to spread onto the input so it's labelled and announces its hint/error. */
export interface FieldControlProps {
  id: string
  'aria-invalid': boolean
  'aria-describedby'?: string
}

type Props = {
  id: string
  label: string
  hint?: ReactNode
  /** Shown beneath the field (SRS §3.1: inline, not a modal). */
  error?: string
  children: (control: FieldControlProps) => ReactNode
}

export function FormField({ id, label, hint, error, children }: Props) {
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={error ? 'field field--error' : 'field'}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': describedBy })}
      {hint && (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field__error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}
