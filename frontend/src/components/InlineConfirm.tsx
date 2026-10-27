import './InlineConfirm.css'

type Props = {
  text: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
  busyLabel?: string
  danger?: boolean
}

/** Inline "are you sure?" panel (SRS §3.1 avoids modal dialogs). */
export function InlineConfirm({ text, confirmLabel, cancelLabel, onConfirm, onCancel, busy, busyLabel, danger }: Props) {
  return (
    <div className="iconfirm" role="alertdialog" aria-label={text}>
      <p>{text}</p>
      <div className="iconfirm__actions">
        <button
          type="button"
          className={danger ? 'iconfirm__danger' : 'btn-primary'}
          onClick={onConfirm}
          disabled={busy}
          autoFocus
        >
          {busy ? (busyLabel ?? 'Saving…') : confirmLabel}
        </button>
        <button type="button" className="iconfirm__cancel" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </button>
      </div>
    </div>
  )
}
