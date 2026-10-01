import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Check, CircleCheck, CircleX, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { setTeacher } from '../lib/session'
import { Button } from '../components/ui/Button'

export default function SignIn() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const from = params.get('from')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState<string | null>(params.get('expired') ? 'Your session has ended. Please sign in again.' : null)
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
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
    <div className="grid min-h-screen grid-cols-1 bg-white lg:grid-cols-2">
      <main className="flex items-center px-8 py-16 lg:px-[140px]">
        <div className="w-full max-w-[440px]">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-brand text-white" aria-hidden>
              <Check className="h-5 w-5" strokeWidth={3} />
            </span>
            <span className="text-[24px] font-bold tracking-tight">TsekMate</span>
          </div>
          <h1 className="mt-12 text-[30px] font-bold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-[16px] text-muted">Sign in to your teacher account</p>

          <form onSubmit={submit} className="mt-10 flex flex-col" noValidate>
            <label htmlFor="email" className="text-[14px] font-medium">
              Email address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@university.edu.ph"
              className="field mt-2 h-12 rounded-[10px]"
            />
            <div className="mt-6 flex items-center justify-between">
              <label htmlFor="password" className="text-[14px] font-medium">
                Password
              </label>
              <button type="button" className="text-[14px] font-semibold text-brand-dark hover:underline" onClick={() => setError('Password reset is handled by your school admin.')}>
                Forgot password?
              </button>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="field mt-2 h-12 rounded-[10px]"
            />
            <label className="mt-6 flex items-center gap-12 text-[14px] text-gray-600">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-5 w-5 rounded border-gray-400 accent-brand" />
              Keep me signed in on this device
            </label>
            {error && (
              <p role="alert" className="mt-5 flex items-center gap-2 rounded-ctl border border-bad-border bg-bad-bg px-3 py-2 text-[14px] text-bad-text">
                <CircleX className="h-4 w-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}
            <Button type="submit" loading={loading} className="mt-6 h-12 w-full rounded-[10px] text-[16px]">
              Sign in
            </Button>
          </form>
          <p className="mt-8 text-center text-[14px] text-gray-600">Don&apos;t have an account?</p>
          <p className="text-[16px] font-semibold text-brand-dark">Contact your school admin</p>
        </div>
      </main>

      <aside aria-hidden className="relative hidden items-center justify-center overflow-hidden bg-[#FFF1E6] lg:flex">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/30" />
        <div className="absolute -bottom-16 left-0 h-48 w-48 rounded-full bg-white/20" />
        <div className="flex flex-col items-center">
          <p className="text-center text-[38px] font-bold leading-[1.2] tracking-tight">
            <span className="text-ink">Every step checked.</span>
            <br />
            <span className="text-brand">Every teacher in control.</span>
          </p>
          <div className="relative mt-10 h-[410px] w-[440px]">
            <div className="absolute left-[18px] top-[14px] h-[400px] w-[430px] rotate-[1.5deg] rounded-2xl border border-line bg-white/80" />
            <div className="absolute inset-0 rotate-[2deg] rounded-2xl border border-line bg-white p-8 shadow-pop">
              <div className="h-4 w-[90%] rounded bg-gray-100" />
              <div className="mt-4 h-4 w-[70%] rounded bg-gray-100" />
              {[
                ['w-[48%]', true],
                ['w-[60%]', true],
                ['w-[30%]', false],
              ].map(([w, ok], i) => (
                <div key={i} className="mt-7 flex items-center justify-between">
                  <div className={`h-3 ${w} rounded bg-gray-100`} />
                  <span className={`flex items-center gap-1.5 text-[15px] font-semibold ${ok ? 'text-[#16A34A]' : 'text-bad-strong'}`}>
                    {ok ? <CircleCheck className="h-5 w-5 fill-[#16A34A] text-white" /> : <CircleX className="h-5 w-5 fill-bad-strong text-white" />}
                    {ok ? 'Correct' : 'Error'}
                  </span>
                </div>
              ))}
              <div className="mt-12 border-t border-line pt-4">
                <p className="text-[11px] uppercase tracking-wider text-muted">Grade</p>
                <div className="mt-2 flex items-end justify-between">
                  <span className="text-[30px] font-bold text-brand">85%</span>
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-light text-brand">
                    <Sparkles className="h-4 w-4" />
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}
