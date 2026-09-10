import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE = __ENV.AJAS_BASE_URL || 'http://127.0.0.1:7071'
const TOKEN = __ENV.AJAS_TOKEN || 'local-user'

export const options = {
  vus: 5,
  duration: '15s',
  thresholds: {
    http_req_duration: ['p(95)<2500'],
    http_req_failed: ['rate<0.05'],
  },
}

export default function () {
  const headers = { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' }
  const rank = http.post(
    `${BASE}/api/v1/matches/rank`,
    JSON.stringify({
      resumeText: 'python azure kubernetes',
      jobs: [{ jobId: 'job-1', jobText: 'title: Engineer\nskills: python azure' }],
    }),
    { headers },
  )
  check(rank, { 'rank 2xx': (r) => r.status === 200 || r.status === 202 })
  const list = http.get(`${BASE}/api/v1/match-results?limit=25`, { headers })
  check(list, { 'list 2xx': (r) => r.status === 200 })
  sleep(0.3)
}
