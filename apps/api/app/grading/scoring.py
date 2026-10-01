"""Deterministic scoring and routing. Never trust the model's arithmetic or its routing.

The activity's rubric is the single source of truth for the score breakdown:
- Every rubric criterion appears in the breakdown with exactly the teacher's points as its maximum.
- A unit's points_max is the points of the criterion it counts toward (the model's own number is ignored), and
  points_awarded is clamped to [0, that maximum].
- A criterion's earned points = min(criterion points, sum of its units' points); criteria without any unit earn 0 and
  are marked "assessed": False so the teacher sees them (the grader adds an "unclear" unit for them).
- A problem's score is the sum of its criteria; the maximum is the rubric total.
- A paper is flagged (needs_review) if any unit is unclear, any unit confidence < 0.75, any problem overall
  confidence < 0.75, or the model added any flag. Otherwise it is ready to approve.
"""
from __future__ import annotations

import copy

THRESHOLD = 0.75


def _r(x: float) -> float:
    return round(float(x) + 0.0, 2)


def criterion_points(rubric: list[dict]) -> dict[str, float]:
    return {c["name"].strip().lower(): float(c["points"]) for c in rubric}


def clean_problem(problem: dict, rubric: list[dict]) -> dict:
    """Return a copy of a problem result with clamped points and recomputed scores."""
    p = copy.deepcopy(problem)
    crit = criterion_points(rubric)
    for u in p["units"]:
        cap = crit.get(str(u.get("criterion", "")).strip().lower())
        # The rubric decides the maximum, not the model.
        u["points_max"] = _r(cap if cap is not None else 0.0)
        u["points_awarded"] = _r(min(max(0.0, float(u.get("points_awarded") or 0)), u["points_max"]))
        u["confidence"] = min(max(float(u.get("confidence") or 0), 0.0), 1.0)
    p["criteria_scores"] = criteria_breakdown(p["units"], rubric)
    p["suggested_score"] = _r(sum(c["awarded"] for c in p["criteria_scores"]))
    p["max_score"] = _r(sum(crit.values()))
    p["overall_confidence"] = min(max(float(p.get("overall_confidence") or 0), 0.0), 1.0)
    return p


def criteria_breakdown(units: list[dict], rubric: list[dict]) -> list[dict]:
    out = []
    for c in rubric:
        name = c["name"].strip().lower()
        mine = [u for u in units if str(u.get("criterion", "")).strip().lower() == name]
        got = sum(float(u.get("points_awarded") or 0) for u in mine)
        out.append({"name": c["name"], "description": c.get("description", ""), "awarded": _r(min(got, float(c["points"]))),
                    "points": float(c["points"]), "assessed": bool(mine)})
    return out


def apply_edits(problem: dict, edits: dict[str, dict], rubric: list[dict]) -> dict:
    """Overlay teacher unit edits (keyed 'problem_id:index') and recompute."""
    p = copy.deepcopy(problem)
    for u in p["units"]:
        e = edits.get(f"{p['problem_id']}:{u['index']}")
        if e:
            for k in ("points_awarded", "transcribed_text", "verdict", "error_type", "comment"):
                if k in e:
                    u[k] = e[k]
            u["edited"] = True
    return clean_problem(p, rubric)


def paper_flags(problems: list[dict]) -> list[str]:
    flags: list[str] = []
    for p in problems:
        for f in p.get("flags") or []:
            if f not in flags:
                flags.append(f)
    return flags


def paper_confidence(problems: list[dict]) -> float:
    return min((float(p.get("overall_confidence") or 0) for p in problems), default=0.0)


def needs_teacher(problems: list[dict]) -> bool:
    if paper_flags(problems):
        return True
    for p in problems:
        if float(p.get("overall_confidence") or 0) < THRESHOLD:
            return True
        for u in p["units"]:
            if u.get("verdict") == "unclear" or float(u.get("confidence") or 0) < THRESHOLD:
                return True
    return False


def route(problems: list[dict]) -> str:
    return "needs_review" if needs_teacher(problems) else "ready"


def problem_needs_teacher(p: dict) -> bool:
    return bool(p.get("flags")) or float(p.get("overall_confidence") or 0) < THRESHOLD or any(
        u.get("verdict") == "unclear" or float(u.get("confidence") or 0) < THRESHOLD for u in p["units"]
    )


def focus_problem(problems: list[dict]) -> dict | None:
    """The problem the teacher should look at first: lowest confidence among flagged problems (else overall)."""
    if not problems:
        return None
    flagged = [p for p in problems if problem_needs_teacher(p)] or problems

    def key(p: dict) -> float:
        units = [float(u.get("confidence") or 0) for u in p["units"]] or [1.0]
        return min(float(p.get("overall_confidence") or 0), min(units))

    return min(flagged, key=key)


def queue_chips(problems: list[dict], error_label) -> list[str]:
    """Flag chips for the queue: model flags plus '<type> error' for low-confidence error units."""
    from .flags import FLAG_LABELS

    chips = [FLAG_LABELS.get(f, f) for f in paper_flags(problems)]
    for p in problems:
        for u in p["units"]:
            if u.get("verdict") == "error" and u.get("error_type") and float(u.get("confidence") or 0) < THRESHOLD:
                chip = f"{error_label(u['error_type'])} error"
                if chip not in chips:
                    chips.append(chip)
    return chips


def paper_total(problems: list[dict], problem_scores: dict[str, float] | None = None) -> float:
    ps = problem_scores or {}
    return _r(sum(float(ps[p["problem_id"]]) if ps.get(p["problem_id"]) is not None else p["suggested_score"] for p in problems))


def rubric_problems(criteria: list[dict], total: float | None) -> list[str]:
    """Teacher-facing reasons a rubric cannot be used for grading (empty list = valid). Never fixes points silently."""
    errs: list[str] = []
    if not criteria:
        return ["The rubric has no criteria yet. Add at least one criterion."]
    names = [str(c.get("name", "")).strip() for c in criteria]
    if any(not n for n in names):
        errs.append("Every rubric criterion needs a name.")
    dup = sorted({n for n in names if n and names.count(n) > 1} | {n for n in names if n and [x.lower() for x in names].count(n.lower()) > 1})
    if dup:
        errs.append(f"Criterion names must be different: {', '.join(dup)}.")
    pts = []
    for c in criteria:
        try:
            v = float(c.get("points"))
        except (TypeError, ValueError):
            v = 0.0
        if v <= 0:
            errs.append(f"\"{c.get('name') or 'Unnamed criterion'}\" needs more than 0 points.")
        pts.append(v)
    s = round(sum(pts), 2)
    if total is None or float(total) <= 0:
        errs.append("Enter the rubric's total points.")
    elif abs(s - float(total)) > 1e-6:
        errs.append(f"The criteria add up to {s:g} points, but the rubric total is {float(total):g}. Make them match before grading.")
    return errs


def spread_score(problem_id: str, criteria_scores: list[dict], target: float) -> dict[str, float]:
    """Criterion scores ("problem_id::criterion" -> points) that move a problem from its computed score to `target`.

    Used for the sample data and to carry over per-problem overrides saved before scores were edited per criterion.
    Each criterion stays within 0..its rubric points, so the total is still the sum of the criteria."""
    diff = round(float(target) - sum(c["awarded"] for c in criteria_scores), 2)
    out: dict[str, float] = {}
    for c in criteria_scores if diff > 0 else list(reversed(criteria_scores)):
        if abs(diff) < 1e-9:
            break
        room = c["points"] - c["awarded"] if diff > 0 else -c["awarded"]
        step = min(diff, room) if diff > 0 else max(diff, room)
        if step:
            out[f"{problem_id}::{c['name']}"] = round(c["awarded"] + step, 2)
            diff = round(diff - step, 2)
    return out
