export type MetricSeries = { name: string; value: number; color: string }

export function chartBars(series: MetricSeries[], maxHeight = 80): Array<MetricSeries & { height: number }> {
  const peak = Math.max(1, ...series.map((item) => item.value))
  return series.map((item) => ({ ...item, height: Math.round((item.value / peak) * maxHeight) }))
}
