import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Award, Square, Volume2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { fmtScore } from '../lib/format'
import { AI_LABEL } from '../lib/subjects'
import { getTeacher } from '../lib/session'
import { LogoMark } from '../components/ui/Logo'
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
  const score = prob ? d?.review.problem_scores[prob.id] ?? result?.suggested_score : undefined
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
    <main className="flex min-h-screen flex-col items-center bg-page px-6 py-[188px]">
      <div className="flex items-center gap-2.5">
        <LogoMark size={32} />
        <span className="text-[20px] font-bold tracking-tight">TSEKMATE</span>
      </div>
      {detail.error ? (
        <ErrorState message={detail.error} onRetry={detail.reload} />
      ) : !d || !prob ? (
        <Loading />
      ) : d.status !== 'approved' ? (
        <div className="mt-10 max-w-md text-center">
          <h1 className="text-[24px] font-bold">Your feedback is not ready yet</h1>
          <p className="mt-2 text-[17px] text-muted">Your teacher is still reviewing this work.</p>
        </div>
      ) : (
        <>
          <h1 className="mt-10 text-center text-[24px] font-bold">
            Your feedback: {short}, {noun} {prob.order}
          </h1>
          <p className="mt-3 text-[17px] text-gray-600">Reviewed and approved by {teacher}</p>
          <section className="mt-10 w-full max-w-[600px] rounded-2xl border border-line bg-white px-10 py-10 shadow-pop">
            <div className="flex items-start justify-between">
              <div>
                <p className="label-caps tracking-[0.14em]">Your score</p>
                <p className="mt-2 text-[60px] font-bold leading-none">
                  {fmtScore(score)} <span className="text-[26px] font-medium text-gray-400">/ {fmtScore(result?.max_score)}</span>
                </p>
              </div>
              <span className="flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-light text-brand" aria-hidden>
                <Award className="h-9 w-9" />
              </span>
            </div>
            <p className="label-caps mt-10 tracking-[0.14em]">Teacher&apos;s note</p>
            <p className="mt-3 text-[24px] font-semibold leading-snug text-gray-700">&quot;{note || 'Great work on this one.'}&quot;</p>
            <button
              onClick={speak}
              disabled={!canSpeak}
              className="mt-10 flex h-[84px] w-full items-center justify-center gap-3 rounded-2xl bg-brand text-[20px] font-semibold text-white shadow-md hover:bg-brand-dark disabled:opacity-50"
              aria-pressed={speaking}
            >
              {speaking ? <Square className="h-6 w-6" aria-hidden /> : <Volume2 className="h-7 w-7" aria-hidden />}
              {speaking ? 'Stop' : canSpeak ? 'Listen to feedback' : 'Listening is not supported in this browser'}
            </button>
            <p className="mt-4 text-center text-[12px] text-muted">{AI_LABEL}</p>
          </section>
          <Link to={`/gradebook?activity=${d.activity.id}`} className="mt-10 flex items-center gap-2 text-[15px] font-semibold text-gray-500 hover:text-ink">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Back to all grades
          </Link>
        </>
      )}
    </main>
  )
}
