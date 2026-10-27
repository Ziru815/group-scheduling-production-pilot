import './ChipGroup.css'

export interface ChipOption {
  value: string
  label: string
}

type Props = {
  /** Used for the radio group name and element ids. */
  name: string
  legend: string
  options: ChipOption[]
  value: string
  onChange: (value: string) => void
  error?: string
  /** Hide the legend visually (still read by screen readers). */
  hideLegend?: boolean
}

/**
 * Single-choice chip group (SRS §3.1 "selectable chip groups"). Native radio
 * inputs under the hood, so keyboard and screen readers work for free.
 */
export function ChipGroup({ name, legend, options, value, onChange, error, hideLegend }: Props) {
  const errorId = error ? `${name}-error` : undefined
  return (
    <fieldset className="chips" aria-describedby={errorId} aria-invalid={Boolean(error)}>
      <legend className={hideLegend ? 'visually-hidden' : 'chips__legend'}>{legend}</legend>
      <div className="chips__row">
        {options.map((o) => (
          <label key={o.value} className="chip">
            <input
              className="chip__input"
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            <span className="chip__label">{o.label}</span>
          </label>
        ))}
      </div>
      {error && (
        <p className="field__error" id={errorId}>
          {error}
        </p>
      )}
    </fieldset>
  )
}
