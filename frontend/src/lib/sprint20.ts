/** Sprint 20 matching helpers: 0–100 scores with a default threshold of 70. */

export function persistMatch20(score: number, threshold = 70): boolean {
  return score >= threshold
}

export function sprint20Changelog(): { version: string; highlights: string[] }[] {
  return [
    {
      version: '20.0.0',
      highlights: ['GH/Lever ingest + review APIs', 'Match gate 70', 'Graph mail + apply orchestrator'],
    },
  ]
}
