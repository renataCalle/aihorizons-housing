import { Link } from 'react-router'

export function BrandMark() {
  return (
    <Link to="/" className="brand" aria-label="Buildable PGH home">
      <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
        <circle
          cx="16"
          cy="16"
          r="14.5"
          fill="none"
          stroke="var(--cobalt)"
          strokeWidth="1.2"
          strokeDasharray="2.5 2.5"
        />
        <path
          d="M16 5 L18.2 13.8 L27 16 L18.2 18.2 L16 27 L13.8 18.2 L5 16 L13.8 13.8 Z"
          fill="var(--cobalt)"
        />
      </svg>
      <span>Buildable PGH</span>
    </Link>
  )
}
