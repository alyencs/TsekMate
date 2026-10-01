import type { ReactNode } from 'react'
import { Diff, FlaskConical } from 'lucide-react'
import type { Subject } from '../../lib/types'
import { SUBJECTS } from '../../lib/subjects'

export function SubjectIcon({ subject, className = 'h-3.5 w-3.5' }: { subject: Subject; className?: string }) {
  if (subject === 'math') return <Diff className={className} aria-hidden />
  if (subject === 'science') return <FlaskConical className={className} aria-hidden />
  return (
    <span aria-hidden className="font-bold leading-none" style={{ fontSize: '1.05em' }}>
      A
    </span>
  )
}

export function SubjectChip({ subject, size = 'md' }: { subject: Subject; size?: 'sm' | 'md' }) {
  const cls = size === 'sm' ? 'h-6 px-2 text-[11px] gap-1' : 'h-[26px] px-2.5 text-[13px] gap-1.5'
  return (
    <span className={`inline-flex items-center rounded-full bg-soft font-semibold text-[#3B4260] ring-1 ring-inset ring-line ${cls}`}>
      <SubjectIcon subject={subject} className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
      {SUBJECTS[subject].label}
    </span>
  )
}

type Tone = 'ok' | 'bad' | 'warn' | 'brand' | 'accent' | 'neutral'
const tones: Record<Tone, string> = {
  ok: 'bg-ok-bg text-ok-text border-ok-border',
  bad: 'bg-bad-bg text-bad-text border-bad-border',
  warn: 'bg-warn-bg text-warn-text border-warn-border',
  brand: 'bg-brand-light text-brand-dark border-brand-tint',
  accent: 'bg-accent-light text-accent-text border-accent-tint',
  neutral: 'bg-soft text-muted border-line',
}

export function Badge({
  tone,
  children,
  icon,
  shape = 'pill',
  className = '',
}: {
  tone: Tone
  children: ReactNode
  icon?: ReactNode
  shape?: 'pill' | 'tag'
  className?: string
}) {
  return (
    <span
      className={`inline-flex h-6 items-center gap-1 whitespace-nowrap border px-2 text-[11px] font-semibold ${
        shape === 'pill' ? 'rounded-full' : 'rounded'
      } ${tones[tone]} ${className}`}
    >
      {icon}
      {children}
    </span>
  )
}
