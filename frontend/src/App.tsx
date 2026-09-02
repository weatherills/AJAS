import './App.css'

const phases = [
  { name: 'Resume Management', desc: 'Upload, parse to schema, edit, set active per run' },
  { name: 'Source Ingestion', desc: 'Scan Greenhouse & Lever for postings' },
  { name: 'AI Matching', desc: 'Hybrid keyword + semantic scoring with reasons' },
  { name: 'Review & Decision', desc: 'Approve / reject with comments and summary' },
  { name: 'Auto-Apply', desc: 'Auto-fill and submit approved applications' },
  { name: 'Email Ingestion & Reply', desc: 'Pull related emails via Microsoft Graph' },
  { name: 'Learning Loop', desc: 'Adjust matching weights from user decisions' },
  { name: 'Settings', desc: 'Threshold, email connection, source toggles' },
]

function App() {
  return (
    <div className="page">
      <header className="header">
        <span className="badge">Skeleton</span>
        <h1>AJAS</h1>
        <p className="tagline">AI Job Application System</p>
      </header>

      <main>
        <p className="intro">
          Project skeleton is in place. Features are implemented phase by phase
          following <code>.codespring/CURSOR_RUNBOOK.md</code>.
        </p>

        <ul className="phases">
          {phases.map((p) => (
            <li key={p.name} className="phase-card">
              <div className="phase-name">{p.name}</div>
              <div className="phase-desc">{p.desc}</div>
              <span className="pill">Planned</span>
            </li>
          ))}
        </ul>
      </main>

      <footer className="footer">Azure Functions · Cosmos DB · Blob &amp; Queue Storage · Azure OpenAI</footer>
    </div>
  )
}

export default App
