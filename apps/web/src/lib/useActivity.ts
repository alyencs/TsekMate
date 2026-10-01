import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from './api'
import { lastActivity, rememberActivity } from './session'

/** Resolves the activity for pages that work on one activity: ?activity=, else the last one used, else the dashboard's. */
export function useActivityId(): [string | null, (id: string) => void, string | null] {
  const [params, setParams] = useSearchParams()
  const fromUrl = params.get('activity')
  const [resolved, setResolved] = useState<string | null>(fromUrl ?? lastActivity())
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (fromUrl) {
      setResolved(fromUrl)
      rememberActivity(fromUrl)
      return
    }
    if (resolved) return
    api
      .dashboard()
      .then((d) => setResolved(d.activity_id))
      .catch((e: Error) => setError(e.message))
  }, [fromUrl, resolved])
  const set = (id: string) => {
    rememberActivity(id)
    const next = new URLSearchParams(params)
    next.set('activity', id)
    setParams(next, { replace: true })
  }
  return [resolved, set, error]
}
