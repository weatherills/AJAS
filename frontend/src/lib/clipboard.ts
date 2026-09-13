/** Clipboard helpers. Tests assert payload shape; the browser API is optional. */

export function explanationClipboardPayload(match: {
  explanation?: string | null
  highlights?: string[]
  gaps?: string[]
}): string {
  const parts: string[] = []
  if (match.explanation) parts.push(match.explanation)
  if (match.highlights?.length) parts.push(`Skills: ${match.highlights.join(', ')}`)
  if (match.gaps?.length) parts.push(`Gaps: ${match.gaps.join(', ')}`)
  return parts.join('\n')
}

export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through */
  }
  return false
}
