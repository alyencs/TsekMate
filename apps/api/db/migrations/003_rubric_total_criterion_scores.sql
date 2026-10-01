-- Migration 003: rubric totals and per-criterion teacher scores.
-- For databases created before this change. Safe to run more than once. Existing rubrics are kept as they are.

-- The declared points per problem. Existing rubrics get the sum of their criteria, so nothing is re-scored.
alter table rubrics add column if not exists total_points numeric;
update rubrics r
   set total_points = (select coalesce(sum((c->>'points')::numeric), 0) from jsonb_array_elements(r.criteria) c)
 where total_points is null;

-- Teacher edits are now stored per rubric criterion ("problem_id::criterion" -> points), and the problem score is
-- always the sum of its criteria. The old per-problem overrides (problem_scores) are kept but no longer read;
-- approved scores already saved in teacher_reviews.final_score are unchanged.
alter table teacher_reviews add column if not exists criterion_scores jsonb not null default '{}'::jsonb;
