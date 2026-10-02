import type {
  Activity,
  AppSettings,
  Notifications,
  Profile,
  RubricDraft,
  RosterStatusRow,
  ActivityInput,
  ActivitySummary,
  ClassSummary,
  Dashboard,
  Gradebook,
  GradingProgress,
  ParentMessage,
  Queue,
  QueueTab,
  Review,
  RubricTemplate,
  SubmissionDetail,
  UploadedPaper,
} from './types'
import { getToken, signOut, type Teacher } from './session'

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Called when the API says the session is missing, expired, or signed out. */
function sessionEnded() {
  signOut()
  if (window.location.pathname !== '/signin') {
    window.location.assign(`/signin?expired=1&from=${encodeURIComponent(window.location.pathname + window.location.search)}`)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  const token = getToken()
  const headers = new Headers(init?.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers })
  } catch {
    // Teacher-facing: no URLs or server terms.
    throw new ApiError(0, "TsekMate can't connect right now. Check your internet connection and try again.")
  }
  if (res.status === 401 && path !== '/api/auth/signin') {
    sessionEnded()
    throw new ApiError(401, 'Your session has ended. Please sign in again.')
  }
  if (!res.ok) {
    let message = res.status >= 500 ? 'Something went wrong on our side. Please try again.' : 'That request could not be completed. Please try again.'
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = 'Some fields are missing or not valid. Check the form and try again.'
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  signIn: (email: string, password: string) => request<Teacher>('/api/auth/signin', json('POST', { email, password })),
  signOut: () => request<void>('/api/auth/signout', { method: 'POST' }),
  me: () => request<{ name: string; email: string; class_name: string; expires_at: number }>('/api/auth/me'),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  activities: () => request<ActivitySummary[]>('/api/activities'),
  activity: (id: string) => request<Activity>(`/api/activities/${id}`),
  createActivity: (input: ActivityInput) => request<Activity>('/api/activities', json('POST', input)),
  updateRubric: (activityId: string, criteria: Activity['rubric'], totalPoints: number | null) =>
    request<Activity>(`/api/activities/${activityId}/rubric`, json('PATCH', { criteria, total_points: totalPoints })),
  rubricTemplates: () => request<RubricTemplate[]>('/api/rubric-templates'),
  submissions: (activityId: string) => request<UploadedPaper[]>(`/api/activities/${activityId}/submissions`),
  upload: (activityId: string, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<UploadedPaper[]>(`/api/activities/${activityId}/submissions`, { method: 'POST', body: form })
  },
  deleteSubmission: (id: string) => request<void>(`/api/submissions/${id}`, { method: 'DELETE' }),
  startGrading: (activityId: string) => request<GradingProgress>(`/api/activities/${activityId}/grade`, { method: 'POST' }),
  gradingProgress: (activityId: string) => request<GradingProgress>(`/api/activities/${activityId}/grading-progress`),
  queue: (activityId: string, tab: QueueTab) => request<Queue>(`/api/activities/${activityId}/queue?tab=${tab}`),
  submission: (id: string) => request<SubmissionDetail>(`/api/submissions/${id}`),
  saveReview: (id: string, patch: { unit_edits?: Review['unit_edits']; criterion_scores?: Record<string, number | null>; feedback?: Review['feedback'] }) =>
    request<SubmissionDetail>(`/api/submissions/${id}/review`, json('PATCH', patch)),
  approve: (id: string) =>
    request<{ submission: SubmissionDetail; final_score: number; max_score: number }>(`/api/submissions/${id}/approve`, {
      method: 'POST',
    }),
  classSummary: (activityId: string) => request<ClassSummary>(`/api/activities/${activityId}/class-summary`),
  refreshClassSummary: (activityId: string) => request<ClassSummary>(`/api/activities/${activityId}/class-summary/refresh`, { method: 'POST' }),
  practice: (activityId: string) =>
    request<{ items: string[] }>(`/api/activities/${activityId}/practice`, { method: 'POST' }),
  gradebook: (activityId: string) => request<Gradebook>(`/api/activities/${activityId}/gradebook`),
  sendToSchool: (activityId: string) =>
    request<{ accepted: number; note: string }>('/adapter/grades/draft', json('POST', { activity_id: activityId })),
  savedParentMessage: (id: string) => request<ParentMessage>(`/api/submissions/${id}/parent-message`),
  parentMessage: (id: string) => request<ParentMessage>(`/api/submissions/${id}/parent-message`, { method: 'POST' }),
  regrade: (id: string) => request<GradingProgress>(`/api/submissions/${id}/regrade`, { method: 'POST' }),
  assignStudent: (id: string, studentId: string) => request<SubmissionDetail>(`/api/submissions/${id}/student`, json('PATCH', { student_id: studentId })),
  roster: (activityId: string) => request<{ activity: ActivitySummary; students: RosterStatusRow[] }>(`/api/activities/${activityId}/roster`),
  generateRubric: (body: { subject: string; title: string; problems: { text: string; expected_answer: string; rule: string }[]; learning_outcome: string; points_per_problem: number }) =>
    request<RubricDraft>('/api/rubric/generate', json('POST', body)),
  notifications: () => request<Notifications>('/api/notifications'),
  readNotification: (id: string) => request<Notifications>(`/api/notifications/${id}/read`, { method: 'POST' }),
  readAllNotifications: () => request<Notifications>('/api/notifications/read-all', { method: 'POST' }),
  settings: () => request<AppSettings>('/api/settings'),
  saveSettings: (patch: Partial<Omit<AppSettings, 'ai'>>) => request<AppSettings>('/api/settings', json('PATCH', patch)),
  profile: () => request<Profile>('/api/profile'),
  saveProfile: (patch: { name?: string; department?: string }) => request<Profile>('/api/profile', json('PATCH', patch)),
  approveParentMessage: (id: string, language: 'en' | 'fil', text: string) =>
    request<{ sent: boolean; note: string }>(`/api/submissions/${id}/parent-message/approve`, json('POST', { language, text })),
}

/** Log out on the server (the token stops working everywhere), then forget it in this browser. */
export async function logOut() {
  try {
    if (getToken()) await api.signOut()
  } catch {
    /* already signed out or offline: the local session is cleared either way */
  } finally {
    signOut()
  }
}
