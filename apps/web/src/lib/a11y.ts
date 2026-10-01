import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent, type RefObject } from 'react'

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function focusables(root: HTMLElement | null): HTMLElement[] {
  if (!root) return []
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null || el === document.activeElement)
}

/** Close a popover on outside pointer-down or Escape; Escape returns focus to the trigger. */
export function useDismiss(open: boolean, close: () => void, box: RefObject<HTMLElement>, trigger?: RefObject<HTMLElement>) {
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close()
        trigger?.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close, box, trigger])
}

/** Keep Tab focus inside `ref` while active; Escape calls onClose; focus returns to the opener on close. */
export function useFocusTrap(ref: RefObject<HTMLElement>, active: boolean, onClose: () => void) {
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    if (!active) return
    const prev = document.activeElement as HTMLElement | null
    const t = window.setTimeout(() => {
      const root = ref.current
      if (!root) return
      const preferred = root.querySelector<HTMLElement>('[data-autofocus]')
      ;(preferred ?? focusables(root)[0] ?? root).focus()
    }, 0)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        closeRef.current()
        return
      }
      if (e.key !== 'Tab' || !ref.current) return
      const els = focusables(ref.current)
      if (!els.length) return
      const [first, last] = [els[0], els[els.length - 1]]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(t)
      document.removeEventListener('keydown', onKey)
      if (prev && document.contains(prev)) prev.focus()
    }
  }, [ref, active])
}

/** Prevent the page behind an overlay from scrolling. */
export function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
    }
  }, [active])
}

/**
 * Arrow-key navigation for a group of items with the given role (tab, radio, menuitem, option).
 * Moves focus; for tabs and radios it also activates (clicks) the newly focused item.
 */
export function rovingKeyDown(e: ReactKeyboardEvent<HTMLElement>, role: 'tab' | 'radio' | 'menuitem' | 'menuitemradio' | 'option') {
  const keys = ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!keys.includes(e.key)) return
  const group = e.currentTarget
  const items = Array.from(group.querySelectorAll<HTMLElement>(`[role="${role}"]:not([disabled])`))
  if (!items.length) return
  const i = items.indexOf(document.activeElement as HTMLElement)
  let n = i
  if (e.key === 'Home') n = 0
  else if (e.key === 'End') n = items.length - 1
  else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = (i + 1) % items.length
  else n = (i - 1 + items.length) % items.length
  e.preventDefault()
  items[n].focus()
  if (role === 'tab' || role === 'radio') items[n].click()
}
