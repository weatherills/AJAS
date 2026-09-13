import { useState } from 'react'
import { AppNav } from '../components/AppNav'
import { labelledBy } from '../lib/sprint12'

export function AdminPage() {
  const [tenant] = useState('Acme Labs')
  return (
    <div className="page library-page" {...labelledBy('admin-h')}>
      <AppNav />
      <header className="library-header">
        <div>
          <h1 id="admin-h">Admin</h1>
          <p className="tagline">Tenant usage, adapters, and golden signals.</p>
        </div>
      </header>
      <section className="editor-section">
        <h2>Tenant</h2>
        <p>{tenant} · Free plan · 1 workspace</p>
        <dl className="metrics-grid">
          <div>
            <dt>Ingest</dt>
            <dd>12 / 200</dd>
          </div>
          <div>
            <dt>Match</dt>
            <dd>40 / 500</dd>
          </div>
          <div>
            <dt>Apply</dt>
            <dd>2 / 10</dd>
          </div>
        </dl>
      </section>
      <section className="editor-section">
        <h2>Golden signals</h2>
        <p>Latency 42ms · Traffic 12 rpm · Errors 0 · Saturation 18%</p>
      </section>
    </div>
  )
}
