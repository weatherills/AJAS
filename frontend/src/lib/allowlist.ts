export function parseAllowlist(raw: string): string[] {
  return [...new Set(raw.split(/[\s,]+/).map((item) => item.trim().toLowerCase()).filter(Boolean))].sort()
}

export function formatAllowlist(hosts: string[]): string {
  return parseAllowlist(hosts.join(','))
    .join(', ')
}

export type AllowlistAudit = { actor: string; hosts: string[]; action: string }

export function recordAllowlistAudit(actor: string, raw: string): AllowlistAudit {
  return { actor, hosts: parseAllowlist(raw), action: 'allowlist.update' }
}
