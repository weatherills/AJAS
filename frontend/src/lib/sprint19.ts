/** Sprint 19 matching helpers: 0–100 ensemble with a default threshold of 70. */

export function persistMatch(score: number, threshold = 70): boolean {
  return score >= threshold
}

export function sprint19Changelog(): { version: string; highlights: string[] }[] {
  return [
    {
      version: '19.0.0',
      highlights: ['GH/Lever adapters', 'Match ensemble + gate 70', 'Graph sync + apply submit'],
    },
  ]
}
