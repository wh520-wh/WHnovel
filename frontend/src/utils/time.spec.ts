import { describe, expect, it } from 'vitest'
import { formatTime, formatDateTime, formatTimeSeconds } from './time'

describe('formatTime', () => {
  it('returns HH:MM for valid ISO string', () => {
    expect(formatTime('2026-05-03T14:30:00')).toBe('14:30')
  })

  it('returns empty string for invalid input', () => {
    expect(formatTime('not-a-date')).toBe('')
  })

  it('returns empty string for empty input', () => {
    expect(formatTime('')).toBe('')
  })
})

describe('formatDateTime', () => {
  it('returns full datetime for valid ISO string', () => {
    expect(formatDateTime('2026-05-03T14:30:45')).toBe('2026-05-03 14:30:45')
  })

  it('returns empty string for empty input', () => {
    expect(formatDateTime('')).toBe('')
  })

  it('returns empty string for invalid date', () => {
    expect(formatDateTime('invalid')).toBe('')
  })
})

describe('formatTimeSeconds', () => {
  it('returns HH:MM:SS for valid ISO string', () => {
    expect(formatTimeSeconds('2026-05-03T14:30:45')).toBe('14:30:45')
  })

  it('returns empty string for empty input', () => {
    expect(formatTimeSeconds('')).toBe('')
  })

  it('returns empty string for invalid date', () => {
    expect(formatTimeSeconds('not-a-date')).toBe('')
  })
})
