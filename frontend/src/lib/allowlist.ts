export function parseAllowlist(raw: string): string[] {
  return [...new Set(raw.split(/[\s,]+/).map((item) => item.trim().toLowerCase()).filter(Boolean))].sort()
}

export function formatAllowlist(hosts: string[]): string {
  return parseAllowlist(hosts.join(','))
    .join(', ')
}
