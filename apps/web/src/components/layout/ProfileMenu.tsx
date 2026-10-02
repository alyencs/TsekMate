import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronDown, LogOut, Settings, UserRound } from 'lucide-react'
import { getTeacher } from '../../lib/session'
import { logOut } from '../../lib/api'
import { Avatar } from '../ui/Logo'

function initials(name: string) {
  const parts = name.replace(/^(Prof|Dr|Ms|Mr|Mrs)\.?\s+/i, '').split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase() || 'T'
}

/** Clickable profile control: compact initials (default) or avatar + name (dashboard). Opens a small account menu. */
export function ProfileMenu({ variant = 'compact' }: { variant?: 'compact' | 'full' }) {
  const navigate = useNavigate()
  const teacher = getTeacher()
  const name = teacher?.name ?? 'Prof. Ana Reyes'
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="relative" ref={box}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${name}`}
        className={`flex items-center gap-3 rounded-full transition-colors hover:bg-gray-100 ${variant === 'full' ? 'py-1 pl-1 pr-2' : 'p-0.5'}`}
      >
        {variant === 'full' ? (
          <>
            <Avatar size={32} />
            <span className="text-left leading-tight">
              <span className="block text-[14px] font-semibold">{name}</span>
              <span className="block text-[11px] text-muted">Teacher</span>
            </span>
            <ChevronDown className="ml-1 h-4 w-4 text-muted" aria-hidden />
          </>
        ) : (
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-light text-[12px] font-bold text-brand-dark">{initials(name)}</span>
        )}
      </button>
      {open && (
        <div role="menu" className="animate-pop absolute right-0 top-12 z-40 w-60 origin-top-right overflow-hidden rounded-card border border-line bg-white py-1 shadow-pop">
          <div className="border-b border-line px-4 py-3">
            <p className="text-[14px] font-semibold">{name}</p>
            <p className="truncate text-[12px] text-muted">{teacher?.email}</p>
          </div>
          <Link role="menuitem" to="/profile" className="flex items-center gap-2.5 px-4 py-2.5 text-[14px] hover:bg-gray-50" onClick={() => setOpen(false)}>
            <UserRound className="h-4 w-4 text-muted" aria-hidden /> Profile
          </Link>
          <Link role="menuitem" to="/settings" className="flex items-center gap-2.5 px-4 py-2.5 text-[14px] hover:bg-gray-50" onClick={() => setOpen(false)}>
            <Settings className="h-4 w-4 text-muted" aria-hidden /> Settings
          </Link>
          <button
            role="menuitem"
            className="flex w-full items-center gap-2.5 border-t border-line px-4 py-2.5 text-left text-[14px] hover:bg-gray-50"
            onClick={async () => {
              await logOut()
              navigate('/signin')
            }}
          >
            <LogOut className="h-4 w-4 text-muted" aria-hidden /> Log out
          </button>
        </div>
      )}
    </div>
  )
}
