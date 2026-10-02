const KEY = 'tsekmate.session'

/**
 * The signed-in teacher as returned by the API's sign-in. `token` is the bearer token the API checks on every request;
 * this stored copy only decides which screens to show. The API refuses expired or signed-out tokens, and a 401 sends
 * the teacher back to the sign-in page (see api.ts).
 */
export interface Teacher {
  name: string
  email: string
  class_name: string
  token: string
  expires_at: number // unix seconds
}

export function getTeacher(): Teacher | null {
  try {
    const raw = localStorage.getItem(KEY) ?? sessionStorage.getItem(KEY)
    const t = raw ? (JSON.parse(raw) as Partial<Teacher>) : null
    // Sessions saved before sign-in returned a token, or past their expiry, are not sessions.
    if (!t || typeof t.token !== 'string' || !t.token || !t.expires_at || t.expires_at * 1000 <= Date.now()) return null
    return t as Teacher
  } catch {
    return null
  }
}

export function getToken(): string | null {
  return getTeacher()?.token ?? null
}

export function setTeacher(t: Teacher, remember: boolean) {
  try {
    ;(remember ? localStorage : sessionStorage).setItem(KEY, JSON.stringify(t))
  } catch {
    /* storage blocked; session lasts for this page only */
  }
}

export function signOut() {
  try {
    localStorage.removeItem(KEY)
    sessionStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}

/** Remembers the last activity the teacher worked on, so sidebar links land somewhere useful. */
export function lastActivity(): string | null {
  try {
    return localStorage.getItem('tsekmate.lastActivity')
  } catch {
    return null
  }
}
export function rememberActivity(id: string) {
  try {
    localStorage.setItem('tsekmate.lastActivity', id)
  } catch {
    /* ignore */
  }
}
