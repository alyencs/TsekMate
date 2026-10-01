-- Migration 005: safe grading state and one paper per student per activity (QA fixes B-1, B-2, B-5).
-- For databases created before this change. Safe to run more than once.

-- Id of the grading run that owns a paper while its status is 'grading'. A result is saved only when the paper still
-- carries the same id (compare-and-set), so a stale or interrupted run can never overwrite newer state.
alter table submissions add column if not exists grading_attempt text;

-- One paper per student per activity. Unidentified papers (student_id null) are not limited.
-- If this fails with "could not create unique index", find the duplicates first and delete or reassign one of each:
--   select activity_id, student_id, count(*) from submissions
--   where student_id is not null group by 1, 2 having count(*) > 1;
create unique index if not exists submissions_one_paper_per_student
  on submissions (activity_id, student_id) where student_id is not null;
