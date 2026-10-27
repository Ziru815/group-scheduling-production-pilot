import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
      <p>This page doesn't exist.</p>
      <Link to="/sessions">Back to your sessions</Link>
    </div>
  )
}
