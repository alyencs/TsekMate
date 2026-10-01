import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, LogOut, Mail, Pencil, ShieldCheck, Users } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/useAsync'
import { getTeacher, setTeacher, signOut } from '../lib/session'
import { AppShell, TopBar } from '../components/layout/AppShell'
import { Avatar } from '../components/ui/Logo'
import { Button } from '../components/ui/Button'
import { ErrorState, Loading } from '../components/ui/States'

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
          <section className="card flex items-start gap-6 px-8 py-8">
            <Avatar size={72} />
            <div className="min-w-0 flex-1">
              {editing ? (
                <div className="grid gap-3">
                  <label className="text-[13px] font-semibold text-gray-600">
                    Display name
                    <input className="field mt-1 font-normal" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
                  </label>
                  <label className="text-[13px] font-semibold text-gray-600">
                    Department
                    <input className="field mt-1 font-normal" value={dept} onChange={(e) => setDept(e.target.value)} maxLength={120} />
                  </label>
                  <div className="flex gap-2">
                    <Button onClick={save} loading={saving} disabled={!name.trim()}>
                      Save
                    </Button>
                    <Button variant="secondary" onClick={() => setEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <h2 className="text-[24px] font-bold tracking-tight">{p.name}</h2>
                  <p className="mt-1 text-[15px] text-muted">
                    {p.role} · {p.department}
                  </p>
                  <p className="mt-3 flex items-center gap-2 text-[14px] text-gray-700">
                    <Mail className="h-4 w-4 text-muted" aria-hidden /> {p.email}
                  </p>
                  <p className="mt-1.5 flex items-center gap-2 text-[14px] text-gray-700">
                    <ShieldCheck className="h-4 w-4 text-[#16A34A]" aria-hidden /> {p.account_status}
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
          </section>
          {msg && (
            <p role={msg.tone === 'bad' ? 'alert' : 'status'} className={`animate-fade mt-4 rounded-ctl border px-4 py-2.5 text-[14px] ${msg.tone === 'bad' ? 'border-bad-border bg-bad-bg text-bad-text' : 'border-ok-border bg-ok-bg text-ok-text'}`}>
              {msg.text}
            </p>
          )}

          <div className="mt-6 grid grid-cols-3 gap-5">
            <div className="card px-6 py-6">
              <p className="label-caps flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5" aria-hidden /> Activities
              </p>
              <p className="mt-2 text-[28px] font-bold">{p.activities}</p>
            </div>
            <div className="card px-6 py-6">
              <p className="label-caps">Classes</p>
              <p className="mt-2 text-[28px] font-bold">{p.classes.length}</p>
            </div>
            <div className="card px-6 py-6">
              <p className="label-caps flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5" aria-hidden /> Students
              </p>
              <p className="mt-2 text-[28px] font-bold">{p.students}</p>
            </div>
          </div>
          <section className="card mt-6 px-8 py-6">
            <h3 className="text-[15px] font-semibold">Classes you manage</h3>
            <ul className="mt-3 divide-y divide-line">
              {p.classes.map((c) => (
                <li key={c} className="py-2.5 text-[14px]">
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
