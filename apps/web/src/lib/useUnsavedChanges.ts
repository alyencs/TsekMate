import { useCallback, useEffect } from 'react'

const MESSAGE = 'You have unsaved changes on this paper. Leave without saving them?'

/**
 * Warn before unsaved edits are lost. Covers closing or reloading the tab (beforeunload) and every in-app link
 * (sidebar, menus, breadcrumbs) through a capture-phase click listener that runs before React Router's <Link>.
 * Returns `confirmLeave()` for code that navigates programmatically (Back, Next paper buttons).
 */
export function useUnsavedChanges(dirty: boolean, message = MESSAGE): () => boolean {
  useEffect(() => {
    if (!dirty) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
      const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null
      if (!a || a.target === '_blank' || a.hasAttribute('download')) return
      const url = new URL(a.href, window.location.href)
      if (url.origin !== window.location.origin) return
      if (url.pathname === window.location.pathname && url.hash) return // a jump within this page
      if (!window.confirm(message)) {
        e.preventDefault()
        e.stopPropagation()
      }
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    document.addEventListener('click', onClick, true)
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      document.removeEventListener('click', onClick, true)
    }
  }, [dirty, message])
  return useCallback(() => !dirty || window.confirm(message), [dirty, message])
}
