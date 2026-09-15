/** Sprint 18 matching helpers: 0–100 scores with a default threshold of 70. */

export function clampThreshold100(value: number, min = 0, max = 100): number {
  if (Number.isNaN(value)) return 70
  return Math.min(max, Math.max(min, value))
}

export function compositeScore100(keyword: number, semantic: number, keywordWeight = 0.4, semanticWeight = 0.6): number {
  return Number((100 * (keyword * keywordWeight + semantic * semanticWeight)).toFixed(1))
}

export function sprint18Changelog(): { version: string; highlights: string[] }[] {
  return [
    {
      version: '18.0.0',
      highlights: ['GH/Lever ingest wiring', 'Match 0–100 + threshold 70', 'Graph mail + apply skeletons'],
    },
  ]
}
