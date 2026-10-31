import { useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import './CopyLinkField.css'

type Props = {
  id: string
  label: string
  /** Access Data (an invitation URL): displayed to its owner, never logged. */
  url: string
  shareTitle?: string
  shareText?: string
  message?: string
  showQr?: boolean
}

/** Read-only link with Copy (and Share, where the device supports it). */
export function CopyLinkField({ id, label, url, shareTitle, shareText, message, showQr = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState('')
  const [qrExpanded, setQrExpanded] = useState(false)
  const canShare = typeof navigator.share === 'function'

  async function copyText(text: string, successMessage: string) {
    try {
      await navigator.clipboard.writeText(text)
      setStatus(successMessage)
    } catch {
      inputRef.current?.select()
      setStatus("Couldn't copy automatically. The link is selected, so copy it manually.")
    }
  }

  async function copy() {
    await copyText(url, 'Link copied')
  }

  async function copyMessage() {
    if (message) await copyText(message, 'Invitation message copied')
  }

  async function share() {
    try {
      await navigator.share({ title: shareTitle, text: shareText, url })
    } catch {
      // Share sheet closed or not allowed. Nothing to do.
    }
  }

  return (
    <div className="copylink">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <div className="copylink__row">
        <input
          ref={inputRef}
          id={id}
          className="input copylink__input"
          type="text"
          readOnly
          value={url}
          onFocus={(e) => e.target.select()}
        />
        <button type="button" className="copylink__copy" onClick={() => void copy()}>
          Copy
        </button>
      </div>
      <p className="copylink__status" role="status" aria-live="polite">
        {status}
      </p>
      <div className="copylink__actions">
        {message && (
          <button type="button" className="copylink__message" onClick={() => void copyMessage()}>
            Copy invitation message
          </button>
        )}
        {canShare && (
          <button type="button" className="copylink__share" onClick={() => void share()}>
            Share link…
          </button>
        )}
        {showQr && (
          <button
            type="button"
            className="copylink__qr-toggle"
            aria-expanded={qrExpanded}
            onClick={() => setQrExpanded((current) => !current)}
          >
            {qrExpanded ? 'Hide QR code' : 'Show QR code'}
          </button>
        )}
      </div>
      {showQr && qrExpanded && (
        <div className="copylink__qr-panel">
          <QRCodeSVG
            className="copylink__qr"
            value={url}
            title="Invitation QR code"
            level="M"
            marginSize={4}
            size={220}
          />
          <p>Show this code so people nearby can scan and join. For online sharing, copy the invitation message.</p>
        </div>
      )}
    </div>
  )
}
