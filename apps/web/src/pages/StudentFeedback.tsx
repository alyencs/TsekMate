import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Award, BadgeCheck, Square, Volume2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { fmtScore } from '../lib/format'
import { AI_LABEL } from '../lib/subjects'
import { getTeacher } from '../lib/session'
import { Logo } from '../components/ui/Logo'
import { ErrorState, Loading } from '../components/ui/States'

export default function StudentFeedback() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const detail = useAsync(() => api.submission(id), [id])
  const [speaking, setSpeaking] = useState(false)
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window
  useEffect(() => () => (canSpeak ? window.speechSynthesis.cancel() : undefined), [canSpeak])

  const d = detail.data
  const order = Number(params.get('p')) || 1
  const prob = d?.activity.problems.find((p) => p.order === order) ?? d?.activity.problems[0]
  const result = d?.ai_result?.problems.find((p) => p.problem_id === prob?.id)
  const score = result?.final_score
  const note = prob ? d?.review.feedback[prob.id] ?? '' : ''
  const short = d?.activity.title.includes(':') ? d.activity.title.split(':')[1].trim() : d?.activity.title
  const noun = d?.activity.subject === 'grammar' ? 'Item' : 'Problem'
  const teacher = getTeacher()?.name ?? 'your teacher'

  function speak() {
    if (!canSpeak) return
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const u = new SpeechSynthesisUtterance(`Your score is ${fmtScore(score)} out of ${fmtScore(result?.max_score)}. Your teacher's note: ${note}`)
    u.rate = 0.92
    u.onend = () => setSpeaking(false)
    u.onerror = () => setSpeaking(false)
    setSpeaking(true)
    window.speechSynthesis.speak(u)
  }

  return (
    <main className="animate-page flex min-h-screen flex-col items-center bg-page bg-[radial-gradient(60%_40%_at_50%_0%,#FFEDD5_0%,transparent_70%)] px-4 py-10 sm:px-6 sm:py-20">
      <Logo size={40} tagline />
      {detail.error ? (
        <ErrorState message={detail.error} onRetry={detail.reload} />
      ) : !d || !prob ? (
        <Loading />
      ) : d.status !== 'approved' ? (
        <div className="card mt-10 max-w-md px-6 py-8 text-center">
          <h1 className="text-[22px] font-bold">Your feedback is not ready yet</h1>
          <p className="mt-2 text-[15px] text-muted">Your teacher is still reviewing this work.</p>
        </div>
      ) : (
        <>
          <h1 className="mt-8 text-center text-[20px] font-bold leading-snug sm:mt-10 sm:text-[24px]">
            Your feedback: {short}, {noun} {prob.order}
          </h1>
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-ok-bg px-3 py-1 text-[13px] font-semibold text-ok-text sm:text-[14px]">
            <BadgeCheck className="h-4 w-4" aria-hidden /> Reviewed and approved by {teacher}
          </p>
          <section className="mt-8 w-full max-w-[600px] rounded-2xl border border-line bg-white px-5 py-6 shadow-pop sm:mt-10 sm:px-10 sm:py-10">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="label-caps tracking-[0.14em]">Your score</p>
                <p className="mt-2 text-[44px] font-bold leading-none text-navy sm:text-[60px]">
                  {fmtScore(score)} <span className="text-[20px] font-medium text-muted sm:text-[26px]">/ {fmtScore(result?.max_score)}</span>
                </p>
              </div>
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent-light text-accent sm:h-20 sm:w-20" aria-hidden>
                <Award className="h-7 w-7 sm:h-9 sm:w-9" />
              </span>
            </div>
            <p className="label-caps mt-8 tracking-[0.14em] sm:mt-10">Teacher&apos;s note</p>
            <p className="mt-3 text-[18px] font-semibold leading-snug text-[#3B4260] sm:text-[22px]">&quot;{note || 'Great work on this one.'}&quot;</p>
            <button
              type="button"
              onClick={speak}
              disabled={!canSpeak}
              className="mt-8 flex min-h-[64px] w-full items-center justify-center gap-3 rounded-2xl bg-brand-strong px-4 text-[17px] font-semibold text-white shadow-cta transition-colors hover:bg-brand-dark disabled:opacity-50 sm:mt-10 sm:min-h-[80px] sm:text-[19px]"
              aria-pressed={speaking}
            >
              {speaking ? <Square className="h-6 w-6" aria-hidden /> : <Volume2 className="h-7 w-7" aria-hidden />}
              {speaking ? 'Stop' : canSpeak ? 'Listen to feedback' : 'Listening is not supported in this browser'}
            </button>
            <p className="mt-4 text-center text-[12px] text-muted">{AI_LABEL}</p>
          </section>
          <Link to={`/gradebook?activity=${d.activity.id}`} className="mt-8 flex items-center gap-2 rounded px-2 py-1 text-[14px] font-semibold text-muted hover:text-ink sm:mt-10">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Back to all grades
          </Link>
        </>
      )}
    </main>
  )
}
