import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, LogOut, Mail, Pencil, ShieldCheck, Users } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { getTeacher, setTeacher, signOut } from '../lib/session'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Avatar, initialsOf } from '../components/ui/Logo'
import { Button } from '../components/ui/Button'
import { ErrorState, Loading, Notice } from '../components/ui/States'

export default function Profile() {
  const navigate = useNavigate()
  const profile = useAsync(() => api.profile(), [])
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [dept, setDept] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const p = profile.data

  async function save() {
    setSaving(true)
    setMsg(null)
    try {
      const r = await api.saveProfile({ name, department: dept })
      profile.setData(r)
      const t = getTeacher()
      if (t) setTeacher({ ...t, name: r.name, class_name: r.department }, true)
      setEditing(false)
      setMsg({ tone: 'ok', text: 'Profile saved.' })
    } catch (e) {
      setMsg({ tone: 'bad', text: (e as Error).message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <AppShell active="profile" topbar={<TopBar title="Profile" />}>
      {profile.error ? (
        <ErrorState message={profile.error} onRetry={profile.reload} />
      ) : !p ? (
        <Loading />
      ) : (
        <div className="mx-auto max-w-[760px]">
          <section className="card relative overflow-hidden">
            <div className="h-20 bg-navy bg-[radial-gradient(80%_120%_at_100%_0%,#323C96_0%,transparent_70%)] sm:h-24" aria-hidden />
            <div className="flex flex-col gap-4 px-5 pb-6 sm:flex-row sm:items-end sm:gap-6 sm:px-8 sm:pb-8">
            <span className="-mt-10 rounded-full ring-4 ring-white sm:-mt-12">
              <Avatar size={80} initials={initialsOf(p.name)} />
            </span>
            <div className="min-w-0 flex-1">
              {editing ? (
                <div className="grid gap-3">
                  <label className="text-[13px] font-semibold text-muted">
                    Display name
                    <input className="field mt-1 font-normal" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
                  </label>
                  <label className="text-[13px] font-semibold text-muted">
                    Department
                    <input className="field mt-1 font-normal" value={dept} onChange={(e) => setDept(e.target.value)} maxLength={120} />
                  </label>
                  <div className="flex gap-2">
                    <Button variant="dark" onClick={save} loading={saving} disabled={!name.trim()}>
                      Save
                    </Button>
                    <Button variant="secondary" onClick={() => setEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <h2 className="text-[22px] font-bold sm:text-[24px]">{p.name}</h2>
                  <p className="mt-1 text-[14px] text-muted sm:text-[15px]">
                    {p.role} · {p.department}
                  </p>
                  <p className="mt-3 flex min-w-0 items-center gap-2 text-[14px] text-[#3B4260]">
                    <Mail className="h-4 w-4 shrink-0 text-muted" aria-hidden /> <span className="truncate">{p.email}</span>
                  </p>
                  <p className="mt-1.5 flex items-center gap-2 text-[14px] text-[#3B4260]">
                    <ShieldCheck className="h-4 w-4 text-ok-bar" aria-hidden /> {p.account_status}
                  </p>
                </>
              )}
            </div>
            {!editing && (
              <Button
                variant="secondary"
                icon={<Pencil className="h-4 w-4" aria-hidden />}
                onClick={() => {
                  setName(p.name)
                  setDept(p.department)
                  setEditing(true)
                }}
              >
                Edit profile
              </Button>
            )}
            </div>
          </section>
          {msg && (
            <Notice tone={msg.tone} className="mt-4">
              {msg.text}
            </Notice>
          )}

          <div className="mt-5 grid grid-cols-3 gap-2 sm:mt-6 sm:gap-5">
            <div className="card px-3 py-4 text-center sm:px-6 sm:py-6 sm:text-left">
              <p className="label-caps flex items-center justify-center gap-1.5 sm:justify-start">
                <BookOpen className="hidden h-3.5 w-3.5 sm:block" aria-hidden /> Activities
              </p>
              <p className="mt-1.5 text-[24px] font-bold text-navy sm:mt-2 sm:text-[28px]">{p.activities}</p>
            </div>
            <div className="card px-3 py-4 text-center sm:px-6 sm:py-6 sm:text-left">
              <p className="label-caps">Classes</p>
              <p className="mt-1.5 text-[24px] font-bold text-navy sm:mt-2 sm:text-[28px]">{p.classes.length}</p>
            </div>
            <div className="card px-3 py-4 text-center sm:px-6 sm:py-6 sm:text-left">
              <p className="label-caps flex items-center justify-center gap-1.5 sm:justify-start">
                <Users className="hidden h-3.5 w-3.5 sm:block" aria-hidden /> Students
              </p>
              <p className="mt-1.5 text-[24px] font-bold text-navy sm:mt-2 sm:text-[28px]">{p.students}</p>
            </div>
          </div>
          <section className="card mt-5 px-5 py-5 sm:mt-6 sm:px-8 sm:py-6">
            <h3 className="text-[15px] font-semibold">Classes you manage</h3>
            <ul className="mt-3 divide-y divide-line">
              {p.classes.map((c) => (
                <li key={c} className="flex items-center gap-2 py-2.5 text-[14px]">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                  {c}
                </li>
              ))}
            </ul>
          </section>
          <p className="mt-6 text-[13px] text-muted">
            Password changes and new accounts are handled by your school's TsekMate administrator.
          </p>
          <Button
            variant="secondary"
            className="mt-4"
            icon={<LogOut className="h-4 w-4" aria-hidden />}
            onClick={() => {
              signOut()
              navigate('/signin')
            }}
          >
            Log out
          </Button>
        </div>
      )}
    </AppShell>
  )
}
