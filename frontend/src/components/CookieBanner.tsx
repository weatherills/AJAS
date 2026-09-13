import { useState } from 'react'
import { defaultChoices, saveChoices, type CookieChoices } from '../lib/cookieConsent'

export function CookieBanner({ onSave }: { onSave?: (choices: CookieChoices) => void }) {
  const [choices, setChoices] = useState<CookieChoices>(defaultChoices)
  return (
    <aside className="cookie-banner" role="dialog" aria-labelledby="cookie-h">
      <h2 id="cookie-h">Cookies</h2>
      <p>Necessary cookies stay on. Analytics and marketing are optional.</p>
      <label>
        <input
          type="checkbox"
          checked={choices.analytics}
          onChange={(event) => setChoices({ ...choices, analytics: event.target.checked })}
        />
        Analytics
      </label>
      <label>
        <input
          type="checkbox"
          checked={choices.marketing}
          onChange={(event) => setChoices({ ...choices, marketing: event.target.checked })}
        />
        Marketing
      </label>
      <button
        type="button"
        onClick={() => {
          const saved = saveChoices(choices)
          onSave?.(saved)
        }}
      >
        Save cookie choices
      </button>
    </aside>
  )
}
