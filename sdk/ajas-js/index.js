// @ajas/client — Sprint 12 JS SDK scaffold (fetch wrapper).
export function createClient({ baseUrl = '/api', token } = {}) {
  async function request(path, { method = 'GET', body } = {}) {
    const headers = { Accept: 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const res = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    const json = await res.json()
    if (!res.ok) throw Object.assign(new Error(json?.error?.message || res.statusText), { status: res.status, json })
    return json
  }
  return {
    jobs: {
      list: (cursor, { sort = 'id', limit = 25 } = {}) =>
        request(`/v1/jobs?limit=${limit}&sort=${sort}${cursor ? `&cursor=${cursor}` : ''}`),
    },
    matches: {
      list: (cursor, { sort = 'score', limit = 25 } = {}) =>
        request(`/v1/matches?limit=${limit}&sort=${sort}${cursor ? `&cursor=${cursor}` : ''}`),
    },
    tenants: { create: (name) => request('/v1/tenants', { method: 'POST', body: { name } }) },
  }
}
