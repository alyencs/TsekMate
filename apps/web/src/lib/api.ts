import type {
  Activity,
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

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, init)
  } catch {
    throw new ApiError(0, `Cannot reach the TsekMate API at ${API_URL}. Is the server running?`)
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
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
  signIn: (email: string, password: string) =>
    request<{ name: string; email: string; class_name: string }>('/api/auth/signin', json('POST', { email, password })),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  activities: () => request<ActivitySummary[]>('/api/activities'),
  activity: (id: string) => request<Activity>(`/api/activities/${id}`),
  createActivity: (input: ActivityInput) => request<Activity>('/api/activities', json('POST', input)),
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
  saveReview: (id: string, patch: Partial<Pick<Review, 'unit_edits' | 'problem_scores' | 'feedback'>>) =>
    request<SubmissionDetail>(`/api/submissions/${id}/review`, json('PATCH', patch)),
  approve: (id: string) =>
    request<{ submission: SubmissionDetail; final_score: number; max_score: number }>(`/api/submissions/${id}/approve`, {
      method: 'POST',
    }),
  classSummary: (activityId: string) => request<ClassSummary>(`/api/activities/${activityId}/class-summary`),
  practice: (activityId: string) =>
    request<{ items: string[]; model: string }>(`/api/activities/${activityId}/practice`, { method: 'POST' }),
  gradebook: (activityId: string) => request<Gradebook>(`/api/activities/${activityId}/gradebook`),
  sendToSchool: (activityId: string) =>
    request<{ accepted: number; note: string }>('/adapter/grades/draft', json('POST', { activity_id: activityId })),
  parentMessage: (id: string) => request<ParentMessage>(`/api/submissions/${id}/parent-message`, { method: 'POST' }),
  approveParentMessage: (id: string, language: 'en' | 'fil', text: string) =>
    request<{ sent: boolean; note: string }>(`/api/submissions/${id}/parent-message/approve`, json('POST', { language, text })),
}
