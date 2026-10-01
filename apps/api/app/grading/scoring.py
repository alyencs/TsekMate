"""Deterministic scoring and routing. Never trust the model's arithmetic or its routing.

Rules (brief Section 8):
- points_awarded is clamped to [0, points_max], and points_max to the criterion's points.
- A problem's score is the sum over rubric criteria of min(criterion points, sum of unit points for that criterion).
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
        pmax = float(u.get("points_max") or 0)
        if cap is not None:
            pmax = min(pmax, cap) if pmax > 0 else cap
        u["points_max"] = _r(max(0.0, pmax))
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
        got = sum(float(u.get("points_awarded") or 0) for u in units if str(u.get("criterion", "")).strip().lower() == name)
        out.append({"name": c["name"], "awarded": _r(min(got, float(c["points"]))), "points": float(c["points"])})
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
