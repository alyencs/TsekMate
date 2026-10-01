import { NavLink, useNavigate } from 'react-router-dom'
import { BookOpenText, History, Layers, LayoutGrid, LogOut, Presentation, Settings } from 'lucide-react'
import type { ReactNode } from 'react'
import { Avatar, Logo } from '../ui/Logo'
import { SUBJECTS, SUBJECT_LIST } from '../../lib/subjects'
import { getTeacher, signOut } from '../../lib/session'

export type NavKey = 'dashboard' | 'activities' | 'queue' | 'summary' | 'gradebook'

const NAV: { key: NavKey; label: string; to: string; icon: typeof LayoutGrid }[] = [
  { key: 'dashboard', label: 'Dashboard', to: '/', icon: LayoutGrid },
  { key: 'activities', label: 'Activities', to: '/activities', icon: Layers },
  { key: 'queue', label: 'Review Queue', to: '/queue', icon: History },
  { key: 'summary', label: 'Class Summary', to: '/class-summary', icon: Presentation },
  { key: 'gradebook', label: 'Gradebook', to: '/gradebook', icon: BookOpenText },
]

export function Sidebar({ active, variant, queueBadge }: { active: NavKey; variant: 'dashboard' | 'default'; queueBadge?: number }) {
  const navigate = useNavigate()
  const teacher = getTeacher()
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-sidebar flex-col border-r border-line bg-white">
      <div className="flex h-topbar items-center px-6">
        <NavLink to="/" aria-label="TsekMate home">
          <Logo />
        </NavLink>
      </div>
      <nav aria-label="Main" className="mt-4 flex flex-col gap-1 px-4">
        {NAV.map(({ key, label, to, icon: Icon }) => {
          const on = key === active
          return (
            <NavLink
              key={key}
              to={to}
              aria-current={on ? 'page' : undefined}
              className={`flex h-12 items-center gap-3 rounded-[10px] px-3 text-[15px] transition-colors ${
                on
                  ? `bg-brand-light font-semibold text-brand-dark ${variant === 'default' ? 'border-l-[3px] border-brand pl-[9px]' : ''}`
                  : 'text-gray-600 hover:bg-gray-50 hover:text-ink'
              }`}
            >
              <Icon className={`h-[18px] w-[18px] ${on ? 'text-brand' : 'text-gray-500'}`} aria-hidden />
              <span className="flex-1">{label}</span>
              {key === 'queue' && queueBadge ? (
                <span className="rounded-full bg-bad-bg px-2 py-0.5 text-[11px] font-semibold text-bad-text" aria-label={`${queueBadge} flagged papers`}>
                  {queueBadge}
                </span>
              ) : null}
            </NavLink>
          )
        })}
      </nav>

      {variant === 'dashboard' && (
        <div className="mt-10 px-4">
          <p className="label-caps px-3 text-gray-400">Subjects</p>
          <ul className="mt-3 flex flex-col gap-1">
            {SUBJECT_LIST.map((s) => (
              <li key={s}>
                <NavLink to={`/activities?subject=${s}`} className="flex h-10 items-center gap-3 rounded-[10px] px-3 text-[15px] text-gray-600 hover:bg-gray-50 hover:text-ink">
                  <span className={`h-2 w-2 rounded-full ${SUBJECTS[s].dot}`} aria-hidden />
                  {SUBJECTS[s].sidebarLabel}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-auto border-t border-line">
        {variant === 'dashboard' ? (
          <div className="flex flex-col gap-1 px-4 py-4">
            <FooterButton icon={<Settings className="h-[18px] w-[18px]" aria-hidden />} label="Settings" title="Settings are not part of the prototype" disabled />
            <FooterButton
              icon={<LogOut className="h-[18px] w-[18px]" aria-hidden />}
              label="Log out"
              onClick={() => {
                signOut()
                navigate('/signin')
              }}
            />
          </div>
        ) : (
          <div className="flex items-center gap-3 px-7 py-5">
            <Avatar size={32} />
            <div className="leading-tight">
              <p className="text-[13px] font-semibold">{teacher?.name ?? 'Ms. Reyes'}</p>
              <p className="text-[11px] text-muted">{teacher?.class_name ?? 'Grade 8 Rizal'}</p>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}

function FooterButton({ icon, label, onClick, disabled, title }: { icon: ReactNode; label: string; onClick?: () => void; disabled?: boolean; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-disabled={disabled || undefined}
      title={title}
      className={`flex h-12 items-center gap-3 rounded-[10px] px-3 text-left text-[15px] text-gray-600 ${disabled ? 'cursor-default' : 'hover:bg-gray-50 hover:text-ink'}`}
    >
      <span className="text-gray-500">{icon}</span>
      {label}
    </button>
  )
}
