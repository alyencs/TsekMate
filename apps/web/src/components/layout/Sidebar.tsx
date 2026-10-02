import { NavLink, useNavigate } from 'react-router-dom'
import { Bell, BookOpenText, History, Layers, LayoutGrid, LogOut, Presentation, Settings, X } from 'lucide-react'
import { Avatar, Logo, initialsOf } from '../ui/Logo'
import { SUBJECTS, SUBJECT_LIST } from '../../lib/subjects'
import { getTeacher } from '../../lib/session'
import { logOut } from '../../lib/api'

export type NavKey = 'dashboard' | 'activities' | 'queue' | 'summary' | 'gradebook' | 'settings' | 'profile' | 'notifications'

const NAV: { key: NavKey; label: string; to: string; icon: typeof LayoutGrid }[] = [
  { key: 'dashboard', label: 'Dashboard', to: '/', icon: LayoutGrid },
  { key: 'activities', label: 'Activities', to: '/activities', icon: Layers },
  { key: 'queue', label: 'Review Queue', to: '/queue', icon: History },
  { key: 'summary', label: 'Class Summary', to: '/class-summary', icon: Presentation },
  { key: 'gradebook', label: 'Gradebook', to: '/gradebook', icon: BookOpenText },
]

const item = (on: boolean) =>
  `group relative flex h-11 items-center gap-3 rounded-[10px] px-3 text-[14px] transition-colors duration-150 ${
    on ? 'bg-white/10 font-semibold text-white' : 'text-[#C7CDF0] hover:bg-white/[0.06] hover:text-white'
  }`

function Indicator({ on }: { on: boolean }) {
  return <span className={`absolute -left-4 top-2 bottom-2 w-1 rounded-r-full bg-brand transition-opacity duration-200 ${on ? 'opacity-100' : 'opacity-0'}`} aria-hidden />
}

/** Navy sidebar. Rendered fixed on desktop and inside the slide-in drawer on smaller screens (`onClose` set). */
export function Sidebar({ active, variant, queueBadge, onClose }: { active?: NavKey; variant: 'dashboard' | 'default'; queueBadge?: number; onClose?: () => void }) {
  const navigate = useNavigate()
  const teacher = getTeacher()
  const name = teacher?.name ?? 'Prof. Ana Reyes'
  const showSubjects = variant === 'dashboard' || !!onClose
  return (
    <div className="on-dark flex h-full w-full flex-col overflow-y-auto bg-navy bg-[radial-gradient(120%_60%_at_0%_0%,#262E7A_0%,transparent_60%)] text-[#C7CDF0]">
      <div className="flex h-[76px] shrink-0 items-center justify-between gap-2 px-5">
        <NavLink to="/" aria-label="TsekMate home" className="rounded-[10px]">
          <Logo tone="light" size={34} tagline />
        </NavLink>
        {onClose && (
          <button type="button" onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-full text-[#C7CDF0] hover:bg-white/10 hover:text-white" aria-label="Close menu">
            <X className="h-5 w-5" aria-hidden />
          </button>
        )}
      </div>

      <nav aria-label="Main" className="mt-3 flex flex-col gap-1 px-4">
        <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#9AA3D8]">Workspace</p>
        {NAV.map(({ key, label, to, icon: Icon }) => {
          const on = key === active
          return (
            <NavLink key={key} to={to} aria-current={on ? 'page' : undefined} className={item(on)}>
              <Indicator on={on} />
              <Icon className={`h-[18px] w-[18px] shrink-0 transition-colors ${on ? 'text-brand-bright' : 'text-[#9AA3D8] group-hover:text-white'}`} aria-hidden />
              <span className="flex-1 truncate">{label}</span>
              {key === 'queue' && queueBadge ? (
                <span className="rounded-full bg-brand-bright px-2 py-0.5 text-[11px] font-bold text-navy-950" aria-label={`${queueBadge} flagged papers`}>
                  {queueBadge}
                </span>
              ) : null}
            </NavLink>
          )
        })}
      </nav>

      {showSubjects && (
        <div className="mt-7 px-4">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#9AA3D8]">Subjects</p>
          <ul className="mt-2 flex flex-col gap-0.5">
            {SUBJECT_LIST.map((s) => (
              <li key={s}>
                <NavLink to={`/activities?subject=${s}`} className="flex h-10 items-center gap-3 rounded-[10px] px-3 text-[14px] text-[#C7CDF0] transition-colors hover:bg-white/[0.06] hover:text-white">
                  <span className={`h-2 w-2 rounded-full ring-2 ring-white/10 ${SUBJECTS[s].dot}`} aria-hidden />
                  {SUBJECTS[s].sidebarLabel}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-auto px-4 pb-4 pt-6">
        <div className="flex flex-col gap-1">
          <NavLink to="/notifications" aria-current={active === 'notifications' ? 'page' : undefined} className={item(active === 'notifications')}>
            <Indicator on={active === 'notifications'} />
            <Bell className={`h-[18px] w-[18px] ${active === 'notifications' ? 'text-brand-bright' : 'text-[#9AA3D8] group-hover:text-white'}`} aria-hidden />
            Notifications
          </NavLink>
          <NavLink to="/settings" aria-current={active === 'settings' ? 'page' : undefined} className={item(active === 'settings')}>
            <Indicator on={active === 'settings'} />
            <Settings className={`h-[18px] w-[18px] ${active === 'settings' ? 'text-brand-bright' : 'text-[#9AA3D8] group-hover:text-white'}`} aria-hidden />
            Settings
          </NavLink>
        </div>
        <div className="mt-3 flex items-center gap-1 rounded-[12px] border border-white/10 bg-white/[0.04] p-1.5">
          <NavLink
            to="/profile"
            aria-current={active === 'profile' ? 'page' : undefined}
            className={`flex min-w-0 flex-1 items-center gap-3 rounded-[10px] px-2 py-2 transition-colors hover:bg-white/[0.06] ${active === 'profile' ? 'bg-white/10' : ''}`}
            aria-label={`Open your profile, ${name}`}
          >
            <Avatar size={34} initials={initialsOf(name)} />
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-[13px] font-semibold text-white">{name}</span>
              <span className="block truncate text-[11px] text-[#9AA3D8]">{teacher?.class_name ?? 'General Education Department'}</span>
            </span>
          </NavLink>
          <button
            type="button"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] text-[#9AA3D8] transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Log out"
            title="Log out"
            onClick={async () => {
              await logOut()
              navigate('/signin')
            }}
          >
            <LogOut className="h-[18px] w-[18px]" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  )
}
