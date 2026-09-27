import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router'
import { BAND_LABEL } from '../lib/labels'
import { formatSqft } from '../lib/format'
import type { LookupMatch } from '../models/search'
import { detect, isStreetStart, shouldLookUp } from './detect'
import { formatCountyId, splitMatch } from './highlight'
import { useLookup } from './useLookup'

const DETECTED_LABEL = {
  parcel_id: 'Detected: parcel ID',
  address: 'Detected: address',
  description: 'AI search',
  empty: '',
} as const

type Option = { type: 'parcel'; match: LookupMatch } | { type: 'ai' }

interface Props {
  /** `hero`: the big box on the landing page. `bar`: the compact box in the map's top bar. */
  variant: 'hero' | 'bar'
  initialText?: string
  /** Focus the box and open its suggestions on mount (after picking an example). */
  autoOpen?: boolean
}

/** One search box for parcel IDs, addresses and plain-language descriptions (docs/01, §2). */
export function Omnibox({ variant, initialText = '', autoOpen = false }: Props) {
  const navigate = useNavigate()
  const listId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState(initialText)
  const [open, setOpen] = useState(autoOpen)
  const [active, setActive] = useState(-1)
  // The query Enter was pressed on before its lookup answered.
  const pendingEnter = useRef<string | null>(null)

  const detection = useMemo(() => detect(text), [text])
  const lookup = useLookup(text, detection)
  const query = text.trim()
  const lookable = shouldLookUp(text, detection)
  // Only results for exactly what's in the box count; older answers are ignored.
  const current = lookup.status === 'ready' && lookup.query === query
  const settled = !lookable || current || lookup.status === 'error'
  const matches = current ? lookup.matches : []

  const options: Option[] = query
    ? [...matches.map((match) => ({ type: 'parcel' as const, match })), { type: 'ai' }]
    : []
  const showList = open && options.length > 0
  // A partial street name only suggests lots: Enter still searches ("Hazelwood").
  const suggestOnly = isStreetStart(query)
  const fallback = suggestOnly ? options[options.length - 1] : options[0]

  function choose(option: Option | undefined) {
    if (!option) return
    setOpen(false)
    if (option.type === 'parcel') navigate(`/parcel/${option.match.parcel.id}`)
    else navigate(`/search?q=${encodeURIComponent(query)}`)
  }

  // Enter pressed before the lookup answered: act as soon as it does.
  useEffect(() => {
    if (pendingEnter.current === query && settled) {
      pendingEnter.current = null
      choose(fallback)
    }
    // `options`, `fallback` and `choose` follow from `query` and `settled`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, settled])

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      if (!options.length) return
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (i + step + options.length) % options.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Enter opens the highlighted row, else the best parcel match, else AI search.
      if (options[active]) choose(options[active])
      else if (!settled) pendingEnter.current = query
      else choose(fallback)
    } else if (e.key === 'Escape') {
      if (showList) setOpen(false)
      else setText('')
      setActive(-1)
    }
  }

  function fill(value: string) {
    setText(value)
    setOpen(true)
    setActive(-1)
    inputRef.current?.focus()
  }

  const optionId = (i: number) => `${listId}-option-${i}`
  const HEADINGS = { county_id: 'Parcel', block_lot: 'Block-lot', address: 'Address' } as const
  const heading = matches[0] ? HEADINGS[matches[0].matchedOn] : ''

  return (
    <div className={`omnibox-root omnibox-${variant}${showList ? ' is-open' : ''}`}>
      <div className="omnibox omnibox-field">
        <svg className="omnibox-icon" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4-4" />
        </svg>
        <input
          ref={inputRef}
          autoFocus={autoOpen}
          className={detection.kind === 'parcel_id' ? 'omnibox-input is-id' : 'omnibox-input'}
          type="text"
          role="combobox"
          aria-label="Search by parcel ID, address, or what you want to build"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          placeholder="Parcel ID, address, or what you want to build"
          autoComplete="off"
          spellCheck={false}
          value={text}
          onChange={(e) => fill(e.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {detection.kind !== 'empty' && (
          <span className="omnibox-detected" aria-live="polite">
            {matches[0]?.matchedOn === 'address' && !suggestOnly
              ? DETECTED_LABEL.address
              : DETECTED_LABEL[detection.kind]}
          </span>
        )}
        {text && (
          <button
            type="button"
            className="omnibox-clear"
            aria-label="Clear search"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => fill('')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        )}
        {variant === 'hero' && (
          <button
            type="button"
            className="omnibox-go"
            aria-label="Search"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => choose(options[active] ?? fallback)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        )}
      </div>

      <div className="omnibox-panel" hidden={!showList}>
        <ul id={listId} role="listbox" aria-label="Search suggestions" className="omnibox-list">
          {matches.length > 0 && (
            <li role="presentation" className="omnibox-heading">
              {heading} · {matches.length} {matches.length === 1 ? 'match' : 'matches'}
            </li>
          )}
          {/* Only for text that is clearly an ID or address, not a description. */}
          {(detection.kind === 'parcel_id' || detection.kind === 'address') &&
            current &&
            matches.length === 0 && (
              <li role="presentation" className="omnibox-empty">
                No parcels match “{query}”.
              </li>
            )}
          {options.map((option, i) =>
            option.type === 'parcel' ? (
              <ParcelRow
                key={option.match.parcel.id}
                id={optionId(i)}
                match={option.match}
                query={query}
                active={i === active}
                onHover={() => setActive(i)}
                onChoose={() => choose(option)}
              />
            ) : (
              <li key="ai" role="presentation">
                {matches.length > 0 && <div className="omnibox-heading">Or</div>}
                <div
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  className={i === active ? 'omnibox-ai is-active' : 'omnibox-ai'}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(option)}
                >
                  <span className="omnibox-ai-icon" aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24">
                      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
                    </svg>
                  </span>
                  <span>Search with AI for “{query}”</span>
                </div>
              </li>
            ),
          )}
        </ul>
        <div className="omnibox-hints" aria-hidden="true">
          <span>↵ {matches.length > 0 && !suggestOnly ? 'Open report' : 'Search'}</span>
          <span>↑↓ Move</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  )
}

interface RowProps {
  id: string
  match: LookupMatch
  query: string
  active: boolean
  onHover: () => void
  onChoose: () => void
}

function ParcelRow({ id, match, query, active, onHover, onChoose }: RowProps) {
  const p = match.parcel
  // Real parcels are named by their address: show it once, in the name's casing.
  const nameIsAddress = !!p.address && p.address.toLowerCase() === p.name.toLowerCase()
  const primary =
    match.matchedOn === 'address'
      ? nameIsAddress
        ? p.name
        : (p.address ?? p.name)
      : match.matchedOn === 'block_lot'
        ? (p.blockLot ?? p.id)
        : formatCountyId(p.id)
  const [hit, rest] = splitMatch(primary, query)
  const meta = [
    p.zoning.join(', '),
    formatSqft(p.lotAreaSqft).replace('sq ft', 'SF'),
    p.currentUse,
  ].filter(Boolean)

  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      className={active ? 'omnibox-row is-active' : 'omnibox-row'}
      onMouseDown={(e) => e.preventDefault()}
      onMouseEnter={onHover}
      onClick={onChoose}
    >
      <span className="omnibox-row-icon" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24">
          <rect x="5" y="4" width="14" height="16" rx="1" />
          <path d="M5 10h14" />
        </svg>
      </span>
      <span className="omnibox-row-main">
        <span className={match.matchedOn === 'address' ? 'omnibox-row-title' : 'omnibox-row-id'}>
          <mark>{hit}</mark>
          {rest}
        </span>
        <span className="omnibox-row-name">
          {match.matchedOn === 'address' && !nameIsAddress
            ? p.name
            : match.matchedOn === 'address'
              ? (p.neighborhood ?? p.municipality)
              : [p.name, p.neighborhood].filter(Boolean).join(' · ')}
          <span className="omnibox-row-meta">{meta.join(' · ')}</span>
        </span>
      </span>
      <span className={`omnibox-row-score band-${p.band ?? 'none'}`}>
        {p.band ? (
          <>
            <span className="omnibox-row-points">{p.score ?? '—'}</span>
            <span className="omnibox-row-band">{BAND_LABEL[p.band]}</span>
          </>
        ) : (
          <span className="omnibox-row-band">Not a candidate</span>
        )}
      </span>
      {active && (
        <span className="omnibox-row-enter" aria-hidden="true">
          ↵
        </span>
      )}
    </li>
  )
}
