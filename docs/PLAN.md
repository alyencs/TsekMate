# TsekMate build plan (24-hour prototype)

Sources: `docs/TsekMate Project Document (24-hour build).html` (tech, scope, AI design, privacy) and
`docs/mockups/TsekMate/*` (UI source of truth). All 18 mockup images were reviewed.

## 0. Mockup inventory vs. brief

The zip uses different frame numbers from the brief and has no "00 Components" or "03 Activities" frame.

| Brief frame | Mockup file | Notes |
|---|---|---|
| 00 Components | (none) | Components are taken from the screens themselves |
| 01 Sign In | `01 Sign In.png` | |
| 02 Dashboard | `02 Dashboard.png` | |
| 03 Activities | (none) | Reuses the Dashboard "Your activities" card as a full page |
| 04A/B/C Create Activity | `03A/B/C Create Activity (...)` | One screen, subject-driven |
| 05 Upload Student Work | `04 Upload Student Work.jpg` | |
| 06 Grading In Progress | `05 Grading In Progress.png` | |
| 07 Review Queue | `06 Review Queue.png` | |
| 08A/B/C Review Detail | `07A/B/C Review Detail (...)` | One screen, subject-driven |
| 08D Approval Confirmation | `07D Approval Confirmation.png` | Modal over the review detail |
| 09A/B/C Class Summary | `08A/B/C Class Summary (...)` | One screen, subject-driven |
| 10 Gradebook (mock) | `09 Gradebook (mock).png` | |
| 11 Parent Update Draft | `10 Parent Update Draft (STRETCH).png` | Stretch |
| 12 Student Feedback View | `11 Student Feedback View (STRETCH).png` | Stretch, no app shell |

### Interpretation decisions (closest reasonable choice, will repeat in final summary)

1. **Score granularity.** The review detail grades one problem at a time (problem tabs 1..5 at the top), and the score
   card shows that problem's score out of 10. The queue row, approval modal, and student view also show "x / 10".
   Decision: review detail, approval modal, student view, and gradebook cells are **per problem** (matching the mockup).
   The queue "Suggested score" column shows the **score of the paper's lowest-confidence problem** (the problem the teacher
   lands on when they click Review), which is the problem that reproduces "5 / 10" for S-014. Paper totals (out of 50/40)
   are used for the class average and the dashboard. Approval approves the whole paper (all problems), so the approval
   modal shows the **paper total** (for example "45 / 50"), not the mockup's per-problem "6 / 10"; a one-line note under
   the Approve button says that approval covers every problem on the paper.
2. **Confidence bar color.** Mockup shows green at or above 75 % and amber below (the brief said orange). Images win: green
   (`#16A34A`) at >= 75 %, amber (`#CA8A04`) below.
3. **Mockup template bugs** (`S-0{{i+24}}`, `{{8+Math.floor(...)}}` in queue and gradebook) are rendered as real data rows.
4. **Dashboard stat cards** (12 awaiting, 9 flagged, 26 approved today, 38/50 average) match the Math quiz only, while the
   table lists 4 activities. Decision: stat cards are scoped to the most recently updated active activity, with deltas
   computed from seeded timestamps (today vs. yesterday). The sidebar Review Queue badge shows flagged papers across all
   activities (seed gives Math 9 + Science 5 + Grammar 7 = 21, matching the mockup badge).
5. **Activities page** (no frame): the Dashboard "Your activities" card on its own page, with the same chips and table.
6. **Create Activity stepper** (Details / Problems and key / Rubric) is a scroll-spy indicator over one long form, which is
   what the mockup shows (all three sections on one page). "Items and key" label for Grammar.
7. **Gradebook column count** follows the selected activity (P1..P5, or I1..I5 for Grammar); the table scrolls horizontally.
   The P4/P5 columns are off-screen in the mockup.
8. **"Generate practice problems"** button on Class Summary: generates 2-3 practice problems for the **teacher** (one LLM call),
   shown in a dialog labeled as an AI draft. This is not a student homework solver. If time runs short it is cut first
   (it is not in the brief's must-have list).
9. **Export summary / Export CSV**: client-side CSV download. **Send to school system**: calls the mock adapter
   `POST /adapter/grades/draft`.
10. **Sign In** is a single demo teacher account (Ms. Reyes). No real auth; the session is a local flag.
11. **Upload screen "Retake suggested / Image is blurry"** is the image quality check (stretch). Before it is built, every
    card shows "Ready".
12. **Review Queue sidebar item** is highlighted for Upload, Grading, Queue, and Review Detail (as in the mockups).

## 1. Routes and components

| Route | Frame | Main components |
|---|---|---|
| `/signin` | 01 | `SignInPage`, `GradeCardIllustration` |
| `/` | 02 | `AppShell`, `StatCard`, `ActivitiesTable`, `SubjectChip`, `FilterChips`, `Pagination` |
| `/activities` | 03 (none) | `ActivitiesTable` |
| `/activities/new` | 04A/B/C | `Stepper`, `SubjectPicker`, `ProblemEditor` (expanded/collapsed), `RubricTable`, `Toggle`, `RadioCard` |
| `/activities/:id/upload` | 05 | `ActivityPicker`, `Dropzone`, `PaperThumb`, `StickyFooterBar` |
| `/activities/:id/grading` | 06 | `ProgressBar`, `GradingRow` (Done / Checking / Waiting), aria-live |
| `/queue?activity=:id&tab=` | 07 | `Tabs`, `FilterSelect`, `QueueTable`, `ConfidenceBar`, `FlagChip`, `StatusLabel` |
| `/submissions/:id?p=n` | 08A/B/C + 08D | `ProblemTabs`, `ImageViewer` (zoom, rotate, bbox overlays), `ProblemHeader`, `UnitCard` (correct/error/unclear), `RubricRecap` (grammar), `ScoreCard`, `ReviewRecord`, `ApprovalModal` |
| `/class-summary?activity=:id` | 09A/B/C | `StatCard`, `ErrorsByTypeChart`, `PerProblemChart` (recharts), `MisconceptionCard`, `InsightCard` |
| `/gradebook?activity=:id` | 10 | `GradebookTable`, "Just approved" and "Edited" badges |
| `/submissions/:id/parent-message` | 11 (stretch) | `SegmentedControl`, `MessagePreview` |
| `/feedback/:id?p=n` | 12 (stretch) | `StudentFeedbackCard`, Web Speech TTS |

Shared UI kit (`apps/web/src/components/ui`): `Button` (primary, secondary, ghost, link), `Input`, `Select`, `Textarea`,
`Card`, `Chip`/`Badge` (subject, status, flag, error type), `Toggle`, `RadioCard`, `Tabs`, `ConfidenceBar`, `StatusPill`
(icon + text + color), `AiDraftLabel` ("AI-assisted draft, reviewed by your teacher"), `Spinner`, `EmptyState`,
`ErrorState`, `Modal`. Icons: lucide-react. Subject config lives in one file (`subjects.ts`) and drives labels, icons, error
types, unit names ("Step" / "Correction"), and problem names ("Problem" / "Item").

## 2. Database tables (Supabase / PostgreSQL)

SQL in `apps/api/db/schema.sql`. Private bucket `submissions` for images (signed URLs only).

| Table | Key columns |
|---|---|
| `students` | `id` text pk (`S-001`..`S-038`), `section` |
| `activities` | `id` uuid, `title`, `subject` (math, science, grammar), `class_name`, `date`, `settings` jsonb, `total_points`, `created_at`, `updated_at` |
| `problems` | `id`, `activity_id`, `order`, `text`, `expected_answer`, `sample_solution`, `rule` (grammar) |
| `rubrics` | `id`, `activity_id`, `criteria` jsonb (`[{name, description, points}]`) |
| `rubric_templates` | `id`, `name`, `subject`, `criteria` jsonb |
| `submissions` | `id`, `activity_id`, `student_id`, `image_path`, `image_hash`, `status` (uploaded, grading, needs_review, ready, approved, failed), `quality` jsonb, timestamps |
| `ai_results` | `id`, `submission_id`, `problem_results` jsonb, `suggested_score`, `overall_confidence`, `flags` text[], `model`, `prompt_version`, `raw_json` jsonb, `created_at` |
| `teacher_reviews` | `id`, `submission_id`, `final_score`, `unit_edits` jsonb, `criterion_scores` jsonb (was `problem_scores`), `feedback` jsonb, `edit_log` jsonb, `approved`, `approved_at`, timestamps |
| `class_summaries` | `activity_id`, `misconceptions` jsonb, `reteach_focus`, `model`, `prompt_version` (cache of the one LLM call) |
| `parent_messages` (stretch) | `id`, `submission_id`, `language`, `text`, `approved`, `sent_at` |

Storage abstraction (`apps/api/app/store`): `SupabaseStore` (supabase-py, used whenever `SUPABASE_URL` is set) and
`MemoryStore` (in-process, used for tests and for running locally before the Supabase project exists). Same interface,
same seed. This is not a second database; it is a test double.

Seed (`python scripts/seed.py --reset`): 38 students, 4 activities (Linear Equations, Forces and Motion, Subject-Verb
Agreement, Fractions Review), 4 rubric templates, pre-graded results that reproduce the mockup numbers: Math 9 needs
review / 3 ready / 26 approved, Science 7 to review / 31 approved, Grammar 10 to review / 28 approved, Fractions all 35
approved; S-014, S-022, S-031 exactly as in the review detail frames; class summary charts and gradebook rows.

## 3. API (FastAPI, `apps/api`)

| Method and path | Purpose |
|---|---|
| `POST /api/auth/signin` | Demo teacher sign-in (one account) |
| `GET /api/dashboard` | Stat cards, deltas, sidebar badge |
| `GET/POST /api/activities`, `GET /api/activities/{id}` | Activities with problems, rubric, settings |
| `GET /api/rubric-templates` | Template dropdown |
| `POST /api/activities/{id}/submissions` | Multipart images, assigns next pseudonymous IDs, stores in private bucket |
| `GET /api/activities/{id}/submissions` | Uploaded papers (upload screen) |
| `DELETE /api/submissions/{id}` | Remove an uploaded paper before grading |
| `POST /api/activities/{id}/grade` | Background batch grading |
| `GET /api/activities/{id}/grading-progress` | Done / checking / waiting per paper |
| `GET /api/activities/{id}/queue?tab=` | needs_review, ready, approved, all; lowest confidence first |
| `GET /api/submissions/{id}` | Detail, signed image URL, AI result, review state, next paper |
| `PATCH /api/submissions/{id}/review` | Transcript, verdict, per-criterion scores, feedback edits; every edit logged |
| `POST /api/submissions/{id}/approve` | Writes to the gradebook; optional image delete |
| `GET /api/activities/{id}/class-summary` | Code counts + cached LLM misconceptions and reteach focus |
| `POST /api/activities/{id}/practice` | Teacher practice problems (item 8 above) |
| `GET /api/activities/{id}/gradebook` | Mock gradebook rows |
| `POST /api/submissions/{id}/parent-message` | Stretch: EN + FIL draft |
| `GET /adapter/activities`, `GET /adapter/submissions`, `POST /adapter/grades/draft`, `POST /adapter/notifications` | Mock adapter (not an official integration) |

## 4. AI core

- `apps/api/prompts/grade_v1.0.txt` (system) + activity context; one vision call per paper; JSON only.
- Pydantic schema `PaperResult` (list of `ProblemResult` with `units`), retry once with validation error, else
  status `failed`, flag `grading_failed`.
- Deterministic post-processing (`app/grading/scoring.py`): clamp points, recompute per-problem and per-criterion sums,
  routing (`needs_review` vs. `ready`), queue sort.
- Store model, prompt version, timestamp, raw JSON. `DEMO_MODE=true` returns cached results by image SHA-256 from
  `samples/cache/`.
- Class summary: counts from code; one LLM call (`prompts/summary_v1.0.txt`) names misconceptions and the reteach focus.

## 5. Order of work (commit after each phase)

- **A**: repo layout, `.env.example`, Vite + Tailwind tokens, UI kit, app shell, Sign In.
- **B**: schema SQL, store layer, seed + reset, activities API, Create Activity, Dashboard, Activities.
- **C**: prompt, schema, validation, scoring/routing, `scripts/grade.py`, synthetic smoke images. Checkpoint (a) needs an API key.
- **D**: upload, grading progress, review queue, review detail, approve, gradebook. Checkpoint (b).
- **E**: class summary, Science and Grammar variants, seed polish.
- **F**: `scripts/evaluate.py` + report; stretch in priority order (image quality check, parent message, TTS, SymPy); deploy config.
- **G**: README, demo mode, bug fixes.

## 6. Needed from the team

- `ANTHROPIC_API_KEY` (checkpoint (a) and live grading are blocked without it).
- A Supabase project (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`); until then the app runs on `MemoryStore`.
- The handwritten sample photos and ground truth in `samples/`.

## 7. Decisions made during the build

- **Seed numbers.** Queue counts, flags, S-014/S-022/S-031, error-type counts (Math 12/18/5/3, Science 10/9/22/4),
  misconception counts (14, 9, 18, 9, 19, 11), most missed criterion, deltas (+3, +2, +8), and the badge (21) match the
  mockup. The mockup's class averages (38/50, 33/40, 36/50) and per-problem bars are not consistent with its own error
  counts, so the seed computes them honestly from the seeded papers (Math is about 44/50). Grammar "Grammar rule" errors
  come out at 32, not 24, for the same reason.
- **Grammar units.** Each error in the sentence is a "Finds the errors" correction unit (3 points shared), plus one
  "Correct revision" unit, one "Rule explanation" unit, and one "Spelling check" unit. The mockup labels corrections 2 and 3
  "Correct revision"; ours label them "Finds the errors" so the rubric recap adds up (2/3, 3/4, 2/2, 1/1 = 8 for S-031).
- **Most missed criterion** = the criterion with the most root-cause error steps (steps with an error type).
- **Stretch screen entry points.** Approved papers show "Parent update" and "Student view" buttons in the review top bar
  (the mockup has no other way to reach those screens).
- **Flag button** on the review screen leaves the paper flagged and opens the next paper.
- **Storage.** `MemoryStore` is used when Supabase is not configured; Supabase code is written against the same
  interface but was not run in this environment (no project credentials).

## 8. AI provider change: Anthropic Claude to Google Gemini

The team switched the AI provider to Google Gemini so development and testing can use the Gemini API free tier
(Gemini is on the hackathon's allowed list). Only the provider seam changed: `apps/api/app/grading/llm.py` now calls
`google-genai` (`gemini-2.5-flash` by default, JSON output mode, inline image bytes). Prompts, Pydantic validation, the
retry-once rule, score recompute, routing, API endpoints, database, and UI are unchanged. Env var: `GEMINI_API_KEY`
(replaces `ANTHROPIC_API_KEY`). The optional "Gemini comparison" stretch item no longer applies.

## 9. Provider back to Anthropic Claude (Claude Haiku) and feature round 2

**Provider.** The live AI provider is Anthropic Claude again, model `claude-haiku-4-5` (Claude Haiku 4.5), through the
official `anthropic` Python SDK, configured with `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. Section 8 is kept as history:
the Gemini integration was built and only tested with invalid keys; no live Gemini grading was run. The grading
architecture is unchanged (one vision call per paper, JSON, Pydantic, retry once, code recompute, routing, review).

**Features.** Grade again (`POST /api/submissions/{id}/regrade`); optional AI rubric draft (`POST /api/rubric/generate`,
prompt `rubric_v1.0.txt`, never auto-applied; points no longer normalized since section 11); notifications from real events; profile and
settings pages (settings persisted in `app_settings`; reduce motion stored locally); class roster with names; identity
reading added to the single grading call (prompt `grade_v1.1.txt`), conservative roster matching
(`app/services/roster.py`), manual assignment (`PATCH /api/submissions/{id}/student`), Not submitted / Not identified
tracking; college sample data; lighter layout and subtle animations.

**Decisions.**
- Uploads no longer take the "next free" student ID. Papers start unidentified and get their student from the name/ID
  on the paper after grading (or from the teacher). An unidentified paper is still graded in full but routed to Needs
  review, and approval requires a student.
- Identity confidence is separate from grading confidence. Auto-match needs identity confidence >= 0.5 and either an
  exact roster ID or a clear name match (similarity >= 0.86, clearly ahead of the next name); conflicts and duplicates
  stay unidentified with a suggested student.
- Seed: roster of 40 (BS Computer Science 2A) with 38 papers per activity; 2026-039 and 2026-040 did not submit; the
  Math paper of 2026-036 has no readable name, to demo "Not identified" and assignment. Queue counts (9 / 3 / 26) and the
  dashboard numbers stay as before. Misconception counts now read "14 of 40" because the roster has 40 students.
- Migration `apps/api/db/migrations/002_roster_identity_notifications_settings.sql` (additive, idempotent).

## 11. Rubric-exact scoring and teacher-facing text

**Problem found.** A custom rubric could show the wrong breakdown on the Review screen: the AI sometimes skipped a
criterion (silently 0 and not shown, because the screen listed the AI's steps, not the rubric) and its per-step maximum
was trusted (Method showed /2 for a 3-point criterion). New activities also started with a template rubric filled in.

**Changes.**
- Rubric empty by default; required "total points per problem"; criteria must add up to it (`scoring.rubric_problems`,
  checked in the form, on save, on rubric edit, and before grading). Nothing is normalized, truncated, or invented; the
  AI rubric draft is no longer rescaled.
- `rubrics.total_points`; `PATCH /api/activities/{id}/rubric` until the first paper is graded, then locked.
- Scoring in code: step maximum = criterion points; `criteria_scores` lists every rubric criterion with `assessed`;
  problem score = sum of criteria. Prompt `grade_v1.2.txt` requires every criterion; a gap is retried once, then left
  at 0 as "Not scored by the AI" (routes to Needs review).
- Teacher edits are per criterion (`criterion_scores`, 0..criterion points), replacing the per-problem override.
  Legacy `problem_scores` are spread over criteria on read and converted on the next edit.
- Teacher-facing text: no model, prompt version, provider, key, or setup terms in any page or API response a teacher
  sees (`LLMError` carries a plain message and a separate `detail` for logs). The "Review record" is replaced by
  "AI-assisted draft — Review the suggested score before approving." Metadata stays stored on the server.
- Migration `003_rubric_total_criterion_scores.sql` (additive, idempotent).

**Tests.** `tests/test_rubric_scoring.py`: 2, 4, 5 criteria = 10, 1 + 2 + 3 + 4, a 20-point and a 5-point rubric, edits,
approval, gradebook and class summary consistency, coverage retry and placeholder, invalid rubrics, locking, legacy
overrides, and no technical text in teacher endpoints. Browser regression with a stand-in Claude client covered the
full flow (37 checks). Live Claude Haiku grading was not run (no API key in this environment).

