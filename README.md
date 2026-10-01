# TsekMate

### Every step checked. Every teacher in control.

TsekMate reads a photo of a student's handwritten work, checks it **step by step against the teacher's rubric**, and
produces a marked-up draft with error types, confidence, and a hint for the student. It also reads the student's name
and ID from the paper and matches the paper to the class roster. The teacher reviews, edits, and approves. Only
approved results reach the gradebook, the student view, and the parent update.

Entry for the **AI in Education Hackathon 2026: "Transforming Education Through Artificial Intelligence."**
Full design: [`docs/TsekMate Project Document (24-hour build).html`](docs/). UI source of truth: [`docs/mockups/`](docs/mockups/).
Build plan, mockup decisions, and change log: [`docs/PLAN.md`](docs/PLAN.md).

> The AI drafts. The teacher decides. Every AI output in the app carries the label
> **"AI-assisted draft, reviewed by your teacher."**

**AI provider: Anthropic Claude, model `claude-haiku-4-5` (Claude Haiku 4.5)**, called only from the FastAPI backend.

---

## What is built

| Tier | Item | Status |
|---|---|---|
| Must have | Photo upload (drag and drop, file picker, phone camera) | Built |
| Must have | One vision call per paper: transcribe + split into steps + grade against the rubric + read the student's name/ID, JSON only | Built |
| Must have | Pydantic validation, one retry with the validation error, then "needs teacher" + `grading_failed` | Built |
| Must have | Error-type tags and confidence per step; scores recomputed in code | Built |
| Must have | Review queue, lowest confidence first, tabs (needs review / ready / approved / all) | Built |
| Must have | Review detail: photo with step boxes, per-step edit, points, final score, feedback, review record | Built |
| Must have | Approve (nothing is saved to the gradebook until then), mock gradebook, CSV export | Built |
| Must have | Class summary: counts from code, one LLM call for misconception names and reteach focus | Built |
| Must have | Activity creation with rubric templates (Math, Science, English Grammar) | Built |
| Must have | Evaluation script and command-line grader | Built (waiting for real samples and an API key) |
| New | **Grade again** for papers whose AI grading failed (same paper, current rubric) | Built |
| New | **Optional AI-generated rubric draft** (manual rubric stays the default) | Built |
| New | **Class roster, student names, identity matching, Not submitted / Not identified tracking** | Built |
| New | **Notifications** (bell), **Profile**, **Settings** | Built |
| New | College sample data, lighter layout, subtle animations (respects reduced motion) | Built |
| Stretch | Image quality check (blur and darkness, "Retake suggested") | Built |
| Stretch | Parent message in English and Filipino, labeled machine draft, teacher approval | Built (needs API key) |
| Stretch | Text-to-speech on the student feedback view (browser Web Speech API) | Built |
| Stretch | SymPy cross-check of algebra steps | Not built |
| Stretch | Second-model comparison | Not built |
| Bonus | Mock school-system adapter (`/adapter/*`) | Built, **not an official integration** |

Three subjects share one pipeline; only the rubric, labels, and error types change:

| Subject | Seeded activity | Rubric (10 pts per problem) | Error types | Unit name |
|---|---|---|---|---|
| Math | College Algebra: Linear Equations Quiz 1 (5 problems) | Setup 2, Method 3, Computation 3, Final answer 2 | computational, conceptual, notation, presentation | Step |
| Science | Physics 1: Forces and Motion Quiz 2 (4 problems) | Formula 2, Substitution 2, Computation 3, Answer with units 3 | computational, conceptual, units_and_notation, presentation | Step |
| English Grammar | Technical Writing: Subject-Verb Agreement Worksheet 3 (5 items) | Finds the errors 3, Correct revision 4, Rule explanation 2, Spelling and punctuation 1 | grammar_rule, spelling, punctuation_capitalization, word_choice | Correction |

---

## Quick start (local)

Requirements: Python 3.11, Node 20+.

```bash
cp .env.example .env            # add ANTHROPIC_API_KEY for live grading; Supabase is optional for a local run

# API
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000      # first start renders the seed images (~10 s), then they are cached

# Web (new terminal)
cd apps/web
npm install
npm run dev                            # http://localhost:5173
```

Sign in with the demo teacher account: **areyes@university.edu.ph / tsekmate** (set in `.env`).

Without `SUPABASE_URL` the API runs on an **in-memory test store** that seeds itself on every start (restart = reset).
Without `ANTHROPIC_API_KEY` everything works except live AI calls: new uploads are marked "Grading failed" with the
reason, the teacher can press **Grade again** once the key is set, or grade by hand. The parent message, practice
problems, and AI rubric draft show a clear error.

### Anthropic Claude setup

TsekMate calls Claude from the **backend only**; the browser never sees the key.

1. Create an API key in the Claude Console (<https://console.anthropic.com/>). API usage is billed per token.
2. Put it in the repo-root `.env` as `ANTHROPIC_API_KEY=...` and keep `ANTHROPIC_MODEL=claude-haiku-4-5`
   (`.env` is gitignored; never use a `VITE_` prefix for it).
3. Restart the API and open `http://localhost:8000/api/health`: it shows `"ai_provider": "anthropic"`, `"ai": "configured"`,
   and the model. Settings in the app shows the same. Then try one paper:
   `python scripts/grade.py samples/synthetic/math-synthetic-01.jpg --activity act-linear-eq-quiz1`.

How it is called: one Messages API request per paper with the photo as a base64 image block (PDFs as a document
block) plus the versioned prompt from `apps/api/prompts/` (`grade_v1.1.txt`), then Pydantic validation, one retry with
the validation error, and code-side score recompute (`apps/api/app/grading/llm.py`, `grader.py`). The SDK retries
429, 5xx, and connection errors with backoff; `GRADING_WORKERS` (default 2) limits parallel calls.

Errors reach the teacher without exposing the key: missing key, rejected key, permission denied, unknown model, rate
limit (HTTP 429), no credit, timeout, connection error, provider outage, refusal, cut-off or malformed JSON (retried
once). A paper that fails is marked **Grading failed** with the reason and a **Grade again** button.

**Troubleshooting: "No module named 'anthropic'" / "The Anthropic Python SDK is not installed".** The API is running
in a Python environment without the SDK (for example one set up while the project briefly used Gemini). Stop the API
and reinstall in the same environment that runs `uvicorn`:

```bash
cd apps/api && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

`/api/health` then reports `"ai": "configured"`. Papers that failed meanwhile can be retried with **Grade again**.

### Supabase

1. Create a project. In the SQL editor run [`apps/api/db/schema.sql`](apps/api/db/schema.sql) (tables, RLS on with no
   public policies, and a **private** `submissions` bucket).
2. **Existing database from an earlier version?** Run
   [`apps/api/db/migrations/002_roster_identity_notifications_settings.sql`](apps/api/db/migrations/) instead. It adds
   `students.name`, makes `submissions.student_id` nullable, adds `submissions.identity`, `ai_results.identity`, and the
   `notifications` and `app_settings` tables. It is safe to run more than once.
3. Put `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (service role, server side only) in `.env`.
4. Seed or reset with one command: `python scripts/seed.py --reset`

### Command-line tools

```bash
python scripts/grade.py samples/math/paper01.jpg --activity act-linear-eq-quiz1   # one paper, prints JSON (incl. identity)
python scripts/seed.py --reset                                                    # reset + seed the database
python scripts/make_synthetic.py        # font-rendered smoke-test papers (never used in the reported evaluation)
python scripts/evaluate.py              # evaluation on samples/{math,science,grammar} -> samples/eval/report.md
python scripts/evaluate.py --write-cache  # same, and store results for DEMO_MODE
cd apps/api && python -m pytest -q      # 41 tests: scoring, routing, schema, retry, Claude adapter, identity, features
```

Seeded activity ids: `act-linear-eq-quiz1`, `act-forces-motion-quiz2`, `act-sva-worksheet3`, `act-fractions-review`.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key (backend only). Required for live grading |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Claude model for grading, rubric drafts, summaries |
| `GRADING_WORKERS` | `2` | Papers graded in parallel |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | (none) | Database and private storage. Empty = in-memory test store |
| `SUPABASE_BUCKET` | `submissions` | Private bucket name |
| `VITE_API_URL` | `http://localhost:8000` | Where the web app finds the API |
| `DELETE_IMAGES_ON_APPROVE` | `false` | Starting value of the Settings toggle "Delete the photo after approval" |
| `DEMO_MODE` | `false` | Use cached AI results (by image SHA-256) from `samples/cache` when present |
| `PUBLIC_API_URL`, `CORS_ORIGINS`, `IMAGE_SIGNING_SECRET` | local values | Signed image links and CORS (`*.vercel.app` is also allowed) |
| `APP_TIMEZONE` | `Asia/Manila` | "Today" for the dashboard |
| `DEMO_TEACHER_EMAIL`, `DEMO_TEACHER_PASSWORD` | demo values | The single teacher account |

Never commit `.env`.

---

## Features added in this round

- **Grade again.** A paper whose AI grading failed (rate limit, timeout, invalid response, missing key, outage) shows the
  reason and a **Grade again** button on the review screen and in the queue. It re-grades the same paper with the
  activity's current rubric and settings, shows the grading progress screen, then returns to that paper. If it fails
  again, the failed state and the button stay. No delete and re-upload needed.
- **AI-generated rubric (optional).** In Create Activity, **Create your own rubric** is the default. **Generate rubric
  with AI** drafts 3 to 5 criteria from the subject, title, problems, answer key, and an optional learning outcome. The
  draft is labeled *AI-generated draft — review and edit before using*, is fully editable, must add up to the chosen
  points per problem (normalized in code), and only replaces the rubric when the teacher clicks **Use this rubric**.
  Discarding returns to the manual rubric. Nothing is saved until **Save activity**.
- **Class roster and student identity.** Each activity's class has a roster (`students` with `section` = class name).
  The single grading call also reads the student name and ID written on the paper (`student_name`, `student_id`,
  `identity_confidence`, separate from grading confidence). Code matches the paper to the roster: exact ID first, then
  a clear name match; low-confidence, conflicting, unknown, or duplicate readings stay **Not identified**. A missing
  name never stops grading: the paper is still graded in full and goes to Needs review until the teacher picks the
  student from the roster on the review screen. Approval requires a student.
- **Submission tracking.** The gradebook lists every enrolled student with a status (Approved, Ready to approve, Needs
  review, Grading failed, Submitted, **Not submitted**) plus unidentified papers. Class Summary shows submitted vs.
  enrolled and lists who has not submitted.
- **Notifications.** The bell (on every page) shows real events: uploads, grading finished (with how many need review or
  are not identified), grading failures, Grade again results, papers that need a student. Unread state, "2 minutes ago"
  timestamps, mark all as read, empty state; clicking opens the related queue or paper.
- **Profile.** Click the avatar or initials (or the name in the sidebar): name, email, role, department, account status,
  activities, classes, and students managed; edit display name and department; log out.
- **Settings.** Every setting has an effect: confidence threshold (re-sorts papers not approved yet), default feedback
  mode, default "accept alternate methods", default rubric option, delete photo after approval (server-side), and
  reduce motion (stored in this browser only). The AI model is shown read-only (it is set in `.env`).
- **College sample data.** Fictional college students (`2026-001`…`2026-040` in *BS Computer Science 2A*,
  `2026-201`…`2026-235` in *BS Secondary Education 1B*), college course titles, and a teacher profile (Prof. Ana Reyes).
- **UI cleanup and motion.** One AI note per table instead of one per row, queue filters merged into the tab row,
  lighter tip box, student name + ID everywhere; short page, panel, dialog, and approval animations that turn off under
  `prefers-reduced-motion` or the Reduce motion setting.

---

## Demo script (about 3 minutes)

1. **Sign in** as Prof. Ana Reyes. The dashboard shows 12 papers awaiting review, 9 flagged, 26 approved today; the
   activities table shows submitted / enrolled (38 / 40).
2. **Notifications**: open the bell. "1 paper needs a student" opens a paper whose name could not be read; the review
   screen says **Student: Not identified**. Pick *Harold Santiago · 2026-036* and **Assign**.
3. **Create activity** (optional): enter a title and a problem, choose **Generate rubric with AI**, edit the draft, then
   **Use this rubric** and **Save activity**.
4. **Upload**: open College Algebra: Linear Equations Quiz 1 → Upload. Maria Santos (2026-002) is marked *Retake
   suggested: Image is blurry*. Delete it and upload a new photo; the paper is matched to the roster when graded.
5. **Grade with TsekMate** → progress screen → queue. If a paper fails (for example a rate limit), its row says
   *Grading failed* with **Grade again**.
6. **Review detail (Paolo Mendiola, 2026-014, Problem 2)**: step 2 is a conceptual error, step 3 is unclear. Change the
   final score from 5 to 6 ("Edited by you") and **Approve and save**.
7. **Gradebook**: Paolo is on top (*Just approved*, P2 = 6 *Edited*); Kathleen Uy and Lorenzo Velasco are *Not
   submitted*. **Send to school system** shows the mock adapter.
8. **Class summary**: "14 of 40 students did not multiply every term inside the parentheses", the reteach focus, and the
   Not submitted list.
9. Optional: **Settings** (confidence threshold, reduce motion), **Profile**, **Parent update**, **Student view**.

If the API or network is slow during the demo, set `DEMO_MODE=true` after running `python scripts/evaluate.py
--write-cache` on the sample photos you plan to show; those photos then return cached results instantly.

---

## Architecture

```
React (Vite, TypeScript, Tailwind, recharts)          apps/web   -> Vercel
   |  typed API client (src/lib/api.ts)
FastAPI (Python 3.11, Pydantic v2)                    apps/api   -> Cloud Run (Dockerfile) or a laptop
   1. upload -> image quality check -> private bucket (signed URLs only); papers start "not identified"
   2. background job: ONE Claude Haiku vision call per paper
      (transcribe + split into units + grade vs rubric + read name/ID), JSON only
   3. Pydantic validation -> retry once -> else "Grading failed" (+ Grade again)
   4. code recomputes every score and routes: needs_review vs ready (threshold from Settings)
   5. code matches name/ID to the class roster (identity is separate from grading confidence)
   6. teacher edits / assigns the student (every edit logged) -> approve -> gradebook
   7. class summary: counts in code, one LLM call names misconceptions
Supabase (PostgreSQL + Storage)                       apps/api/db/schema.sql, db/migrations/
```

### How the AI is kept reliable (document Section 6.4)

- **One call per paper** with the problems, answer key, sample solutions, rubric (criteria, points, descriptions),
  settings, and the allowed error types in the prompt. Prompts are versioned text files in
  [`apps/api/prompts/`](apps/api/prompts/): `grade_v1.1.txt` (v1.0 plus the identity fields; v1.0 is kept),
  `rubric_v1.0.txt`, `summary_v1.0.txt`, `parent_v1.0.txt`, `practice_v1.0.txt`.
- **Prompt-injection safety**: everything on the paper is student work, never instructions.
- **Identity never changes the grade**: the prompt says so, the schema parses identity leniently (bad or missing
  values become "not identified" instead of failing validation), and routing ignores identity confidence.
- **Feedback rules**: describe the work, never the child. Hint-only by default.
- **Structured output** validated with Pydantic; **deterministic code** recomputes scores and routing.
- **Accountability**: every AI result stores the model, prompt version, timestamp, raw JSON, and identity reading;
  every teacher edit (including student assignment) is logged.
- **Class summary counts come from code.** The LLM only groups error comments by id and names them.

---

## Data model

`students` (id = student number, **name**, section) · `activities` · `problems` · `rubrics` · `rubric_templates` ·
`submissions` (student_id **nullable** until identified, **identity** jsonb, status, image path) · `ai_results`
(problem results, scores, confidence, flags, model, prompt version, raw JSON, **identity**) · `teacher_reviews` ·
`class_summaries` · `parent_messages` · **`notifications`** · **`app_settings`** (`settings`, `profile`).
The class roster of an activity is every student whose `section` equals the activity's `class_name`.
AI rubric drafts are not stored; they live in the form until the teacher accepts them.

---

## Privacy and responsible AI

- **No real student data.** Seed names are fictional (random combinations of common Filipino names) with made-up
  student numbers; seed papers are rendered with a handwriting font. Real test papers come from our team or consenting
  adults.
- **Names now leave the browser.** Because TsekMate reads the name on the paper, the photo (including the name) is sent
  to the Claude API. For real classes a school needs consent, a data processing agreement, and its own privacy review.
- **Human in the loop**: nothing reaches the gradebook, the student, or a parent without teacher approval, and the
  teacher confirms or assigns every student identity that is not a clear match.
- **Private storage, signed URLs**, optional deletion of photos after approval (Settings).
- **Non-labeling feedback**: comments describe the work. Parent messages contain no name, ID, or score.
- Under the Philippine Data Privacy Act (RA 10173) grades are sensitive personal information. Not legal advice.

---

## Evaluation

`scripts/evaluate.py` measures, on our own handwritten samples: transcription accuracy per handwriting style, rubric-item
agreement, catch rate per planted error type, whether low-confidence flags coincide with real disagreements, and (when
ground truth includes `student_name` / `student_id`) how often the name and ID are read correctly. It writes
`samples/eval/report.md` and `report.json` and states the sample size.

**Status: not run yet.** No Anthropic API key and no real sample photos were available while building. The pipeline is
tested with a stubbed model and font-rendered smoke-test images, which are excluded from the reported evaluation.

---

## API

| Method and path | Purpose |
|---|---|
| `POST /api/auth/signin` | Demo teacher sign-in |
| `GET /api/dashboard` | Stat cards and deltas |
| `GET/POST /api/activities`, `GET /api/activities/{id}` | Activities (with roster size, not submitted, unidentified counts) |
| `GET /api/rubric-templates` | Rubric template dropdown |
| `POST /api/rubric/generate` | **AI rubric draft** (not saved; normalized to the points per problem) |
| `GET/POST /api/activities/{id}/submissions` | List or upload papers (multipart `files`, optional `student_ids`) |
| `DELETE /api/submissions/{id}` | Remove a not-yet-approved paper (retake) |
| `POST /api/activities/{id}/grade`, `GET .../grading-progress` | Background batch grading (uploaded and failed papers) |
| `POST /api/submissions/{id}/regrade` | **Grade again** one failed (or not yet graded) paper |
| `PATCH /api/submissions/{id}/student` | **Assign the paper to a roster student** (`{"student_id": "2026-036"}`) |
| `GET /api/activities/{id}/roster` | **Roster with submission status** (incl. Not submitted) |
| `GET /api/activities/{id}/queue?tab=` | `needs_review`, `ready`, `approved`, `all` |
| `GET /api/submissions/{id}` | Detail with signed image URL, AI result, identity, roster, review state |
| `PATCH /api/submissions/{id}/review` | Unit edits, problem scores, feedback (logged) |
| `POST /api/submissions/{id}/approve` | Approve and write to the gradebook (needs an assigned student) |
| `GET /api/activities/{id}/class-summary`, `POST .../practice` | Summary (incl. submissions); teacher practice problems |
| `GET /api/activities/{id}/gradebook` | Mock gradebook with names and statuses |
| `GET /api/notifications`, `POST /api/notifications/{id}/read`, `POST /api/notifications/read-all` | **Notifications** |
| `GET/PATCH /api/settings` | **Settings** (threshold, defaults, photo deletion; AI model read-only) |
| `GET/PATCH /api/profile` | **Profile** (name, department; stats) |
| `POST /api/submissions/{id}/parent-message` (+ `/approve`) | Stretch: EN + FIL draft, teacher approval |
| `GET /adapter/activities`, `GET /adapter/submissions`, `POST /adapter/grades/draft`, `POST /adapter/notifications` | Mock adapter |

The adapter endpoints are thin wrappers over the mock gradebook. **This is not an official integration.** Interactive
docs: `http://localhost:8000/docs`.

---

## Deploy

- **Web (Vercel)**: project root `apps/web`, set `VITE_API_URL` to the API URL. `vercel.json` adds the SPA rewrite.
- **API (Google Cloud Run)**: `apps/api/Dockerfile` (command in the file header). Set the env vars above as secrets.
  The Dockerfile has not been built in our environment (no Docker daemon). One worker: grading jobs run in background
  threads, so the job list is per instance.
- Fallback: demo from a laptop with the local setup above.

---

## Limits (stated openly)

- Live Claude Haiku grading has not been run yet (no API key while building); see Evaluation.
- Accuracy depends on handwriting and photo quality; diagrams and unusual notation are not handled.
- Confidence (grading and identity) is model-reported, not calibrated.
- Name matching is deliberately conservative: similar names or nicknames may need the teacher to assign the student.
- One teacher account, no real authentication; the student view is a teacher-side preview. Profile edits change the
  display name and department only.
- The in-memory store loses data on restart; use Supabase for anything that should persist. The Supabase code path
  (including migration 002) has not been run against a real project yet.
- The gradebook and adapter are mocks. Not legal advice on data privacy.

## History

- The project briefly used **Google Gemini** (`gemini-2.5-flash`, `GEMINI_API_KEY`) to try the Gemini free tier. Only
  invalid-key calls were tested against Google; no live Gemini grading was run. The live provider was then switched
  back to **Anthropic Claude (Claude Haiku 4.5)**. See `docs/PLAN.md` sections 8 and 9.

## Roadmap (designed, not built)

Offline capture queue and PWA; on-device name redaction (note: this now conflicts with reading names for roster
matching and would need a separate ID-only capture); student and parent logins with row-level security; Bisaya
messages; locally hosted model for privacy-strict schools; real LMS integration and roster import; geometry and
diagrams; essay grading; SymPy cross-checks and a second-model comparison.

## Suggestions (not built, for the team to decide)

- Calibrate the confidence threshold per subject once real evaluation data exists.
- Roster import from CSV (rosters are seeded today).
- Show a per-problem "AI vs teacher" agreement chart from the edit log (we already store it).
- Push notifications (today the bell refreshes every 20 seconds and when opened).

## Repository layout

```
apps/web     React app (Vite, TypeScript, Tailwind)
apps/api     FastAPI app, prompts/, db/schema.sql, db/migrations/, tests/
scripts      seed.py, grade.py, evaluate.py, make_synthetic.py
samples      real samples (math/science/grammar), synthetic smoke tests, demo cache, eval reports
docs         project document, mockups, PLAN.md
```
