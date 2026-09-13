import { useMemo, useState } from 'react'
import { AppNav } from '../components/AppNav'
import { labelledBy, searchHelp } from '../lib/sprint12'

const DOCS = [
  { id: 'connect-email', title: 'Connect Microsoft 365', body: 'Settings → Email → Connect.' },
  { id: 'threshold', title: 'Match threshold', body: 'Jobs at or above the slider land in Review.' },
  { id: 'share', title: 'Share a match', body: 'Pro and Team plans can mint expiring links.' },
]

export function HelpPage() {
  const [q, setQ] = useState('')
  const items = useMemo(() => searchHelp(DOCS, q), [q])
  return (
    <div className="page library-page" {...labelledBy('help-h')}>
      <AppNav />
      <header className="library-header">
        <div>
          <h1 id="help-h">Help</h1>
          <p className="tagline">In-app knowledge base.</p>
        </div>
      </header>
      <label>
        Search docs
        <input value={q} onChange={(event) => setQ(event.target.value)} />
      </label>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
