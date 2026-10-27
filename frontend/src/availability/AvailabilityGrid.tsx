import { Fragment, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { rectangle, rowLabel, slotKey, type GridModel, type SlotKey } from './slots'
import './AvailabilityGrid.css'

type Props = {
  grid: GridModel
  /** Cells the participant marked as available. */
  selected: Set<SlotKey>
  /** Cells overlapping Google Calendar busy blocks (display only). */
  busy: Set<SlotKey>
  onChange: (next: Set<SlotKey>) => void
  disabled?: boolean
  invalid?: boolean
  describedBy?: string
}

type Cell = [day: number, row: number]
type Drag = { anchor: Cell; current: Cell; mode: 'add' | 'remove' }

const weekday = new Intl.DateTimeFormat('en-SG', { weekday: 'short', timeZone: 'UTC' })
const dayMonth = new Intl.DateTimeFormat('en-SG', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const dateAt = (isoDate: string) => new Date(`${isoDate}T12:00:00Z`)

function applyDrag(selected: Set<SlotKey>, drag: Drag): Set<SlotKey> {
  const next = new Set(selected)
  for (const key of rectangle(drag.anchor, drag.current)) {
    if (drag.mode === 'add') next.add(key)
    else next.delete(key)
  }
  return next
}

/**
 * Date-range availability grid (SRS §3.1, FR-B1), When2Meet-style: press on a
 * cell and drag to paint a rectangle. Starting on an empty cell adds, starting
 * on a marked one erases. Keyboard: arrow keys move, Space/Enter toggles.
 *
 * Touch: the cells take over touch gestures (touch-action: none) so dragging
 * paints instead of scrolling; the time labels and date headers still scroll.
 */
export function AvailabilityGrid({ grid, selected, busy, onChange, disabled, invalid, describedBy }: Props) {
  const tableRef = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const [focusCell, setFocusCell] = useState<Cell>([0, 0])

  const shown = useMemo(() => (drag ? applyDrag(selected, drag) : selected), [selected, drag])

  function cellFrom(el: Element | null): Cell | null {
    const cell = el?.closest<HTMLElement>('[data-cell]')
    if (!cell || !tableRef.current?.contains(cell)) return null
    return [Number(cell.dataset.day), Number(cell.dataset.row)]
  }

  function handlePointerDown(e: PointerEvent<HTMLDivElement>) {
    if (disabled || e.button !== 0) return
    const cell = cellFrom(e.target as Element)
    if (!cell) return
    e.preventDefault()
    // Keep receiving moves even when the finger leaves the starting cell.
    tableRef.current?.setPointerCapture(e.pointerId)
    setFocusCell(cell)
    setDrag({ anchor: cell, current: cell, mode: selected.has(slotKey(...cell)) ? 'remove' : 'add' })
  }

  function handlePointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!drag) return
    const cell = cellFrom(document.elementFromPoint(e.clientX, e.clientY))
    if (cell && (cell[0] !== drag.current[0] || cell[1] !== drag.current[1])) setDrag({ ...drag, current: cell })
  }

  function handlePointerUp() {
    if (!drag) return
    onChange(applyDrag(selected, drag))
    setDrag(null)
  }

  /** Keyboard activation only (pointer input is handled above; it has detail > 0). */
  function handleCellClick(e: MouseEvent<HTMLButtonElement>, cell: Cell) {
    if (disabled || e.detail !== 0) return
    const key = slotKey(...cell)
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onChange(next)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, Cell> = {
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
    }
    const delta = moves[e.key]
    if (!delta) return
    e.preventDefault()
    const next: Cell = [
      Math.max(0, Math.min(grid.dates.length - 1, focusCell[0] + delta[0])),
      Math.max(0, Math.min(grid.rowMinutes.length - 1, focusCell[1] + delta[1])),
    ]
    setFocusCell(next)
    tableRef.current
      ?.querySelector<HTMLButtonElement>(`[data-day="${next[0]}"][data-row="${next[1]}"]`)
      ?.focus()
  }

  return (
    <div
      className={invalid ? 'agrid agrid--invalid' : 'agrid'}
      role="group"
      aria-label="Availability grid"
      aria-describedby={describedBy}
    >
      <div className="agrid__scroller">
        <div
          ref={tableRef}
          className={disabled ? 'agrid__table agrid__table--disabled' : 'agrid__table'}
          style={{ gridTemplateColumns: `var(--agrid-label-w) repeat(${grid.dates.length}, minmax(var(--agrid-col-min), 1fr))` }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => setDrag(null)}
          onKeyDown={handleKeyDown}
        >
          <div className="agrid__corner" />
          {grid.dates.map((date) => (
            <div key={date} className="agrid__day">
              <span className="agrid__weekday">{weekday.format(dateAt(date))}</span>
              <span className="agrid__date">{dayMonth.format(dateAt(date))}</span>
            </div>
          ))}

          {grid.rowMinutes.map((minutes, r) => {
            const onHour = minutes % 60 === 0
            return (
              <Fragment key={minutes}>
                <div className={onHour ? 'agrid__time' : 'agrid__time agrid__time--half'} aria-hidden="true">
                  {onHour ? rowLabel(minutes) : ''}
                </div>
                {grid.dates.map((date, d) => {
                  const key = slotKey(d, r)
                  const on = shown.has(key)
                  const isBusy = busy.has(key)
                  const isFocus = focusCell[0] === d && focusCell[1] === r
                  let cls = 'agrid__cell'
                  if (onHour) cls += ' agrid__cell--hour'
                  if (on) cls += ' agrid__cell--on'
                  if (isBusy) cls += ' agrid__cell--busy'
                  return (
                    <button
                      key={key}
                      type="button"
                      className={cls}
                      data-cell=""
                      data-day={d}
                      data-row={r}
                      tabIndex={isFocus ? 0 : -1}
                      aria-pressed={on}
                      aria-label={`${weekday.format(dateAt(date))} ${dayMonth.format(dateAt(date))}, ${rowLabel(minutes)}${isBusy ? ', busy in your calendar' : ''}`}
                      aria-disabled={disabled || undefined}
                      onClick={(e) => handleCellClick(e, [d, r])}
                      onFocus={() => setFocusCell([d, r])}
                    />
                  )
                })}
              </Fragment>
            )
          })}
        </div>
      </div>

      <div className="agrid__legend" aria-hidden="true">
        <span className="agrid__swatch agrid__swatch--on" /> Available
        <span className="agrid__swatch agrid__swatch--busy" /> Busy (Google Calendar)
      </div>
    </div>
  )
}

