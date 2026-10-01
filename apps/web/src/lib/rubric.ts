import type { Criterion } from './types'

/**
 * Teacher-facing reasons a rubric can't be saved or used for grading (empty = ready).
 * Mirrors scoring.rubric_problems() on the server, which has the final say. Points are never fixed silently.
 */
export function rubricProblems(criteria: Criterion[], total: number | null): string[] {
  if (!criteria.length) return ['The rubric has no criteria yet. Add at least one criterion.']
  const errs: string[] = []
  const names = criteria.map((c) => c.name.trim())
  if (names.some((n) => !n)) errs.push('Every rubric criterion needs a name.')
  const lower = names.filter(Boolean).map((n) => n.toLowerCase())
  const dup = [...new Set(names.filter((n) => n && lower.filter((x) => x === n.toLowerCase()).length > 1))]
  if (dup.length) errs.push(`Criterion names must be different: ${dup.join(', ')}.`)
  criteria.forEach((c) => {
    if (!(Number(c.points) > 0)) errs.push(`"${c.name.trim() || 'Unnamed criterion'}" needs more than 0 points.`)
  })
  const sum = rubricSum(criteria)
  if (total === null || !(total > 0)) errs.push("Enter the rubric's total points.")
  else if (Math.abs(sum - total) > 1e-6) errs.push(`The criteria add up to ${fmt(sum)} points, but the rubric total is ${fmt(total)}. Make them match before grading.`)
  return errs
}

export const rubricSum = (criteria: Criterion[]) => Math.round(criteria.reduce((s, c) => s + (Number(c.points) || 0), 0) * 100) / 100

export const fmt = (n: number) => String(Math.round(n * 100) / 100)
