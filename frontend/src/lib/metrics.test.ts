import { describe, expect, it } from 'vitest'
import { chartBars } from './metrics'

describe('metrics charts', () => {
  it('scales bars to the peak series value', () => {
    const bars = chartBars([
      { name: 'Ingestion', value: 10, color: '#38bdf8' },
      { name: 'Matches', value: 5, color: '#34d399' },
    ])
    expect(bars[0].height).toBe(80)
    expect(bars[1].height).toBe(40)
  })
})
