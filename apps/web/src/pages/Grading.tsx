import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { BellRing, CircleCheck, CircleX, Clock, Hourglass, Loader2, Sparkles, UserRoundCheck } from 'lucide-react'
import { LogoMark } from '../components/ui/Logo'
import { api } from '../lib/api'
import { clockTime, duration } from '../lib/format'
import type { GradingProgress, SaverStatus } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { AppShell } from '../components/layout/AppShell'
import { ErrorState } from '../components/ui/States'
import { Button } from '../components/ui/Button'

export default function Grading() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const returnTo = params.get('return') // Grade again: go back to that paper when done
  const activity = useAsync(() => api.activity(id), [id])
  const [prog, setProg] = useState<GradingProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number>()
  const saverRef = useRef(false)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const p = await api.gradingProgress(id)
        if (!alive) return
        setProg(p)
        saverRef.current = !!p.saver
        setError(null)
        if (!p.running && p.total > 0 && p.done >= p.total) {
          timer.current = window.setTimeout(() => navigate(returnTo ? `/submissions/${returnTo}` : `/queue?activity=${id}`), 1400)
          return
        }
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
      // Saver results arrive in one go after minutes to hours, so there is no need to ask every second.
      if (alive) timer.current = window.setTimeout(tick, saverRef.current ? 15000 : 1200)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer.current)
    }
  }, [id, navigate, returnTo])

  const total = prog?.total ?? 0
  const done = prog?.done ?? 0
  const pct = total ? Math.round((done / total) * 100) : 0
  const items = prog?.items ?? []
  const cur = Math.max(0, items.findIndex((i) => i.state === 'checking' || i.state === 'waiting'))
  const start = Math.max(0, Math.min(cur - 2, items.length - 5))
  const windowed = items.slice(start, start + 5)
  const short = (activity.data?.title ?? '').split(':')[0].replace(/^Solving /, '')
  const failed = items.filter((i) => i.state === 'failed').length
  const saver = prog?.saver ?? null

  return (
    <AppShell active="queue" contentClassName="flex items-start justify-center px-4 py-8 sm:px-8 sm:py-16 lg:py-24">
      {error && !prog ? (
        <ErrorState message={error} />
      ) : (
        <section className="relative w-full max-w-[600px] overflow-hidden rounded-2xl border border-line bg-white px-5 pb-8 pt-12 text-center shadow-pop sm:px-10 sm:pb-10 sm:pt-16">
          <Sparkles className="absolute right-5 top-4 h-10 w-10 text-accent/30" aria-hidden />
          <span className="relative mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-brand-light" aria-hidden>
            {prog?.running && <span className="absolute inset-0 animate-spin rounded-full border-[3px] border-transparent border-t-brand" />}
            <LogoMark size={40} />
          </span>
          <h1 className="mt-6 text-[20px] font-bold sm:text-[24px]">
            {total === 0 ? 'Nothing to check' : returnTo ? 'Grading this paper again' : `TsekMate is checking ${total} paper${total === 1 ? '' : 's'}`}
          </h1>
          <p className="mt-2 text-[14px] text-muted sm:text-[15px]">TsekMate is checking every step of the students&apos; work against your rubric.</p>
          {saver && <SaverNotice saver={saver} />}

          <div className="mt-8 flex items-center justify-between text-[14px] sm:mt-10 sm:text-[15px]">
            <span className="font-semibold" aria-live="polite" aria-atomic="true">
              {done} of {total} done
            </span>
            <span className="font-semibold text-brand">{pct}%</span>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-[#E9EDF5]" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Grading progress">
            <div className="h-full rounded-full bg-gradient-to-r from-brand to-sky transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>

          {windowed.length > 0 && (
            <ul className="mt-8 overflow-hidden rounded-card border border-line text-left sm:mt-10">
              {windowed.map((i) => (
                <li key={i.submission_id} className={`animate-fade flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-3 sm:px-6 sm:py-4 transition-colors last:border-0 ${i.state === 'checking' ? 'bg-rowhover' : i.state === 'waiting' ? 'text-[#8790A6]' : ''}`}>
                  <span className="min-w-0 flex-1 truncate text-[14px] sm:text-[15px]">{i.student_name ?? (i.state === 'done' || i.state === 'failed' ? 'Student not identified' : 'Reading name…')}</span>
                  <span className="text-[13px] tabular-nums text-muted">{i.student_id ?? short}</span>
                  {i.state === 'done' && (
                    <span className="flex items-center gap-1.5 text-[14px] font-semibold text-ok-text">
                      <CircleCheck className="h-4 w-4 fill-ok-bar text-white" aria-hidden /> Done
                    </span>
                  )}
                  {i.state === 'checking' && (
                    <span className="flex items-center gap-1.5 text-[14px] font-semibold text-brand">
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Checking...
                    </span>
                  )}
                  {i.state === 'waiting' && (
                    <span className="flex items-center gap-1.5 text-[14px] font-semibold">
                      <Hourglass className="h-4 w-4" aria-hidden /> Waiting
                    </span>
                  )}
                  {i.state === 'failed' && (
                    <span className="flex items-center gap-1.5 text-[14px] font-semibold text-bad-text">
                      <CircleX className="h-4 w-4" aria-hidden /> Needs teacher
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {failed > 0 && (
            <p className="mt-4 text-[13px] text-bad-text" role="status">
              {failed} paper{failed === 1 ? '' : 's'} could not be graded automatically. Open {failed === 1 ? 'it' : 'them'} from the queue and press Grade again, or grade by hand.
            </p>
          )}
          {total === 0 && prog && (
            <Button className="mt-8" onClick={() => navigate(`/queue?activity=${id}`)}>
              Go to the review queue
            </Button>
          )}
          <p className="mt-8 flex items-center justify-center gap-1.5 text-[13px] font-medium text-navy sm:mt-10">
            <UserRoundCheck className="h-4 w-4 text-accent" aria-hidden /> You review and approve every result before anything is final.
          </p>
        </section>
      )}
    </AppShell>
  )
}

function SaverNotice({ saver }: { saver: SaverStatus }) {
  const when =
    saver.eta_seconds !== null
      ? `About ${duration(saver.eta_seconds)} left`
      : `Taking longer than usual. Results will be ready by ${clockTime(saver.deadline)} at the latest`
  const basis =
    saver.eta_basis === 'progress'
      ? 'Estimated from the papers graded so far.'
      : saver.eta_basis === 'history'
        ? 'Estimated from how long your earlier Saver grading took.'
        : 'Saver grading usually finishes within an hour (at most 24 hours).'
  return (
    <div className="animate-fade mt-6 rounded-card border border-brand-100 bg-brand-light px-4 py-4 text-left sm:px-5" role="status" aria-live="polite">
      <p className="flex items-start gap-2 text-[14px] font-semibold text-navy sm:text-[15px]">
        <Clock className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden /> {when}
      </p>
      <p className="mt-1 text-[13px] text-muted">
        Saver mode (half price). Sent at {clockTime(saver.submitted_at)}. {basis}
      </p>
      <p className="mt-2 flex items-start gap-2 text-[13px] text-muted">
        <BellRing className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden /> You can close this page. You&apos;ll get a notification when the drafts are ready.
      </p>
    </div>
  )
}
