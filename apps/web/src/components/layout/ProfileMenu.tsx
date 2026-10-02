import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, LogOut, Settings, UserRound } from 'lucide-react'
import { getTeacher } from '../../lib/session'
import { logOut } from '../../lib/api'
import { rovingKeyDown, useDismiss } from '../../lib/a11y'
import { Avatar, initialsOf } from '../ui/Logo'

const itemCls = 'flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-[14px] text-ink transition-colors hover:bg-soft focus:bg-soft focus:outline-none'

/** Account control: initials (compact) or avatar + name (full, md+). Opens a small account menu. */
export function ProfileMenu({ variant = 'compact' }: { variant?: 'compact' | 'full' }) {
  const navigate = useNavigate()
  const teacher = getTeacher()
  const name = teacher?.name ?? 'Prof. Ana Reyes'
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const close = useCallback(() => setOpen(false), [])
  useDismiss(open, close, box, btn)
  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
  }, [open])

  return (
    <div className="relative" ref={box}>
      <button
        ref={btn}
        type="button"
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setOpen(true)
          }
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${name}`}
        className={`flex items-center gap-3 rounded-full transition-colors hover:bg-soft ${open ? 'bg-soft' : ''} ${variant === 'full' ? 'p-1 md:py-1 md:pl-1 md:pr-3' : 'p-1'}`}
      >
        <Avatar size={34} initials={initialsOf(name)} />
        {variant === 'full' && (
          <>
            <span className="hidden text-left leading-tight md:block">
              <span className="block max-w-[160px] truncate text-[14px] font-semibold">{name}</span>
              <span className="block text-[11px] text-muted">Teacher</span>
            </span>
            <ChevronDown className={`hidden h-4 w-4 text-muted transition-transform md:block ${open ? 'rotate-180' : ''}`} aria-hidden />
          </>
        )}
      </button>
      {open && (
        <div
          ref={menu}
          role="menu"
          aria-label="Account"
          onKeyDown={(e) => rovingKeyDown(e, 'menuitem')}
          className="animate-pop absolute right-0 top-12 z-40 w-64 origin-top-right overflow-hidden rounded-card border border-line bg-white py-1 shadow-pop"
        >
          <div className="flex items-center gap-3 border-b border-line px-4 py-3">
            <Avatar size={38} initials={initialsOf(name)} />
            <div className="min-w-0">
              <p className="truncate text-[14px] font-semibold">{name}</p>
              <p className="truncate text-[12px] text-muted">{teacher?.email}</p>
            </div>
          </div>
          <Link role="menuitem" tabIndex={-1} to="/profile" className={itemCls} onClick={close}>
            <UserRound className="h-4 w-4 text-muted" aria-hidden /> Profile
          </Link>
          <Link role="menuitem" tabIndex={-1} to="/settings" className={itemCls} onClick={close}>
            <Settings className="h-4 w-4 text-muted" aria-hidden /> Settings
          </Link>
          <Link role="menuitem" tabIndex={-1} to="/notifications" className={itemCls} onClick={close}>
            <Bell className="h-4 w-4 text-muted" aria-hidden /> Notifications
          </Link>
          <button
            role="menuitem"
            tabIndex={-1}
            type="button"
            className={`${itemCls} border-t border-line`}
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
