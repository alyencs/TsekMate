import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CircleCheck, CircleX, Eye, EyeOff, Info, ShieldCheck, Sparkles, UserRoundCheck } from 'lucide-react'
import { api } from '../lib/api'
import { setTeacher } from '../lib/session'
import { Button } from '../components/ui/Button'
import { Logo } from '../components/ui/Logo'

export default function SignIn() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const from = params.get('from')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState<string | null>(params.get('expired') ? 'Your session has ended. Please sign in again.' : null)
  const [info, setInfo] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    if (!email.trim() || !password) {
      setError('Enter your email address and password.')
      return
    }
    setLoading(true)
    try {
      const t = await api.signIn(email, password)
      setTeacher(t, remember)
      // only same-app paths: never navigate to another origin taken from the URL
      navigate(from && /^\/(?![/\\])/.test(from) && !from.includes('\\') && !from.startsWith('/signin') ? from : '/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-1 bg-white lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <main className="animate-page flex items-center justify-center px-5 py-10 sm:px-10 sm:py-16">
        <div className="w-full max-w-[420px]">
          <Logo size={46} tagline />
          <h1 className="mt-10 text-[26px] font-bold sm:mt-12 sm:text-[30px]">Welcome back</h1>
          <p className="mt-1.5 text-[15px] text-muted">Sign in to your teacher account</p>

          <form onSubmit={submit} className="mt-8 flex flex-col" noValidate aria-describedby={error ? 'signin-error' : undefined}>
            <label htmlFor="email" className="text-[14px] font-medium">
              Email address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              inputMode="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@university.edu.ph"
              aria-invalid={!!error && !email.trim()}
              className="field mt-2 h-12"
            />
            <div className="mt-5 flex items-center justify-between">
              <label htmlFor="password" className="text-[14px] font-medium">
                Password
              </label>
              <button
                type="button"
                className="rounded text-[13px] font-semibold text-brand-dark hover:underline"
                onClick={() => {
                  setError(null)
                  setInfo('Password resets are handled by your school’s TsekMate administrator.')
                }}
              >
                Forgot password?
              </button>
            </div>
            <div className="relative mt-2">
              <input
                id="password"
                type={show ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                aria-invalid={!!error && !password}
                className="field h-12 pr-12"
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute right-1.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-ctl text-muted hover:bg-soft hover:text-ink"
                aria-label={show ? 'Hide password' : 'Show password'}
                aria-pressed={show}
              >
                {show ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
              </button>
            </div>
            <label className="mt-5 flex w-fit items-center gap-3 text-[14px] text-[#3B4260]">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-[18px] w-[18px] rounded border-[#B7C0D3] accent-brand" />
              Keep me signed in on this device
            </label>
            {error && (
              <p id="signin-error" role="alert" className="notice notice-bad animate-fade mt-5">
                <CircleX className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}
            {info && (
              <p role="status" className="notice notice-info animate-fade mt-5">
                <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {info}
              </p>
            )}
            <Button type="submit" size="lg" loading={loading} className="mt-6 w-full">
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
          <p className="mt-8 text-center text-[14px] text-muted">
            Don&apos;t have an account? <span className="font-semibold text-ink">Contact your school admin.</span>
          </p>
          <p className="mt-8 flex items-start justify-center gap-2 text-center text-[12px] text-muted lg:hidden">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" aria-hidden />
            AI drafts every grade. You approve every grade.
          </p>
        </div>
      </main>

      <aside aria-hidden className="on-dark relative hidden items-center justify-center overflow-hidden bg-navy px-10 py-16 lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(70%_60%_at_80%_10%,#323C96_0%,transparent_70%),radial-gradient(60%_50%_at_10%_100%,#262E7A_0%,transparent_70%)]" />
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full border border-white/10" />
        <div className="absolute -bottom-24 -left-10 h-72 w-72 rounded-full border border-white/10" />
        <Sparkles className="absolute right-[14%] top-[12%] h-8 w-8 text-accent" />
        <div className="relative flex max-w-[520px] flex-col items-center">
          <p className="text-center text-[34px] font-bold leading-[1.2] xl:text-[38px]">
            <span className="text-white">Every step checked.</span>
            <br />
            <span className="text-accent">Every teacher in control.</span>
          </p>
          <p className="mt-4 text-center text-[15px] text-[#C7CDF0]">TsekMate drafts the grade from your rubric. You review, adjust, and approve it.</p>

          <div className="relative mt-10 w-full max-w-[420px]">
            <div className="absolute inset-0 translate-x-4 translate-y-3 rotate-[2deg] rounded-2xl bg-white/10" />
            <div className="relative rounded-2xl bg-white p-7 shadow-pop">
              <div className="flex items-center justify-between">
                <div className="h-3.5 w-40 rounded bg-[#E9EDF5]" />
                <span className="rounded-full bg-brand-light px-2.5 py-1 text-[11px] font-semibold text-brand-dark">AI draft</span>
              </div>
              {[
                ['w-[48%]', true],
                ['w-[60%]', true],
                ['w-[34%]', false],
              ].map(([w, ok], i) => (
                <div key={i} className="mt-6 flex items-center justify-between">
                  <div className={`h-3 ${w} rounded bg-[#E9EDF5]`} />
                  <span className={`flex items-center gap-1.5 text-[14px] font-semibold ${ok ? 'text-ok-text' : 'text-bad-text'}`}>
                    {ok ? <CircleCheck className="h-5 w-5 fill-ok-bar text-white" /> : <CircleX className="h-5 w-5 fill-bad-strong text-white" />}
                    {ok ? 'Correct' : 'Error'}
                  </span>
                </div>
              ))}
              <div className="mt-8 flex items-end justify-between border-t border-line pt-4">
                <div>
                  <p className="label-caps">Final grade</p>
                  <p className="mt-1 text-[30px] font-bold text-navy">
                    8.5 <span className="text-[16px] font-medium text-muted">/ 10</span>
                  </p>
                </div>
                <span className="flex items-center gap-1.5 rounded-full bg-accent-light px-3 py-1.5 text-[12px] font-semibold text-accent-text">
                  <UserRoundCheck className="h-4 w-4" /> Approved by teacher
                </span>
              </div>
            </div>
          </div>

          <ol className="mt-10 flex items-center gap-2 text-[13px] font-medium text-[#C7CDF0]">
            {['Upload work', 'AI drafts', 'You review', 'You approve'].map((s, i) => (
              <li key={s} className="flex items-center gap-2">
                {i > 0 && <span className="h-px w-4 bg-white/25" />}
                <span className={`rounded-full px-3 py-1 ${i === 3 ? 'bg-accent text-navy-950 font-semibold' : 'bg-white/10'}`}>{s}</span>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  )
}
