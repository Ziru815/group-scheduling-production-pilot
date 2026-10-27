import { useRef, useState } from 'react'
import './CopyLinkField.css'

type Props = {
  id: string
  label: string
  /** Access Data (an invitation URL): displayed to its owner, never logged. */
  url: string
  shareTitle?: string
  shareText?: string
}

/** Read-only link with Copy (and Share, where the device supports it). */
export function CopyLinkField({ id, label, url, shareTitle, shareText }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState('')
  const canShare = typeof navigator.share === 'function'

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setStatus('Link copied')
    } catch {
      inputRef.current?.select()
      setStatus("Couldn't copy automatically. The link is selected, so copy it manually.")
    }
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
      {canShare && (
        <button type="button" className="copylink__share" onClick={() => void share()}>
          Share link…
        </button>
      )}
    </div>
  )
}
