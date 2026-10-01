// Shared API types. Mirrors apps/api/app/models.py.

export type Subject = 'math' | 'science' | 'grammar'
export type FeedbackStyle = 'hint_only' | 'full_solution'
export type Verdict = 'correct' | 'error' | 'unclear'
export type SubmissionStatus = 'uploaded' | 'grading' | 'needs_review' | 'ready' | 'approved' | 'failed'
export type QueueTab = 'needs_review' | 'ready' | 'approved' | 'all'
export type Flag =
  | 'unclear_handwriting'
  | 'step_mismatch'
  | 'alternate_method'
  | 'low_confidence_final_answer'
  | 'grading_failed'

export interface Criterion {
  name: string
  description: string
  points: number
}

export interface ActivitySettings {
  accept_alternate: boolean
  require_units: boolean
  feedback_style: FeedbackStyle
}

export interface Problem {
  id: string
  order: number
  text: string
  expected_answer: string
  sample_solution: string
  rule: string
}

export interface ActivitySummary {
  id: string
  title: string
  subject: Subject
  class_name: string
  date: string
  total_points: number
  papers: number
  to_review: number
  flagged: number
  approved: number
  roster_size: number
  not_submitted: number
  unidentified: number
  updated_at: string
}

export interface Activity extends ActivitySummary {
  settings: ActivitySettings
  problems: Problem[]
  rubric: Criterion[]
}

export interface ActivityInput {
  title: string
  subject: Subject
  class_name: string
  date: string
  settings: ActivitySettings
  problems: Omit<Problem, 'id'>[]
  rubric: Criterion[]
}

export interface RubricTemplate {
  id: string
  name: string
  subject: Subject
  criteria: Criterion[]
}

export interface StatDelta {
  value: number
  delta: number
}

export interface Dashboard {
  activity_id: string | null
  awaiting_review: StatDelta
  flagged: StatDelta
  approved_today: StatDelta
  class_average: { value: number; out_of: number; delta_pct: number }
  queue_badge: number
}

export interface Unit {
  index: number
  transcribed_text: string
  alt_reading: string | null
  verdict: Verdict
  error_type: string | null
  criterion: string
  points_awarded: number
  points_max: number
  confidence: number
  comment: string
  bbox: [number, number, number, number] | null
}

export interface ProblemResult {
  problem_id: string
  expected_answer: string
  student_answer?: string
  units: (Unit & { edited?: boolean })[]
  suggested_score: number
  ai_suggested_score: number
  criteria_scores: { name: string; awarded: number; points: number }[]
  max_score: number
  overall_confidence: number
  flags: Flag[]
  student_hint: string
}

export interface AiResult {
  problems: ProblemResult[]
  suggested_score: number
  max_score: number
  overall_confidence: number
  flags: Flag[]
  model: string
  prompt_version: string
  created_at: string
  failure_reason?: string | null
}

export interface UnitEdit {
  points_awarded?: number
  transcribed_text?: string
  verdict?: Verdict
  error_type?: string | null
  comment?: string
}

export interface EditLogEntry {
  at: string
  field: string
  from: unknown
  to: unknown
}

export interface Review {
  unit_edits: Record<string, UnitEdit> // key: `${problem_id}:${unit_index}`
  problem_scores: Record<string, number> // teacher-typed final score per problem
  feedback: Record<string, string> // per problem
  edit_log: EditLogEntry[]
  final_score: number | null
  approved: boolean
  approved_at: string | null
  updated_at: string | null
}

export interface QueueRow {
  submission_id: string
  student_id: string | null
  student_name: string | null
  status: SubmissionStatus
  focus_problem_id: string | null
  focus_problem_order: number | null
  score: number | null
  score_max: number
  confidence: number | null
  chips: string[]
}

export interface Queue {
  activity: ActivitySummary
  counts: Record<QueueTab, number>
  rows: QueueRow[]
}

export interface Identity {
  status?: 'matched' | 'unidentified' | 'pending' | 'manual'
  method?: 'id' | 'name' | 'teacher' | 'teacher_upload' | null
  extracted_name?: string | null
  extracted_id?: string | null
  identity_confidence?: number
  suggested_student_id?: string | null
  reason?: string | null
}

export interface RosterStudent {
  id: string
  name: string
  has_paper: boolean
}

export interface SubmissionDetail {
  id: string
  student_id: string | null
  student_name: string | null
  identity: Identity
  roster: RosterStudent[]
  status: SubmissionStatus
  image_url: string | null
  image_deleted: boolean
  activity: Activity
  ai_result: AiResult | null
  review: Review
  next_submission: { id: string; student_id: string | null; student_name: string | null } | null
  focus_problem_id: string | null
}

export interface UploadedPaper {
  id: string
  student_id: string | null
  student_name: string | null
  status: SubmissionStatus
  image_url: string | null
  quality: { ok: boolean; reason: string | null } | null
}

export interface GradingProgress {
  total: number
  done: number
  running: boolean
  items: { submission_id: string; student_id: string | null; student_name: string | null; state: 'done' | 'checking' | 'waiting' | 'failed' }[]
}

export interface Misconception {
  text: string
  error_type: string
  count: number
  problems: string[]
}

export interface ClassSummary {
  activity: ActivitySummary
  approved: number
  students: number
  average_score: number
  out_of: number
  most_missed_criterion: string | null
  errors_by_type: { error_type: string; label: string; count: number }[]
  per_problem: { label: string; average: number }[]
  misconceptions: Misconception[]
  submissions: { submitted: number; not_submitted: RosterStatusRow[]; unidentified: number }
  reteach_focus: string
  ai_model: string | null
}

export interface RosterStatusRow {
  student_id: string
  student_name: string
  submission_id: string | null
  status: string
}

export interface GradebookRow {
  student_id: string | null
  student_name: string | null
  status: string
  submission_id: string | null
  scores: (number | null)[]
  edited: boolean[]
  total: number | null
  just_approved: boolean
}

export interface Gradebook {
  activity: ActivitySummary
  columns: string[]
  rows: GradebookRow[]
}

export interface ParentMessage {
  en: string
  fil: string
  model: string
  approved: boolean
}

export interface AppNotification {
  id: string
  kind: 'grading_done' | 'needs_review' | 'grading_failed' | 'regrade_ok' | 'upload_done'
  title: string
  body: string
  link: string | null
  read: boolean
  created_at: string
}

export interface Notifications {
  unread: number
  items: AppNotification[]
}

export interface AppSettings {
  confidence_threshold: number
  default_feedback_style: FeedbackStyle
  default_accept_alternate: boolean
  default_rubric_mode: 'manual' | 'ai'
  delete_images_on_approve: boolean
  ai: { provider: string; model: string; configured: boolean; demo_mode: boolean }
  rerouted?: number
}

export interface Profile {
  name: string
  department: string
  title: string
  email: string
  role: string
  account_status: string
  activities: number
  classes: string[]
  students: number
}

export interface RubricDraft {
  criteria: Criterion[]
  points_per_problem: number
  model: string
  prompt_version: string
  draft: true
}
