# Samples

Handwritten test papers for the evaluation (document Section 11). **No real student work.** Papers are written by our
team or consenting adult volunteers, using our own problems (the seeded activities), with planted errors.

```
samples/
  math/       photos + ground truth for "Solving Linear Equations: Quiz 1"  (act-linear-eq-quiz1)
  science/    photos + ground truth for "Forces and Motion: Quiz 2"         (act-forces-motion-quiz2)
  grammar/    photos + ground truth for "Subject-Verb Agreement: Worksheet 3" (act-sva-worksheet3)
  synthetic/  font-rendered papers for smoke tests ONLY (never in the reported evaluation)
  cache/      demo-mode AI results keyed by image SHA-256 (written by evaluate.py --write-cache)
  eval/       evaluation reports (report.md, report.json)
```

## Adding a paper

1. Photograph the paper (flat, good light, no names). Save as `samples/<subject>/<name>.jpg`.
2. Copy `ground_truth.template.json` to `samples/<subject>/<name>.json` and fill it in:
   - `style`: one of `neat`, `cursive`, `slanted`, `cramped` (results are reported per style).
   - `student_name` / `student_id`: what is written at the top of the paper (fictional names only), or `null` if the
     paper has no name. Used to measure identity reading, which is reported separately from grading.
   - `transcript`: what is actually written, one line per step (grammar: the revised sentence, then the rule).
   - `units`: one entry per rubric criterion with the points a careful teacher gives.
   - `planted_errors`: every error you planted on purpose, with its criterion and error type.
   Problem ids are `<activity_id>-p<number>`.
3. Run `python scripts/evaluate.py`.

Target: about 15 papers, 3 to 4 writers, 15 to 20 planted errors across the error types.
