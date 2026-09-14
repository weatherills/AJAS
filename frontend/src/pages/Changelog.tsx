import { AppNav } from '../components/AppNav'
import { changelogEntries, labelledBy } from '../lib/sprint12'
import { sprint13Changelog } from '../lib/sprint13'
import { sprint14Changelog } from '../lib/sprint14'
import { sprint15Changelog } from '../lib/sprint15'

export function ChangelogPage() {
  return (
    <div className="page library-page" {...labelledBy('cl-h')}>
      <AppNav />
      <header className="library-header">
        <div>
          <h1 id="cl-h">Changelog</h1>
          <p className="tagline">Releases and highlights.</p>
        </div>
      </header>
      <ol>
        {[...sprint15Changelog(), ...sprint14Changelog(), ...sprint13Changelog(), ...changelogEntries()].map((entry) => (
          <li key={entry.version}>
            <strong>{entry.version}</strong>
            <p>{entry.highlights.join(' · ')}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
