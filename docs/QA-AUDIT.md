# TsekMate QA and Audit Report

- **Date:** 2026-10-01
- **Commit audited:** `ec61f7f` (current `main`)
- **Scope:** `apps/api` (FastAPI backend, grading pipeline, stores, DB schema, Dockerfile), `apps/web` (React/Vite app),
  `scripts/`
- **Method:** a full read of the backend and the main web screens, the existing test suite, a type check and production
  build of the web app, `npm audit`, and a reproduction probe ([`docs/qa/repro_probe.py`](qa/repro_probe.py)) run against
  the in-memory store. Each finding is marked **Confirmed** (reproduced) or **By inspection** (read in the code but not
  run; mostly Supabase or deployment paths that need real credentials).

No source code was changed. This branch only adds this report and the probe script.

---

## 1. Summary

| Check | Result |
|---|---|
| Backend tests (`pytest`, Python 3.11) | **70 passed, 1 failed** (the failure depends on the time of day; see B-9) |
| Web type check (`tsc -b`) | Passes |
| Web production build (`vite build`) | Passes, with a warning that the 714 kB JS bundle is over the 500 kB chunk limit |
| `npm audit` | **4 vulnerabilities (1 high, 3 moderate)** (see S-6) |

| Severity | Count | Main themes |
|---|---|---|
| Critical | 1 | The API has no authentication at all |
| High | 6 | Papers stuck in "grading" forever, race between approve and re-grade, NaN values that permanently break pages, PDFs/WEBP that can't be graded on Supabase, duplicate students in one upload, unsafe default secrets |
| Medium | 12 | "Save draft" silently changes approved grades, background work stalls on Cloud Run, blocking upload handler, unvalidated edit inputs, time-dependent test, dependency advisories, and others |
| Low | 16 | UX, consistency, and hardening items |

**Fix first:** S-1 (authentication), B-1 (stuck papers), B-2 (approve/re-grade race), B-3 (NaN input), B-4 (Supabase
media types), B-5 (duplicate students), and S-2 (default secrets).

---

## 2. Security findings

### S-1 [Critical] The API has no authentication. Every endpoint is public. (Confirmed)
- `apps/api/app/main.py:88` `/api/auth/signin` compares the email and password and returns the profile, but it issues
  **no token or session**. No other route checks who is calling.
- The web app's "sign-in" is just a flag in `localStorage` (`apps/web/src/lib/session.ts`, `App.tsx` `RequireTeacher`),
  so it only hides screens in the browser.
- Anyone who can reach the API can read every student's name, ID, scores, and feedback; change the rubric, settings,
  and profile; approve grades; delete papers; trigger paid AI calls (`/grade`, `/regrade`, `/practice`,
  `/parent-message`, `/rubric/generate`); and export grades (`/adapter/*`).
- The Dockerfile's deploy command uses `--allow-unauthenticated` on Cloud Run, which makes this public on the internet.
- Probe: `GET /api/activities` and `PATCH /api/settings` with no credentials both return `200`.
- **Fix:** issue a signed session token (or use Supabase Auth) at sign-in and require it on every `/api/*` and
  `/adapter/*` route through a FastAPI dependency. Have the web client send it.

### S-2 [High] Unsafe default secrets and credentials. (By inspection)
- `apps/api/app/config.py:35`: `IMAGE_SIGNING_SECRET` falls back to `"local-dev-only-secret"`, and `.env.example`
  ships `change-me`. Anyone who knows the default can forge image URLs and read any paper photo in the in-memory
  deployment.
- `config.py:37`: the demo password `tsekmate` is the default and is printed in the README.
- **Fix:** refuse to start (or log a loud error) when these are unset or still at their defaults outside local
  development.

### S-3 [Medium] CORS allows every `*.vercel.app` origin. (By inspection)
- `main.py:43`: `allow_origin_regex=r"https://.*\.vercel\.app"` trusts any app hosted on Vercel, including other
  people's. Combined with S-1, any Vercel-hosted page can call the API from a visitor's browser.
- **Fix:** list the exact production and preview origins (for example `https://tsekmate(-[a-z0-9-]+)?\.vercel\.app`).

### S-4 [Medium] `/api/health` exposes the model and setup details. (Confirmed)
- `main.py:75` returns the model name, the AI provider, whether the key is set, and the demo mode to anyone. The README
  calls it an "admin endpoint", but it isn't protected.
- **Fix:** return only `{"ok": true}` publicly and move the details behind admin auth.

### S-5 [Medium] Uploads are read fully into memory, trusted by their declared type, and decoded without a pixel limit. (Confirmed / By inspection)
- `main.py:136` calls `await f.read()` before checking the size, so a very large request is buffered completely. The
  number of files per request isn't limited either.
- The content type comes from the client. Probe #15: arbitrary bytes (an HTML string) sent as `image/jpeg` are
  accepted and stored (`201`). They only get "Retake suggested".
- `services/quality.py` and `grading/images.py` open uploads with Pillow and don't set an explicit pixel limit. A
  small, highly compressed PNG with very large dimensions can use a lot of memory (a decompression bomb).
- **Fix:** read in chunks up to `MAX_UPLOAD`, check the file's magic bytes, cap the number of files, and set
  `Image.MAX_IMAGE_PIXELS` (or check `img.size` before `load()`).

### S-6 [Medium] Vulnerable frontend dependencies. (Confirmed: `npm audit`)
- `react-router` / `react-router-dom` 6.x: open redirect through a backslash in `<Link>`/`useNavigate`
  (GHSA-wrjc-x8rr-h8h6) and another advisory (GHSA-337j-9hxr-rhxg). The fix is in 7.18+, which is a major upgrade.
- `vite` 5 / `esbuild` ≤ 0.24.2: the dev server lets any website read its responses (GHSA-67mh-4wv8-2f99). This only
  affects development, but developers run it daily.
- **Fix:** plan an upgrade to react-router 7 and vite ≥ 6.4.3 / 7. Until then, don't run `npm run dev` bound to a
  public interface.

### S-7 [Low] CSV export allows spreadsheet formula injection. (By inspection)
- `apps/web/src/lib/format.ts:47` `downloadCsv` quotes commas and quotes, but it doesn't neutralize cells that start
  with `=`, `+`, `-`, or `@`, and it doesn't quote `\r`. Student names come from the roster, so the risk is limited
  today, but they will be teacher-editable later.
- **Fix:** prefix those cells with `'` and quote `\r`.

### S-8 [Low] The container runs as root. (By inspection)
- The `Dockerfile` has no `USER` line. Add a non-root user.

---

## 3. Functional bugs

### B-1 [High] Papers can get stuck in "grading" forever. (Confirmed)
- `services/jobs.py:54` sets papers to `grading` and grades them in an in-process thread. If the process restarts
  during Fast grading (a deploy, a crash, or Cloud Run scaling down), nothing resets them. The lifespan hook only
  resumes **Saver** batches.
- Once stuck, the paper can't be recovered from the UI:
  - "Grade again" refuses it (`jobs.py:45` only allows `failed`/`uploaded`) → `409`
  - Delete refuses it ("being checked right now") → `409`
  - "Grade all" skips it
  - The grading screen polls every 1.2 s forever: progress shows it as `waiting` with `running: false`.
- The in-memory store hides this because it reseeds on restart. Supabase deployments will hit it.
- Probe #7: `regrade 409`, `delete 409`, and the paper isn't included in grade-all.
- **Fix:** on startup (and whenever no in-process job exists for the activity), move `grading` papers that aren't
  part of a processing batch back to `uploaded` (or `failed` with a reason). Or let Grade again accept `grading` when
  no job is running for it.

### B-2 [High] Approving during a re-grade loses the approval. (Confirmed)
- `services/core.py:579` `approve()` doesn't check the paper's status. A teacher can approve a paper while it's in
  `grading` (for example a second tab during Grade again). When the grader finishes, `jobs.py:151` deletes the
  `teacher_reviews` row (which holds the approval, scores, and edit log) and `jobs.py:171` overwrites the status with
  `needs_review`/`ready`.
- Probe #6: approving a `grading` paper returns `200`.
- **Fix:** refuse to approve, edit, or reassign papers in `grading`. In `grade_submission`, re-read the status and save
  the result only if it's still `grading`.

### B-3 [High] Non-finite numbers (NaN/Infinity) are accepted and permanently break pages. (Confirmed)
- FastAPI's JSON parser accepts `NaN` and `Infinity`, and Pydantic `float` allows them. Validation doesn't catch them:
  - `grading/scoring.py:153`: `v <= 0` is `False` for NaN.
  - `scoring.py:159`: `abs(nan - total) > 1e-6` is `False`.
  - `core.py` `patch_review` range check: `v < 0 or v > max` is `False` for NaN.
- The value is stored. Every response that includes it then fails JSON encoding with a **500**.
- Probe #2: creating an activity with a NaN rubric fails with `500`, but the row is already inserted, and **from then
  on `GET /api/activities` (and the dashboard) returns 500 for everyone.**
- Probe #5: one NaN criterion score makes that paper's detail page return 500 **permanently**. Resetting the score
  doesn't help, because the NaN stays in `edit_log`.
- **Fix:** use `Field(allow_inf_nan=False)` (or `math.isfinite` checks) on every numeric input (`Criterion.points`,
  `rubric_total`, `RubricUpdate.total_points`, `criterion_scores` values, `points_awarded`). Validate before inserting
  anything in `create_activity`.

### B-4 [High] On Supabase, PDF and WEBP papers are sent to the AI with the wrong media type. (By inspection)
- `store/supabase_store.py:65` `get_image()` labels every file that isn't PNG as `image/jpeg`. Uploaded PDFs
  (`.pdf`) and WEBP files (`.webp`) are then graded as `image/jpeg`:
  - A PDF fails `images.prepare` and is sent as an "image", which the API rejects. **PDF papers can never be graded on
    Supabase.**
  - A small, upright WEBP is sent unchanged with the wrong type, which the API also rejects.
- The in-memory store keeps the real type, so the tests don't catch this.
- **Fix:** map the extension to a type (`.pdf` → `application/pdf`, `.webp` → `image/webp`, `.png`, `.jpg`), or store
  the type on the submission row.

### B-5 [High] One upload can give the same student two papers. (Confirmed)
- `core.py:321` checks the requested `student_ids` against papers that already exist, but not against each other.
  Sending `student_ids="2026-036,2026-036"` creates two papers for one student (probe #3: `201`, both rows
  `2026-036`).
- The schema has no `unique (activity_id, student_id)` constraint on `submissions`, so the database doesn't stop it.
  The roster, gradebook, and `taken()` then silently keep only one of them.
- **Fix:** reject duplicates within the request, and add a partial unique index
  `on submissions(activity_id, student_id) where student_id is not null`.

### B-6 [Medium] "Save draft" on an approved paper silently changes the grade in the gradebook. (Confirmed)
- The UI says "Draft saved. Nothing is final until you approve." But `core.py:575` recomputes `final_score` for
  approved papers, and the gradebook, class average, and `/adapter/grades/draft` read the live edited scores, not the
  score at approval.
- An approved grade can change without re-approval, which goes against the README rule that "Only approved results
  reach the gradebook".
- Probe #10: `PATCH /review` on an approved paper returns `200`.
- **Fix:** freeze the approved scores in a snapshot that the gradebook uses, or move the paper back to `ready` when it's
  edited after approval so it needs re-approval.

### B-7 [Medium] Unvalidated unit edits cause 500 errors. (Confirmed)
- `core.py:535` `float(v)` raises an error on `null` or non-numeric `points_awarded` → 500 (probe #4).
- `comment`/`transcribed_text` accept any JSON type. A `null` comment later breaks the class summary at
  `services/ai_text.py:24` (`None[:160]`), which runs before its `try` block.
- **Fix:** give `unit_edits` a typed Pydantic model.

### B-8 [Medium] Background work stalls on Cloud Run and doesn't scale beyond one process. (By inspection)
- Grading threads, the Saver batch poller, `_jobs`, and `scoring.THRESHOLD` (set through `settings.apply`) all live in
  one process.
- With Cloud Run's default CPU throttling, threads get almost no CPU once the HTTP response is sent, so "Grade all"
  stalls. Add `--no-cpu-throttling` (and `--min-instances=1`) to the documented deploy command.
- With more than one instance, a confidence threshold saved on one instance doesn't reach the others, and job progress
  isn't shared.
- **Fix:** document a single instance (`--max-instances=1`), or move job state and the threshold into the database or
  a queue.

### B-9 [Medium] The dashboard's "approved today" and its test depend on the time of day. (Confirmed)
- `seed.py:343,508` dates the "today" approvals `now − 1h − 3·n minutes`, but "today" is counted from local midnight
  in Asia/Manila (`core.py` `dashboard`).
- Between about 00:00 and 03:00 Manila time, some or all of these approvals fall on the previous day. Seeding at UTC
  16:30 gives `approved_today = 0`, at 17:30 it gives `8`, and from 19:30 it gives `26`.
- `tests/test_api_flow.py::test_seed_reproduces_mockup_numbers` fails during that window (it failed in this run, at
  02:21 Manila time).
- **Fix:** anchor the seed's "today" to local noon (or clamp it to after local midnight), or freeze time in the test.

### B-10 [Medium] `async def upload` blocks the event loop. (By inspection)
- `main.py:133` is `async` but calls `core.add_uploads` synchronously. That function does Pillow work and (on
  Supabase) network I/O for every file. While a class set uploads, every other request waits.
- **Fix:** make the route a plain `def` after reading the files, or use `await run_in_threadpool(...)`.

### B-11 [Medium] Supabase `reset()` probably never ends once uploads exist. (By inspection)
- `supabase_store.py:75-86` lists `uploads/` and removes the names it finds. Uploads are stored at
  `uploads/<activity_id>/<sub>.ext`, so the listing returns **folder** entries. Removing those deletes nothing, and the
  `while True` loop repeats forever. `python scripts/seed.py --reset` would hang.
- **Fix:** list each folder recursively, and stop when a pass deletes nothing.

### B-12 [Medium] Parent update makes a paid AI call and saves 2 rows every time the page opens. (By inspection)
- `apps/web/src/pages/ParentUpdate.tsx:35` `useEffect(generate, [id])` posts to `/parent-message` on every visit. In
  development, React StrictMode runs it twice. Each call inserts two `parent_messages` rows (`main.py`) that are never
  reused or cleaned up.
- **Fix:** return the latest saved draft when there is one, and generate only when the teacher asks.

### B-13 [Medium] No warning about unsaved review edits. (By inspection)
- `apps/web/src/pages/ReviewDetail.tsx` keeps a `dirty` flag, but "Leave flagged and go to the next paper", Back, the
  sidebar links, and closing the tab all drop unsaved edits without asking.
- **Fix:** use react-router's `useBlocker` or `beforeunload` while `dirty`.

### B-14 [Medium] The class summary page triggers a paid AI call. (By inspection)
- `GET /class-summary` (`core.py:697`) calls the model whenever the set of error units changes, and `/practice` calls
  it again. A page view should not have paid side effects; with S-1 this is also an open cost risk.
- A cached summary with the signature `"seed"` is **never** refreshed, even after the teacher edits seeded papers.
  This is probably intended for the demo, but it also affects real use of the seeded activities.

### B-15 [Low] Approving is allowed without checking the paper's state. (Confirmed)
- `approve()` accepts any status that has an AI row, including `failed`, where all scores are 0 unless the teacher
  entered them. That is intended for grading by hand, but a stray click records a 0.
- Re-approving overwrites `approved_at` (probe #9). Consider asking for confirmation when approving a `failed` paper
  with no scores entered.

### B-16 [Low] A parent message can be "approved" for a paper that isn't approved. (Confirmed)
- `main.py:326` checks that the paper exists but not that it's approved. Drafting the message is gated, but this
  endpoint isn't (probe #12: `200`).

### B-17 [Low] The student view shows paper results that aren't approved. (By inspection)
- `/feedback/:id` (`StudentFeedback.tsx`) renders any paper's AI draft. The link is hidden until approval, but the URL
  works for any paper.

### B-18 [Low] The review screen hard-codes the 0.75 threshold. (By inspection)
- `ReviewDetail.tsx:43` `needsCheck` uses `0.75`, but the server routes with the Settings threshold. Flag dots then
  disagree with the queue after the teacher changes the threshold. `useThreshold()` already exists for this.

### B-19 [Low] The Create Activity default date is the UTC date. (By inspection)
- `CreateActivity.tsx:32` uses `new Date().toISOString().slice(0, 10)`. In the Philippines (UTC+8), from 00:00 to
  08:00 local time it defaults to yesterday.
- The backend also doesn't validate `date` (`models.py` `date: str`). Bad input is accepted by the in-memory store
  and fails with a 500 on Postgres.

### B-20 [Low] A failed settings request is cached forever. (By inspection)
- `apps/web/src/lib/appSettings.ts:12` keeps a rejected `inflight` promise. After one network error, every later
  `loadSettings()` returns the same rejection until a forced reload.

### B-21 [Low] Upload input quirks. (By inspection)
- `Upload.tsx:160` doesn't reset the file input's `value`, so choosing the same file again (for example after deleting
  it) does nothing.
- The help text says "JPG, PNG or PDF", but WEBP is also accepted.
- Grading runs only after an upload, but a single file over 10 MB rejects the whole multi-file upload. Check sizes on
  the client first.

### B-22 [Low] Store inconsistencies. (By inspection)
- `SupabaseStore.delete(**eq)` uses `.eq(k, None)` for `None` values, while `select` uses `.is_(k, "null")`. They
  match different rows from the memory store.
- `models.check_against` compares criteria with `.lower()` but doesn't strip spaces, while scoring uses
  `.strip().lower()`. A reply like `"Setup "` fails validation and spends a retry.
- `settings.reroute` updates `status` without updating `updated_at`.

### B-23 [Low] A roster change can hide approved grades. (By inspection)
- `gradebook()` and `class_summary()` list only students whose `section` equals the activity's `class_name`. If a
  student's section changes, or the class name is edited, their approved paper disappears from the gradebook
  (`approved_grades` still exports it).

### B-24 [Low] `downloadCsv` revokes the object URL right after `click()`. (By inspection)
- Some browsers (Safari, older Firefox) cancel the download. Revoke it in a `setTimeout`.

---

## 4. Performance and maintainability

- **P-1 [Low] N+1 queries.** `list_activities` builds a full `Bundle` (about 5 queries) for every activity, and
  `dashboard` calls it, then builds more bundles. `queue_row` calls `b.effective()` several times per paper. This is
  fine in memory but slow on Supabase as data grows.
- **P-2 [Low] Large bundle.** The web build produces a 714 kB JS chunk (recharts included). Lazy-load routes such as
  ClassSummary and Gradebook.
- **P-3 [Low] Per-process state.** `_jobs` in `jobs.py` is never trimmed, and `scoring.THRESHOLD` is a mutable
  module global. Both are tied to B-8.
- **P-4 [Low] Missing coverage.** No tests cover auth (none exists), Supabase store behavior (B-4, B-11, B-22),
  restart recovery (B-1), or non-finite input (B-3).

---

## 5. Suggested order of work

1. Add real authentication (S-1) and remove unsafe defaults (S-2, S-3, S-4).
2. Make grading state safe:
   - recover stuck papers (B-1)
   - block approve/edit during grading and guard the grader's write (B-2)
   - freeze approved grades (B-6)
3. Harden input validation: finite numbers (B-3), duplicate student IDs plus a unique index (B-5), typed unit edits
   (B-7), upload limits and type checks (S-5).
4. Fix the Supabase paths: media types (B-4), `reset()` (B-11), store consistency (B-22).
5. Fix deployment: Cloud Run CPU throttling and single-instance constraints (B-8), non-blocking upload (B-10).
6. Make the test deterministic (B-9) and add regression tests for each fixed item.
7. Upgrade dependencies (S-6) and handle the UX items (B-12, B-13, B-18 to B-21, B-24).

## 6. Reproducing

```bash
cd apps/api
pip install -r requirements.txt
python -m pytest -q                      # 70 passed, 1 failed (B-9, between 00:00 and about 03:00 Asia/Manila)
python ../../docs/qa/repro_probe.py      # prints the observed status code for each confirmed finding
cd ../web && npm ci && npx tsc -b && npx vite build && npm audit
```
