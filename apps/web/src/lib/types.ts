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
  rubric_total: number // points per problem; equals the sum of the criteria
  rubric_errors: string[] // why the rubric can't be used for grading yet (empty = ready)
  rubric_locked: boolean // true once any paper is graded: one rubric scores the whole class
}

export interface ActivityInput {
  title: string
  subject: Subject
  class_name: string
  date: string
  settings: ActivitySettings
  problems: Omit<Problem, 'id'>[]
  rubric: Criterion[]
  rubric_total: number | null
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
  /** Every criterion of the activity rubric, in rubric order. `final_score` is the sum of `awarded`. */
  criteria_scores: CriterionScore[]
  final_score: number
  max_score: number
  overall_confidence: number
  flags: Flag[]
  student_hint: string
}

export interface CriterionScore {
  name: string
  description: string
  awarded: number
  points: number // the rubric's points for this criterion
  computed: number // what the AI's marks add up to
  assessed: boolean // false: the AI did not score this criterion; the teacher should
  edited: boolean // the teacher typed this score
}

export interface AiResult {
  problems: ProblemResult[]
  suggested_score: number
  max_score: number
  overall_confidence: number
  flags: Flag[]
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
  criterion_scores: Record<string, number> // key: `${problem_id}::${criterion name}`
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
  /** Set while Saver grading runs (half price, results usually within an hour). */
  saver: SaverStatus | null
}

export interface SaverStatus {
  submitted_at: string
  /** Seconds left (estimate); null once it is taking longer than estimated. */
  eta_seconds: number | null
  eta_basis: 'progress' | 'history' | 'typical'
  overdue: boolean
  /** Latest finish time (24 hours after sending). */
  deadline: string
  in_batch: number
}

export type GradingMode = 'fast' | 'saver'

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
  grading_mode: GradingMode
  ai: { available: boolean; demo_mode: boolean }
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
  problems: string[] // why the drafted points can't be used as they are (the teacher fixes them)
  draft: true
}
