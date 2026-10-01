-- TsekMate schema for Supabase (PostgreSQL). Run once in the Supabase SQL editor.
-- Ids are text so the same rows work in the in-memory test store. No real names anywhere: students are pseudonymous.

create table if not exists students (
  id text primary key,                -- student number, e.g. 2026-014 (stable identifier)
  name text not null default '',      -- fictional names in the demo seed
  section text not null               -- class roster = students whose section equals activities.class_name
);

create table if not exists activities (
  id text primary key,
  title text not null,
  subject text not null check (subject in ('math', 'science', 'grammar')),
  class_name text not null,
  date date not null,
  settings jsonb not null default '{}'::jsonb,
  total_points numeric not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists problems (
  id text primary key,
  activity_id text not null references activities(id) on delete cascade,
  position int not null,
  text text not null,
  expected_answer text not null,
  sample_solution text not null default '',
  rule text not null default ''
);

create table if not exists rubrics (
  id text primary key,
  activity_id text not null references activities(id) on delete cascade,
  criteria jsonb not null               -- [{name, description, points}]
);

create table if not exists rubric_templates (
  id text primary key,
  name text not null,
  subject text not null,
  criteria jsonb not null
);

create table if not exists submissions (
  id text primary key,
  activity_id text not null references activities(id) on delete cascade,
  student_id text references students(id),  -- null until the paper is identified (AI) or assigned (teacher)
  identity jsonb,                       -- {status, method, extracted_name, extracted_id, identity_confidence, ...}
  image_path text,                      -- path in the private bucket; null after deletion
  image_hash text,
  status text not null check (status in ('uploaded', 'grading', 'needs_review', 'ready', 'approved', 'failed')),
  quality jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists submissions_activity on submissions(activity_id);

create table if not exists ai_results (
  id text primary key,
  submission_id text not null references submissions(id) on delete cascade,
  problem_results jsonb not null,
  suggested_score numeric not null,
  max_score numeric not null,
  overall_confidence numeric not null,
  flags text[] not null default '{}',
  model text not null,
  prompt_version text not null,
  raw_json jsonb,
  identity jsonb,                       -- name / ID read from the paper; separate from grading confidence
  created_at timestamptz not null default now()
);
create index if not exists ai_results_submission on ai_results(submission_id);

create table if not exists teacher_reviews (
  id text primary key,
  submission_id text not null unique references submissions(id) on delete cascade,
  final_score numeric,
  unit_edits jsonb not null default '{}'::jsonb,
  problem_scores jsonb not null default '{}'::jsonb,
  feedback jsonb not null default '{}'::jsonb,
  edit_log jsonb not null default '[]'::jsonb,
  approved boolean not null default false,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists class_summaries (
  id text primary key,                  -- = activity_id
  activity_id text not null references activities(id) on delete cascade,
  signature text not null,
  misconceptions jsonb not null,
  reteach_focus text not null,
  model text not null,
  prompt_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists parent_messages (
  id text primary key,
  submission_id text not null references submissions(id) on delete cascade,
  language text not null,
  text text not null,
  approved boolean not null default false,
  sent_at timestamptz,
  model text not null,
  created_at timestamptz not null default now()
);

create table if not exists notifications (
  id text primary key,
  kind text not null,                   -- grading_done, needs_review, grading_failed, regrade_ok, upload_done
  title text not null,
  body text not null default '',
  link text,                            -- in-app route to open
  activity_id text references activities(id) on delete cascade,
  submission_id text,
  read boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists app_settings (
  id text primary key,                  -- 'settings' | 'profile'
  value jsonb not null,
  updated_at timestamptz not null default now()
);

-- The API uses the service key server-side. Enable RLS with no policies so the anon key cannot read anything.
alter table students enable row level security;
alter table activities enable row level security;
alter table problems enable row level security;
alter table rubrics enable row level security;
alter table rubric_templates enable row level security;
alter table submissions enable row level security;
alter table ai_results enable row level security;
alter table teacher_reviews enable row level security;
alter table class_summaries enable row level security;
alter table parent_messages enable row level security;
alter table notifications enable row level security;
alter table app_settings enable row level security;

-- Private bucket for student work images (signed URLs only).
insert into storage.buckets (id, name, public) values ('submissions', 'submissions', false)
on conflict (id) do nothing;
