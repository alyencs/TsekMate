const KEY = 'tsekmate.session'

export interface Teacher {
  name: string
  email: string
  class_name: string
}

export function getTeacher(): Teacher | null {
  try {
    const raw = localStorage.getItem(KEY) ?? sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Teacher) : null
  } catch {
    return null
  }
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
