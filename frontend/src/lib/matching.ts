export type MatchBand = 'green' | 'amber' | 'red'

export function scoreBand(score: number): MatchBand {
  if (score >= 70) return 'green'
  if (score >= 50) return 'amber'
  return 'red'
}
