# TsekMate

### Every step checked. Every teacher in control.

TsekMate reads a photo of a student's handwritten work, checks it **step by step against the teacher's rubric**, and
produces a marked-up draft with error types, confidence, and a hint for the student. The teacher reviews, edits, and
approves. Only approved results reach the gradebook, the student view, and the parent update.

Entry for the **AI in Education Hackathon 2026: "Transforming Education Through Artificial Intelligence."**
Full design: [`docs/TsekMate Project Document (24-hour build).html`](docs/). UI source of truth: [`docs/mockups/`](docs/mockups/).
Build plan and mockup decisions: [`docs/PLAN.md`](docs/PLAN.md).

> The AI drafts. The teacher decides. Every AI output in the app carries the label
> **"AI-assisted draft, reviewed by your teacher."**

---

## What is built

| Tier | Item | Status |
|---|---|---|
| Must have | Photo upload (drag and drop, file picker, phone camera), pseudonymous IDs | Built |
| Must have | One vision call per paper: transcribe + split into steps + grade against the rubric, JSON only | Built |
| Must have | Pydantic validation, one retry with the validation error, then "needs teacher" + `grading_failed` | Built |
| Must have | Error-type tags and confidence per step; scores recomputed in code | Built |
| Must have | Review queue, lowest confidence first, tabs (needs review / ready / approved / all) | Built |
| Must have | Review detail: photo with step boxes, per-step edit, points, final score, feedback, review record | Built |
| Must have | Approve (nothing is saved to the gradebook until then), mock gradebook, CSV export | Built |
| Must have | Class summary: counts from code, one LLM call for misconception names and reteach focus | Built |
| Must have | Activity creation with rubric templates (Math, Science, English Grammar) | Built |
| Must have | Evaluation script and command-line grader | Built (waiting for real samples and an API key) |
| Stretch | Image quality check (blur and darkness, "Retake suggested") | Built |
| Stretch | Parent message in English and Filipino, labeled machine draft, teacher approval | Built (needs API key) |
| Stretch | Text-to-speech on the student feedback view (browser Web Speech API) | Built |
| Stretch | SymPy cross-check of algebra steps | Not built |
| Stretch | Gemini comparison | Not built |
| Bonus | Mock school-system adapter (`/adapter/*`) | Built, **not an official integration** |

Three subjects share one pipeline; only the rubric, labels, and error types change:

| Subject | Seeded activity | Rubric (10 pts per problem) | Error types | Unit name |
|---|---|---|---|---|
| Math | Solving Linear Equations: Quiz 1 (5 problems) | Setup 2, Method 3, Computation 3, Final answer 2 | computational, conceptual, notation, presentation | Step |
| Science | Forces and Motion: Quiz 2 (4 problems) | Formula 2, Substitution 2, Computation 3, Answer with units 3 | computational, conceptual, units_and_notation, presentation | Step |
| English Grammar | Subject-Verb Agreement: Worksheet 3 (5 items) | Finds the errors 3, Correct revision 4, Rule explanation 2, Spelling and punctuation 1 | grammar_rule, spelling, punctuation_capitalization, word_choice | Correction |

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

Sign in with the demo teacher account: **reyes@school.edu.ph / tsekmate** (set in `.env`).

Without `SUPABASE_URL` the API runs on an **in-memory test store** that seeds itself on every start (restart = reset).
Without `ANTHROPIC_API_KEY` everything works except live AI calls: new uploads are marked "Grading failed" so the
teacher can grade by hand, and the parent message and practice problems show a clear error.

### Supabase

1. Create a project. In the SQL editor run [`apps/api/db/schema.sql`](apps/api/db/schema.sql) (tables, RLS on with no
   public policies, and a **private** `submissions` bucket).
2. Put `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (service role, server side only) in `.env`.
3. Seed or reset with one command: `python scripts/seed.py --reset`

### Command-line tools

```bash
python scripts/grade.py samples/math/paper01.jpg --activity act-linear-eq-quiz1   # one paper, prints JSON
python scripts/seed.py --reset                                                    # reset + seed the database
python scripts/make_synthetic.py        # font-rendered smoke-test papers (never used in the reported evaluation)
python scripts/evaluate.py              # evaluation on samples/{math,science,grammar} -> samples/eval/report.md
python scripts/evaluate.py --write-cache  # same, and store results for DEMO_MODE
cd apps/api && python -m pytest -q      # tests: scoring, routing, schema validation, retry, API flow, evaluation
```

Seeded activity ids: `act-linear-eq-quiz1`, `act-forces-motion-quiz2`, `act-sva-worksheet3`, `act-fractions-review`.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Claude API key. Required for live grading |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Vision model used for grading and summaries |
| `ANTHROPIC_EFFORT` | `medium` | Effort level (`low`, `medium`, `high`) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | (none) | Database and private storage. Empty = in-memory test store |
| `SUPABASE_BUCKET` | `submissions` | Private bucket name |
| `VITE_API_URL` | `http://localhost:8000` | Where the web app finds the API |
| `DELETE_IMAGES_ON_APPROVE` | `false` | Delete the photo after approval; keep scores, feedback, review record |
| `DEMO_MODE` | `false` | Use cached AI results (by image SHA-256) from `samples/cache` when present |
| `PUBLIC_API_URL`, `CORS_ORIGINS`, `IMAGE_SIGNING_SECRET` | local values | Signed image links and CORS (`*.vercel.app` is also allowed) |
| `APP_TIMEZONE` | `Asia/Manila` | "Today" for the dashboard |
| `DEMO_TEACHER_EMAIL`, `DEMO_TEACHER_PASSWORD` | demo values | The single teacher account |

Never commit `.env`.

---

## Demo script (about 2 minutes)

1. **Sign in** as Ms. Reyes. The dashboard shows 12 papers awaiting review, 9 flagged, 26 approved today.
2. **Upload**: open Solving Linear Equations: Quiz 1 → Upload. S-002 is marked *Retake suggested: Image is blurry*
   (the image quality check). Delete it, then take a new photo with **Use camera** (or choose a file). It gets the
   pseudonymous ID S-002 again.
3. **Grade with TsekMate**: the progress screen checks the paper (one vision call), then opens the queue.
4. **Review queue**: lowest confidence first. S-014 is on top at 54%, flagged *Unclear handwriting* and *Step mismatch*.
5. **Review detail (S-014, Problem 2)**: the photo with colored step boxes beside the transcript. Step 2 is a
   conceptual error ("3 was multiplied by x but not by -4"), Step 3 is unclear ("could be 9 or 8"). Change the final
   score from 5 to 6 ("Edited by you"), keep the hint-only feedback, **Approve and save**.
6. **Gradebook**: S-014 is on top, *Just approved*, P2 = 6 *Edited*. **Send to school system** shows the mock adapter.
7. **Class summary**: "14 of 38 students did not multiply every term inside the parentheses", errors by type, the
   suggested reteach focus. Switch to Science (S-022: "5 m" instead of 5 m/s) and Grammar (S-031 missed "say").
8. Optional: from the approved paper, **Parent update** (English / Filipino, machine draft) and **Student view**
   (large text, *Listen to feedback*).

If the API or network is slow during the demo, set `DEMO_MODE=true` after running `python scripts/evaluate.py
--write-cache` on the sample photos you plan to show; those photos then return cached results instantly. The UI does
not change.

---

## Architecture

```
React (Vite, TypeScript, Tailwind, recharts)          apps/web   -> Vercel
   |  typed API client (src/lib/api.ts)
FastAPI (Python 3.11, Pydantic v2)                    apps/api   -> Cloud Run (Dockerfile) or a laptop
   1. upload -> image quality check -> private bucket (signed URLs only)
   2. background job: ONE Claude vision call per paper (transcribe + split + grade vs rubric), JSON only
   3. Pydantic validation -> retry once -> else "needs teacher" (grading_failed)
   4. code recomputes every score and routes: needs_review vs ready
   5. teacher edits (every edit logged) -> approve -> gradebook
   6. class summary: counts in code, one LLM call names misconceptions
Supabase (PostgreSQL + Storage)                       apps/api/db/schema.sql
```

### How the AI is kept reliable (document Section 6.4)

- **One call per paper** with the problems, answer key, sample solutions, rubric (criteria, points, descriptions),
  settings, and the allowed error types in the prompt. Prompts are versioned text files in
  [`apps/api/prompts/`](apps/api/prompts/) (`grade_v1.0.txt`, `summary_v1.0.txt`, `parent_v1.0.txt`, `practice_v1.0.txt`).
- **Prompt-injection safety**: the prompt states that everything on the paper is student work, never instructions.
- **Feedback rules**: describe the work, never the child. In `hint_only` mode the model points to the error and asks a
  guiding question; full solutions only when the teacher picks `full_solution`.
- **Structured output** validated with Pydantic: verdicts, confidence 0 to 1, error types limited to the subject,
  every problem present, criteria that exist in the rubric. Bounding boxes are best effort; bad ones are dropped.
- **Deterministic code, not the model**, decides: points are clamped to the unit and criterion maximum; problem score
  = sum over criteria of min(criterion points, unit points); a paper needs review if any step is unclear, any step or
  problem confidence is below 0.75, or the model added a flag. The queue sorts by the lowest problem confidence.
- **Accountability**: every AI result stores the model, prompt version, timestamp, and raw JSON; every teacher edit is
  logged with old and new values (shown in the Review record).
- **Class summary counts come from code.** The LLM only groups error comments by id and names them; the code counts
  distinct students per group.

---

## Privacy and responsible AI

- **No real student data.** Pseudonymous IDs only (S-001 to S-038, plus M-001 to M-035 for the Grade 7 class in the
  seed). Seed papers are rendered with a handwriting font. Real test papers come from our team or consenting adults.
- **Human in the loop**: nothing reaches the gradebook, the student, or a parent without teacher approval.
- **Private storage, signed URLs**, and optional deletion of photos after approval (`DELETE_IMAGES_ON_APPROVE`).
- **Non-labeling feedback**: comments describe the work. Parent messages contain no name, ID, or score and are labeled
  "Machine-drafted message. Please review before sending."
- **Third-party AI**: images go to Anthropic for grading. A real deployment needs a data processing agreement,
  zero-retention settings where available, and a school-level privacy review, or a locally hosted model.
- Under the Philippine Data Privacy Act (RA 10173) grades are sensitive personal information. This README is not legal
  advice.

---

## Evaluation

`scripts/evaluate.py` measures, on our own handwritten samples: transcription accuracy per handwriting style, rubric-item
agreement, catch rate per planted error type, and whether low-confidence flags coincide with real disagreements. It
writes `samples/eval/report.md` and `report.json` and states the sample size in the report.

**Status: not run yet.** This environment had no API key and no real sample photos. The pipeline is tested with a
stubbed model (`tests/test_evaluate.py`) and font-rendered smoke-test images, which are excluded from the reported
evaluation by design. Add photos and ground truth as described in [`samples/README.md`](samples/README.md).

---

## API

| Method and path | Purpose |
|---|---|
| `POST /api/auth/signin` | Demo teacher sign-in |
| `GET /api/dashboard` | Stat cards and deltas |
| `GET/POST /api/activities`, `GET /api/activities/{id}` | Activities with problems, rubric, settings |
| `GET /api/rubric-templates` | Rubric template dropdown |
| `GET/POST /api/activities/{id}/submissions` | List or upload papers (multipart `files`, optional `student_ids`) |
| `DELETE /api/submissions/{id}` | Remove a not-yet-approved paper (retake) |
| `POST /api/activities/{id}/grade`, `GET .../grading-progress` | Background batch grading |
| `GET /api/activities/{id}/queue?tab=` | `needs_review`, `ready`, `approved`, `all` |
| `GET /api/submissions/{id}` | Detail with signed image URL, AI result, review state |
| `PATCH /api/submissions/{id}/review` | Unit edits, problem scores, feedback (logged) |
| `POST /api/submissions/{id}/approve` | Approve and write to the gradebook |
| `GET /api/activities/{id}/class-summary`, `POST .../practice` | Summary; teacher practice problems |
| `GET /api/activities/{id}/gradebook` | Mock gradebook |
| `POST /api/submissions/{id}/parent-message` (+ `/approve`) | Stretch: EN + FIL draft, teacher approval |
| `GET /adapter/activities`, `GET /adapter/submissions`, `POST /adapter/grades/draft`, `POST /adapter/notifications` | Mock adapter |

The adapter endpoints are thin wrappers over the mock gradebook, showing how TsekMate could plug into a school platform
such as Wela+ / Silid LMS. **This is not an official integration** and we have no partnership or access to any
vendor's API. Interactive docs: `http://localhost:8000/docs`.

---

## Deploy

- **Web (Vercel)**: project root `apps/web`, set `VITE_API_URL` to the API URL. `vercel.json` adds the SPA rewrite.
- **API (Google Cloud Run)**: `apps/api/Dockerfile` (command in the file header). Set the env vars above as secrets.
  The Dockerfile has not been built in our environment yet (no Docker daemon). One worker: grading jobs run in
  background threads, so the job list is per instance.
- Fallback: demo from a laptop with the local setup above.

---

## Limits (stated openly)

- Accuracy depends on handwriting and photo quality; diagrams and unusual notation are not handled.
- Confidence is model-reported, not calibrated.
- The evaluation, when run, uses about 15 papers from 3 to 4 writers: indicative only.
- One teacher account, no real authentication; the student view is a teacher-side preview.
- The in-memory store loses data on restart; use Supabase for anything that should persist.
- The gradebook and adapter are mocks. Not legal advice on data privacy.

## Roadmap (designed, not built)

Offline capture queue and PWA; on-device name redaction; student and parent logins with row-level security; Bisaya
messages; locally hosted model for privacy-strict schools; real LMS integration; geometry and diagrams; essay grading;
SymPy cross-checks and Gemini comparison (stretch items not reached).

## Suggestions (not built, for the team to decide)

- Calibrate the 0.75 threshold per subject once real evaluation data exists.
- Show a per-problem "AI vs teacher" agreement chart from the edit log (we already store it).
- Let the teacher set the student ID per upload from the UI (the API already accepts `student_ids`).
- Batch re-grade of `failed` papers after an outage (the Grade button already retries them).
- Settings page (the mockup has a Settings link; it is inactive in the prototype).

## Repository layout

```
apps/web     React app (Vite, TypeScript, Tailwind)
apps/api     FastAPI app, prompts/, db/schema.sql, tests/
scripts      seed.py, grade.py, evaluate.py, make_synthetic.py
samples      real samples (math/science/grammar), synthetic smoke tests, demo cache, eval reports
docs         project document, mockups, PLAN.md
```

The earlier version of this README described a different concept (typed essays and a "Class Knowledge Map"). It was
replaced to match the project document and mockups.
