import { describe, expect, it } from 'vitest'
import { recordMockDecision, resetMockLearning } from '../api/learningMock'
import { mockMatchingApi } from '../api/matchingMock'
import {
  chipOverflow,
  combineScore,
  displayScore,
  isOutdated,
  keywordOverlap,
  parseThresholdInput,
  scoreBand,
  scoreLabel,
  storedMatchesForJobs,
  truncateExplanation,
} from './matching'

describe('matching display helpers', () => {
  it('maps score ranges to color and label', () => {
    expect(scoreBand(49)).toBe('red')
    expect(scoreLabel(49)).toBe('Poor match')
    expect(scoreBand(50)).toBe('amber')
    expect(scoreLabel(69)).toBe('Fair match')
    expect(scoreBand(70)).toBe('green')
    expect(scoreLabel(82)).toBe('Good match')
    expect(displayScore(81.6)).toBe(82)
    expect(scoreBand(69.6)).toBe('green')
    expect(scoreLabel(69.6)).toBe('Good match')
  })

  it('combines keyword and semantic with 0.4 / 0.6 weights', () => {
    expect(combineScore(100, 0)).toBe(40)
    expect(combineScore(0, 100)).toBe(60)
  })

  it('truncates explanations on a word boundary', () => {
    const text = `${'matched skills python azure cosmos '.repeat(40)}end`
    const result = truncateExplanation(text, 80)
    expect(result.truncated).toBe(true)
    expect(result.text.length).toBeLessThanOrEqual(80)
    expect(result.text.endsWith(' ')).toBe(false)
  })

  it('groups overflowing keyword chips', () => {
    const chips = chipOverflow(['python', 'azure', 'cosmos', 'react', 'node', 'sql', 'kafka'], 6)
    expect(chips.shown).toHaveLength(6)
    expect(chips.extra).toBe(1)
  })

  it('validates threshold integers 0–100', () => {
    expect(parseThresholdInput('70')).toEqual({ value: 70, error: null })
    expect(parseThresholdInput('101').error).toBeTruthy()
    expect(parseThresholdInput('hot').error).toBeTruthy()
  })

  it('flags outdated model versions', () => {
    expect(isOutdated({ algorithm: 'weighted-legacy', embeddingsModel: 'x', prompt: 'p', keywordWeights: 'k', normalization: 'n' })).toBe(
      true,
    )
  })
})

describe('mock matching api', () => {
  it('uses learning weights after mock review decisions', async () => {
    resetMockLearning()
    const job = {
      id: 'staff-learn',
      text: 'Title: Staff Platform Engineer\nCompany: Acme\nSkills: python azure cosmos matching crawlers ingestion kubernetes',
    }
    const before = await mockMatchingApi.scoreOne({
      resumeId: 'seed-ready',
      resumeText: 'Staff Engineer Python Azure Cosmos APIs matching crawlers kubernetes',
      threshold: 70,
      job,
    })
    recordMockDecision('match-staff', 'approve')
    recordMockDecision('match-staff', 'approve')
    const after = await mockMatchingApi.scoreOne({
      resumeId: 'seed-ready',
      resumeText: 'Staff Engineer Python Azure Cosmos APIs matching crawlers kubernetes',
      threshold: 70,
      job: { ...job, id: 'staff-learn-after' },
    })
    expect(before.breakdown?.weights.keyword).toBe(0.4)
    expect(after.breakdown?.weights.keyword).toBeGreaterThan(0.4)
    resetMockLearning()
  })

  it('scores engineer jobs higher than designer jobs', async () => {
    resetMockLearning()
    const resume = 'Staff Engineer Python Azure Cosmos APIs matching crawlers'
    const rows = await mockMatchingApi.scoreMany({
      resumeId: 'seed-ready',
      resumeText: resume,
      threshold: 70,
      jobs: [
        { id: 'eng', text: 'Title: Staff Engineer\nCompany: Acme\nSkills: python azure cosmos matching crawlers ingestion' },
        { id: 'des', text: 'Title: Product Designer\nCompany: Globex\nSkills: figma illustration branding workshop' },
      ],
    })
    const eng = rows.find((item) => item.jobId === 'eng')
    const des = rows.find((item) => item.jobId === 'des')
    expect(eng?.state).toBe('computed')
    expect(des?.state).toBe('computed')
    expect((eng?.score || 0) > (des?.score || 0)).toBe(true)
    expect((eng?.score || 0) >= 70).toBe(true)
    expect(des?.versions?.algorithm).toBe('weighted-legacy')
  })

  it('persists a Save match below the threshold', async () => {
    const row = await mockMatchingApi.scoreOne({
      resumeId: 'seed-ready',
      resumeText: 'python azure cosmos matching crawlers',
      threshold: 70,
      persist: true,
      job: { id: 'des', text: 'Title: Product Designer\nCompany: Globex\nSkills: figma illustration branding workshop' },
    })
    expect(row.state).toBe('computed')
    expect((row.score || 0) < 70).toBe(true)
    expect(row.persisted).toBe(true)
    expect(row.matchId).toBe('match-des')
  })

  it('returns a no-resume state without a resume id', async () => {
    const rows = await mockMatchingApi.scoreMany({
      resumeId: null,
      resumeText: '',
      threshold: 70,
      jobs: [{ id: 'x', text: 'Title: Staff Engineer\nBuild crawlers and matching.' }],
    })
    expect(rows[0].state).toBe('no_resume')
    expect(rows[0].score).toBeNull()
  })

  it('flags short job text as insufficient', async () => {
    const row = await mockMatchingApi.scoreOne({
      resumeId: 'seed-ready',
      resumeText: 'python azure',
      threshold: 70,
      job: { id: 'short', text: 'Hi' },
    })
    expect(row.state).toBe('insufficient')
  })

  it('uses keyword overlap as a 0–100 signal', () => {
    expect(keywordOverlap('python azure', 'python azure cosmos')).toBe(100)
    expect(keywordOverlap('python azure', 'figma branding')).toBe(0)
  })

  it('splits stored match results from jobs that still need ranking', () => {
    const split = storedMatchesForJobs(
      ['a', 'b', 'c'],
      [
        { jobId: 'a', score: 88 },
        { jobId: 'c', score: 41 },
      ],
    )
    expect(split.known.map((row) => row.jobId)).toEqual(['a', 'c'])
    expect(split.missingIds).toEqual(['b'])
  })

  it('lists persisted mock results without ranking again', async () => {
    const row = await mockMatchingApi.scoreOne({
      resumeId: 'seed-ready',
      resumeText: 'python azure cosmos matching crawlers ingestion',
      threshold: 70,
      persist: true,
      job: { id: 'keep', text: 'Title: Staff Engineer\nCompany: Acme\nSkills: python azure cosmos matching crawlers' },
    })
    expect(row.persisted).toBe(true)
    const stored = await mockMatchingApi.listResults({ resumeId: 'seed-ready', jobIds: ['keep', 'other'] })
    expect(stored.map((item) => item.jobId)).toEqual(['keep'])
    expect(stored[0].score).toBe(row.score)
  })
})
