export function unifiedDiff(previous: string, current: string): { changed: boolean; lines: string[] } {
  const left = (previous || '').split('\n')
  const right = (current || '').split('\n')
  if (left.join('\n') === right.join('\n')) return { changed: false, lines: [] }
  const lines = ['--- previous', '+++ current']
  const max = Math.max(left.length, right.length)
  for (let i = 0; i < max; i += 1) {
    const a = left[i]
    const b = right[i]
    if (a === b) continue
    if (a != null && b != null) {
      lines.push(`- ${a}`)
      lines.push(`+ ${b}`)
    } else if (a != null) lines.push(`- ${a}`)
    else lines.push(`+ ${b}`)
  }
  return { changed: true, lines }
}
