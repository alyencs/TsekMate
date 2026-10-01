import { Calculator, FlaskConical, Type, type LucideIcon } from 'lucide-react'
import type { Subject } from './types'

export interface SubjectConfig {
  key: Subject
  label: string
  shortLabel: string
  sidebarLabel: string
  icon: LucideIcon
  dot: string
  problemNoun: string // "Problem" | "Item"
  problemsNoun: string
  problemPrefix: string // "P" | "I"
  unitNoun: string // "Step" | "Correction"
  expectedLabel: string
  problemTextLabel: string
  errorTypes: { key: string; label: string; chart: string }[]
}

export const SUBJECTS: Record<Subject, SubjectConfig> = {
  math: {
    key: 'math',
    label: 'Math',
    shortLabel: 'Math',
    sidebarLabel: 'Mathematics',
    icon: Calculator,
    dot: 'bg-subject-math',
    problemNoun: 'Problem',
    problemsNoun: 'problems',
    problemPrefix: 'P',
    unitNoun: 'Step',
    expectedLabel: 'Correct final answer',
    problemTextLabel: 'Problem text',
    errorTypes: [
      { key: 'computational', label: 'Computational', chart: 'Computational' },
      { key: 'conceptual', label: 'Conceptual', chart: 'Conceptual' },
      { key: 'notation', label: 'Notation', chart: 'Notation' },
      { key: 'presentation', label: 'Presentation', chart: 'Presentation' },
    ],
  },
  science: {
    key: 'science',
    label: 'Science',
    shortLabel: 'Science',
    sidebarLabel: 'Science',
    icon: FlaskConical,
    dot: 'bg-subject-science',
    problemNoun: 'Problem',
    problemsNoun: 'problems',
    problemPrefix: 'P',
    unitNoun: 'Step',
    expectedLabel: 'Expected answer',
    problemTextLabel: 'Problem text',
    errorTypes: [
      { key: 'computational', label: 'Computational', chart: 'Computational' },
      { key: 'conceptual', label: 'Conceptual', chart: 'Conceptual' },
      { key: 'units_and_notation', label: 'Units and notation', chart: 'Units and notation' },
      { key: 'presentation', label: 'Presentation', chart: 'Presentation' },
    ],
  },
  grammar: {
    key: 'grammar',
    label: 'English Grammar',
    shortLabel: 'English Grammar',
    sidebarLabel: 'English Grammar',
    icon: Type,
    dot: 'bg-subject-grammar',
    problemNoun: 'Item',
    problemsNoun: 'items',
    problemPrefix: 'I',
    unitNoun: 'Correction',
    expectedLabel: 'Corrected version',
    problemTextLabel: 'Sentence to correct',
    errorTypes: [
      { key: 'grammar_rule', label: 'Grammar rule', chart: 'Grammar rule' },
      { key: 'spelling', label: 'Spelling', chart: 'Spelling' },
      { key: 'punctuation_capitalization', label: 'Punctuation', chart: 'Punctuation' },
      { key: 'word_choice', label: 'Word choice', chart: 'Word choice' },
    ],
  },
}

export const SUBJECT_LIST: Subject[] = ['math', 'science', 'grammar']

export function errorTypeLabel(subject: Subject, key: string | null | undefined): string {
  if (!key) return ''
  return SUBJECTS[subject].errorTypes.find((e) => e.key === key)?.label ?? key.replace(/_/g, ' ')
}

export const FLAG_LABELS: Record<string, string> = {
  unclear_handwriting: 'Unclear handwriting',
  step_mismatch: 'Step mismatch',
  alternate_method: 'Alternate method',
  low_confidence_final_answer: 'Low confidence answer',
  grading_failed: 'Grading failed',
}

export const AI_LABEL = 'AI-assisted draft, reviewed by your teacher'
