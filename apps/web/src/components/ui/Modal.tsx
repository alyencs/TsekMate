import { useRef, type ReactNode } from 'react'
import { useFocusTrap, useScrollLock } from '../../lib/a11y'

export function Modal({
  open,
  onClose,
  labelledBy,
  children,
  className = '',
}: {
  open: boolean
  onClose: () => void
  labelledBy: string
  children: ReactNode
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(ref, open, onClose)
  useScrollLock(open)
  if (!open) return null
  return (
    <div className="animate-fade fixed inset-0 z-[60] flex items-end justify-center bg-navy-950/50 p-3 backdrop-blur-[3px] sm:items-center sm:p-4" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={`animate-dialog max-h-[calc(100dvh-1.5rem)] w-full overflow-y-auto overscroll-contain rounded-2xl bg-white shadow-pop focus:outline-none sm:max-h-[calc(100dvh-2rem)] ${className}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}
