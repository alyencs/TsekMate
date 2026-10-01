-- Migration 004: token usage per AI result, and Batch API grading ("Saver" grading mode).
-- For databases created before this change. Safe to run more than once.

-- Token counts for each graded paper: {"input_tokens", "output_tokens", "batch_input_tokens", "batch_output_tokens", "calls"}.
-- Batch tokens are kept apart because they are billed at half price.
alter table ai_results add column if not exists usage jsonb not null default '{}'::jsonb;

-- One row per Anthropic message batch. Saved so grading picks up again after a server restart.
create table if not exists grading_batches (
  id text primary key,
  activity_id text not null references activities(id) on delete cascade,
  provider_batch_id text not null,
  requests jsonb not null,               -- {"custom_id": "submission_id"}
  status text not null default 'processing' check (status in ('processing', 'ended')),
  total integer not null,
  done integer not null default 0,
  model text not null,
  submitted_at timestamptz not null default now(),
  ended_at timestamptz
);
create index if not exists grading_batches_activity on grading_batches(activity_id);
create index if not exists grading_batches_status on grading_batches(status);
alter table grading_batches enable row level security;
