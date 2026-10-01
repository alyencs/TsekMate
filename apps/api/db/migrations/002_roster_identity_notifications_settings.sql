-- Migration 002: class roster names, paper identity, notifications, settings.
-- For databases created with the original schema.sql. Safe to run more than once.
-- After running it, reseed the demo data with: python scripts/seed.py --reset

alter table students add column if not exists name text not null default '';

alter table submissions alter column student_id drop not null;
alter table submissions add column if not exists identity jsonb;

alter table ai_results add column if not exists identity jsonb;

create table if not exists notifications (
  id text primary key,
  kind text not null,
  title text not null,
  body text not null default '',
  link text,
  activity_id text references activities(id) on delete cascade,
  submission_id text,
  read boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists app_settings (
  id text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

alter table notifications enable row level security;
alter table app_settings enable row level security;
