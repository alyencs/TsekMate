"""Build the demo database: 38 pseudonymous students, 4 activities, and pre-graded results that reproduce the mockup.

Usage: python scripts/seed.py --reset   (works against Supabase when SUPABASE_URL is set, else the in-memory store)

All seeded "AI results" are synthetic, labeled with model "seed-synthetic", and exist only so the demo screens have
data. They are never used in the evaluation report.
"""
from __future__ import annotations

import copy
import random
from datetime import datetime, timedelta, timezone

from .grading.scoring import clean_problem, paper_confidence, paper_flags, route
from .seed_data import ACTIVITIES, FRACTIONS, GRAMMAR, MATH, RUBRIC_TEMPLATES, SCIENCE
from .services.paper import render_paper_cached as render_paper
from .store.base import Store

SEED_MODEL = "seed-synthetic"
SEED_PROMPT = "v1.2"  # matches the mockup's review record; real results use the grader's PROMPT_VERSION

S = [f"S-{i:03d}" for i in range(1, 39)]
M = [f"M-{i:03d}" for i in range(1, 36)]

# ---------------------------------------------------------------- per-activity plans
# errors: (problem_index, variant, [fixed students], extra random count)
PLANS = {
    "math": {
        "students": S,
        "errors": [
            (1, "dist", ["S-014", "S-005", "S-007", "S-010", "S-012", "S-016", "S-018", "S-021", "S-023", "S-026", "S-029", "S-031", "S-034", "S-037"], 0),
            (4, "dist", ["S-007", "S-016", "S-026", "S-034"], 0),
            (0, "sub", ["S-004", "S-008", "S-013", "S-024", "S-033"], 0),
            (3, "sub", ["S-006", "S-015", "S-028", "S-038"], 0),
            (2, "comp", ["S-017", "S-022", "S-031"], 0),
            (1, "nota", ["S-001", "S-019"], 0),
            (3, "nota", ["S-009", "S-027", "S-036"], 0),
            (0, "pres", ["S-014", "S-003"], 0),
            (4, "pres", ["S-010"], 0),
        ],
        # status, overall confidence, review pattern
        "needs_review": {
            "S-014": ("special", 0.54),
            "S-002": ("blurry", 0.58),
            "S-009": ("lowconf_error", 0.62),
            "S-036": ("unclear", 0.66),
            "S-019": ("mismatch", 0.71),
            "S-025": ("subtle", 0.75),
            "S-027": ("lowconf_error", 0.72),
            "S-030": ("subtle", 0.84),
            "S-032": ("subtle", 0.88),
        },
        "ready": ["S-011", "S-020", "S-035"],
        "graded_today": ["S-014", "S-009", "S-011"],
        "approved_when": "today",
        "edited": {"S-003": {1: 7}},  # teacher overrides shown as "Edited" in the gradebook
    },
    "science": {
        "students": S,
        "errors": [
            (2, "units", ["S-022", "S-002", "S-004", "S-006", "S-009", "S-013", "S-018", "S-025", "S-030", "S-035"], 0),
            (1, "units", ["S-001", "S-004", "S-011", "S-018", "S-027", "S-033"], 0),
            (3, "units", ["S-006", "S-012", "S-020", "S-025", "S-029", "S-037"], 0),
            (0, "inv", ["S-003", "S-008", "S-015", "S-021", "S-034"], 0),
            (2, "inv", ["S-010", "S-016", "S-024", "S-038"], 0),
            (0, "comp", ["S-005", "S-019"], 0),
            (1, "comp", ["S-007", "S-014", "S-023"], 0),
            (2, "comp", ["S-017", "S-028"], 0),
            (3, "comp", ["S-026", "S-031", "S-036"], 0),
            (3, "pres", ["S-011", "S-032", "S-001", "S-008"], 0),
        ],
        "needs_review": {
            "S-022": ("special", 0.58),
            "S-030": ("unclear", 0.63),
            "S-009": ("lowconf_error", 0.69),
            "S-017": ("subtle", 0.77),
            "S-036": ("mismatch", 0.8),
        },
        "ready": ["S-002", "S-019"],
        "graded_today": [],
        "approved_when": "yesterday",
        "edited": {},
    },
    "grammar": {
        "students": S,
        "errors": [
            (3, "nearest", ["S-002", "S-004", "S-005", "S-008", "S-010", "S-012", "S-013", "S-016", "S-019", "S-021", "S-024", "S-027", "S-029", "S-033", "S-036"], 0),
            (0, "miss", ["S-006", "S-017", "S-025", "S-038"], 0),
            (3, "miss_s", ["S-031", "S-001", "S-009", "S-014", "S-022", "S-034"], 0),
            (1, "miss_s", ["S-003", "S-011", "S-018", "S-026", "S-030"], 0),
            (1, "spell", ["S-007", "S-020", "S-028", "S-035"], 0),
            (2, "spell", ["S-015", "S-023", "S-032", "S-037"], 0),
            (0, "punct", ["S-003", "S-009", "S-020"], 0),
            (2, "punct", ["S-001", "S-011", "S-026"], 0),
            (3, "punct", ["S-007", "S-018", "S-028"], 0),
            (4, "punct", ["S-005", "S-014", "S-030"], 0),
            (1, "word", ["S-010", "S-024", "S-037"], 0),
            (4, "word", ["S-004", "S-016", "S-034"], 0),
            (4, "rule", ["S-012", "S-031"], 0),
        ],
        "needs_review": {
            "S-031": ("special", 0.61),
            "S-012": ("unclear", 0.64),
            "S-019": ("lowconf_error", 0.68),
            "S-027": ("subtle", 0.72),
            "S-006": ("mismatch", 0.78),
            "S-033": ("subtle", 0.83),
            "S-038": ("lowconf_error", 0.7),
        },
        "ready": ["S-015", "S-023", "S-035"],
        "graded_today": [],
        "approved_when": "3days",
        "edited": {},
    },
    "fractions": {
        "students": M,
        "errors": [
            (0, "comp", [], 16),
            (1, "conc", [], 22),
            (2, "pres", [], 18),
            (3, "conc", [], 22),
            (4, "comp", [], 14),
        ],
        "needs_review": {},
        "ready": [],
        "graded_today": [],
        "approved_when": "4days",
        "edited": {},
    },
}


# ---------------------------------------------------------------- unit construction
def _base_units(spec: dict, prob: dict, rubric: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Correct-solution units for a problem, plus a map of symbolic keys (grammar) to indexes."""
    pts = {c["name"]: float(c["points"]) for c in rubric}
    units: list[dict] = []
    keys: dict[str, int] = {}
    if spec["subject"] == "grammar":
        n = len(prob["corrections"])
        share = round(pts["Finds the errors"] / n, 2)
        for label, _word in prob["corrections"]:
            units.append(_unit(len(units) + 1, label, "Finds the errors", share, ""))
        keys["rev"] = len(units)
        units.append(_unit(len(units) + 1, prob["revision"], "Correct revision", pts["Correct revision"], "All verbs agree with their subjects."))
        keys["rule"] = len(units)
        units.append(_unit(len(units) + 1, prob["explanation"], "Rule explanation", pts["Rule explanation"], ""))
        keys["spell"] = len(units)
        units.append(_unit(len(units) + 1, prob["revision"], "Spelling and punctuation", pts["Spelling and punctuation"], "No new spelling or punctuation errors."))
    else:
        for crit, text in prob["units"]:
            units.append(_unit(len(units) + 1, text, crit, pts[crit], ""))
    return units, keys


def _unit(index: int, text: str, criterion: str, pmax: float, comment: str) -> dict:
    return {
        "index": index,
        "transcribed_text": text,
        "alt_reading": None,
        "verdict": "correct",
        "error_type": None,
        "criterion": criterion,
        "points_awarded": pmax,
        "points_max": pmax,
        "confidence": 0.95,
        "comment": comment,
        "bbox": None,
    }


def _apply_variant(units: list[dict], keys: dict[str, int], variant: dict) -> None:
    for k, o in variant.get("units", {}).items():
        i = keys[k] if isinstance(k, str) else k
        u = units[i]
        if "text" in o:
            u["transcribed_text"] = o["text"]
        for src, dst in (("verdict", "verdict"), ("error_type", "error_type"), ("points", "points_awarded"), ("comment", "comment")):
            if src in o:
                u[dst] = o[src]
    if "revision" in variant and "rev" in keys:
        units[keys["rev"]]["transcribed_text"] = variant["revision"]
        if "rev_points" in variant:
            u = units[keys["rev"]]
            u["points_awarded"] = variant["rev_points"]
            u["verdict"] = "error"
            u["comment"] = "The revision still has an agreement error."
        if units[keys["spell"]]["verdict"] == "correct":
            units[keys["spell"]]["transcribed_text"] = variant["revision"]


def _student_answer(spec: dict, prob: dict, units: list[dict], keys: dict[str, int]) -> str:
    if spec["subject"] == "grammar":
        return units[keys["rev"]]["transcribed_text"]
    return units[-1]["transcribed_text"]


# ---------------------------------------------------------------- confidence patterns
def _confidences(rnd: random.Random, units_by_problem: list[list[dict]], flags_by_problem: list[list[str]], pattern: str | None, overall: float | None) -> list[float]:
    """Set unit confidences; return per-problem overall confidence."""
    for units in units_by_problem:
        for u in units:
            u["confidence"] = round(rnd.uniform(0.86, 0.99), 2)
    overalls = [round(min(0.99, min(u["confidence"] for u in us) + rnd.uniform(0.0, 0.04)), 2) for us in units_by_problem]
    if pattern is None:
        return overalls
    # choose the target problem: first problem with an error, else a random one
    target = next((i for i, us in enumerate(units_by_problem) if any(u["verdict"] == "error" for u in us)), rnd.randrange(len(units_by_problem)))
    us = units_by_problem[target]
    if pattern == "unclear":
        u = us[min(2, len(us) - 1)]
        u["verdict"], u["error_type"], u["confidence"] = "unclear", None, overall
        u["alt_reading"] = (u["transcribed_text"] + "?") if not u["alt_reading"] else u["alt_reading"]
        u["comment"] = "Handwriting unclear: please check this line."
        flags_by_problem[target].append("unclear_handwriting")
        overalls[target] = overall
    elif pattern == "lowconf_error":
        err = next((u for u in us if u["verdict"] == "error" and u["error_type"]), us[-1])
        err["confidence"] = overall
        overalls[target] = overall
    elif pattern == "subtle":
        us[0]["confidence"] = round(min(0.74, overall - 0.03), 2)
        overalls[target] = overall
    elif pattern == "mismatch":
        flags_by_problem[target].append("step_mismatch")
        us[1]["confidence"] = round(min(0.74, overall), 2)
        us[1]["comment"] = (us[1]["comment"] or "") + " This line does not clearly follow from the one before it."
        overalls[target] = overall
    elif pattern == "blurry":
        for u in us:
            u["confidence"] = round(rnd.uniform(0.55, 0.7), 2)
        us[2]["verdict"], us[2]["error_type"] = "unclear", None
        us[2]["comment"] = "The photo is blurry here; please check this line."
        flags_by_problem[target].append("unclear_handwriting")
        overalls[target] = overall
    return overalls


# ---------------------------------------------------------------- specials (exact mockup frames)
def _special(spec_key: str, student: str, units_by_problem: list[list[dict]], flags_by_problem: list[list[str]], overalls: list[float]) -> None:
    if spec_key == "math" and student == "S-014":
        us = units_by_problem[1]
        us[0].update(confidence=0.96, comment="Correctly identified the starting equation.")
        us[1].update(confidence=0.91)
        us[2].update(transcribed_text="x = 9?", alt_reading="x = 8", verdict="unclear", error_type=None, points_awarded=2, confidence=0.54, comment="Handwriting unclear: this could be 9 or 8.")
        us[3].update(confidence=0.88)
        flags_by_problem[1] = ["unclear_handwriting", "step_mismatch"]
        overalls[1] = 0.54
    if spec_key == "science" and student == "S-022":
        us = units_by_problem[2]
        us[0].update(confidence=0.97)
        us[1].update(confidence=0.93)
        us[2].update(transcribed_text="= 5", alt_reading="= 6", verdict="unclear", error_type=None, points_awarded=3, confidence=0.58, comment="Handwriting unclear: this could be 5 or 6.")
        us[3].update(confidence=0.90)
        flags_by_problem[2] = ["unclear_handwriting"]
        overalls[2] = 0.58
    if spec_key == "grammar" and student == "S-031":
        us = units_by_problem[3]
        us[0].update(confidence=0.95)
        us[1].update(confidence=0.92)
        us[2].update(confidence=0.94)
        us[3].update(confidence=0.9, comment="Two of the three verbs are fixed; 'say' still needs -s.")
        us[4].update(verdict="correct", error_type=None, points_awarded=2, transcribed_text='"The subject is team, not players."', confidence=0.88, comment="")
        us[5].update(transcribed_text='"practicing"', alt_reading='"practising"', verdict="unclear", error_type=None, points_awarded=1, confidence=0.61, comment="Handwriting smudged: practicing or practising?")
        flags_by_problem[3] = ["unclear_handwriting"]
        overalls[3] = 0.61


# ---------------------------------------------------------------- builder
def _assign(plan: dict, rnd: random.Random, n_problems: int) -> dict[str, dict[int, list[str]]]:
    out: dict[str, dict[int, list[str]]] = {s: {} for s in plan["students"]}
    for pi, variant, fixed, extra in plan["errors"]:
        chosen = list(fixed)
        pool = [s for s in plan["students"] if s not in chosen and pi not in out[s]]
        chosen += rnd.sample(pool, min(extra, len(pool)))
        for s in chosen:
            out[s].setdefault(pi, []).append(variant)
    return out


def _render(spec: dict, problems: list[dict], student: str, results: list[dict], blur: bool, seed: int) -> tuple[bytes, dict]:
    header = f"{spec['title'].split(':')[0]}    {student}"
    blocks = []
    for prob, res in zip(problems, results):
        lines = []
        if spec["subject"] == "grammar":
            rev_unit = next(u for u in res["units"] if u["criterion"] == "Correct revision")
            spell = next(u for u in res["units"] if u["criterion"] == "Spelling and punctuation")
            text = _wrap(rev_unit["transcribed_text"], 44)
            lines.append((f"{prob['id']}:rev", text, spell["verdict"] == "unclear"))
            rule = next(u for u in res["units"] if u["criterion"] == "Rule explanation")
            lines.append((f"{prob['id']}:rule", "Rule: " + rule["transcribed_text"].strip('"'), False))
        else:
            for u in res["units"]:
                lines.append((f"{prob['id']}:{u['index']}", u["transcribed_text"].replace("?", ""), u["verdict"] == "unclear"))
        blocks.append((f"{prob['position']}.", lines))
    png, boxes = render_paper(header, blocks, seed=seed, blur=blur, line_font=44 if spec["subject"] == "grammar" else 50)
    return png, boxes


def _wrap(text: str, width: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return "\n".join(lines)


def build(store: Store, now: datetime | None = None, with_images: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    rnd = random.Random(20260)
    store.insert("students", [{"id": s, "section": "Grade 8 Rizal"} for s in S] + [{"id": m, "section": "Grade 7 Mabini"} for m in M])
    store.insert("rubric_templates", copy.deepcopy(RUBRIC_TEMPLATES))

    when = {
        "today": now - timedelta(hours=1),
        "yesterday": now - timedelta(days=1, hours=1),
        "3days": now - timedelta(days=3),
        "4days": now - timedelta(days=4),
    }
    activity_updated = {"math": now - timedelta(minutes=20), "science": now - timedelta(days=1), "grammar": now - timedelta(days=1, hours=3), "fractions": now - timedelta(days=3)}
    counts = {}
    for spec in ACTIVITIES:
        key = spec["key"]
        plan = PLANS[key]
        problems = [
            {
                "id": f"{spec['id']}-p{i + 1}",
                "activity_id": spec["id"],
                "position": i + 1,
                "text": p["text"],
                "expected_answer": p["expected_answer"],
                "sample_solution": p.get("sample_solution", ""),
                "rule": p.get("rule", ""),
            }
            for i, p in enumerate(spec["problems"])
        ]
        total = sum(float(c["points"]) for c in spec["rubric"]) * len(problems)
        store.insert(
            "activities",
            {
                "id": spec["id"],
                "title": spec["title"],
                "subject": spec["subject"],
                "class_name": spec["class_name"],
                "date": spec["date"],
                "settings": spec["settings"],
                "total_points": total,
                "created_at": (now - timedelta(days=6)).isoformat(),
                "updated_at": activity_updated[key].isoformat(),
            },
        )
        store.insert("problems", problems)
        store.insert("rubrics", {"id": f"{spec['id']}-rubric", "activity_id": spec["id"], "criteria": spec["rubric"]})

        assignment = _assign(plan, rnd, len(problems))
        cluster_members: dict[str, list[str]] = {}
        approved_seq = 0
        subs, ai_rows, reviews = [], [], []
        for n, student in enumerate(plan["students"]):
            sub_id = f"sub-{key}-{student}"
            units_by_problem, keys_by_problem, flags_by_problem, hints = [], [], [], []
            for pi, prob in enumerate(spec["problems"]):
                units, keys = _base_units(spec, prob, spec["rubric"])
                hint = ""
                for vname in assignment[student].get(pi, []):
                    v = prob["variants"][vname]
                    _apply_variant(units, keys, v)
                    hint = v.get("hint", prob["hint"])
                    if v.get("cluster"):
                        for u in units:
                            if u["verdict"] == "error" and u["error_type"] == spec["clusters"][v["cluster"]]["error_type"]:
                                cluster_members.setdefault(v["cluster"], []).append(f"{sub_id}:{problems[pi]['id']}:{u['index']}")
                units_by_problem.append(units)
                keys_by_problem.append(keys)
                flags_by_problem.append([])
                hints.append(hint)
            pattern, overall = plan["needs_review"].get(student, (None, None))
            overalls = _confidences(rnd, units_by_problem, flags_by_problem, None if pattern == "special" else pattern, overall)
            if pattern == "special":
                _special(key, student, units_by_problem, flags_by_problem, overalls)

            results = []
            for pi, prob in enumerate(spec["problems"]):
                hint = hints[pi]
                if not hint and any(u["verdict"] != "correct" for u in units_by_problem[pi]):
                    hint = prob["hint"]
                res = {
                    "problem_id": problems[pi]["id"],
                    "expected_answer": prob["expected_answer"],
                    "student_answer": _student_answer(spec, prob, units_by_problem[pi], keys_by_problem[pi]),
                    "units": units_by_problem[pi],
                    "suggested_score": 0,
                    "max_score": 0,
                    "overall_confidence": overalls[pi],
                    "flags": flags_by_problem[pi],
                    "student_hint": hint or "Nice work. Every step follows the rubric.",
                }
                results.append(clean_problem(res, spec["rubric"]))

            blurry = pattern == "blurry"
            image_path = None
            image_hash = None
            if with_images:
                png, boxes = _render(spec, problems, student, results, blurry, seed=n * 7 + len(key))
                for r in results:
                    for u in r["units"]:
                        if spec["subject"] == "grammar":
                            k = f"{r['problem_id']}:rule" if u["criterion"] == "Rule explanation" else f"{r['problem_id']}:rev"
                        else:
                            k = f"{r['problem_id']}:{u['index']}"
                        u["bbox"] = boxes.get(k)
                image_path = f"seed/{sub_id}.jpg"
                store.put_image(image_path, png, "image/jpeg")
                import hashlib

                image_hash = hashlib.sha256(png).hexdigest()

            status = "approved"
            if student in plan["needs_review"]:
                status = "needs_review"
            elif student in plan["ready"]:
                status = "ready"
            computed = route(results)
            if status != "approved" and computed != status:
                raise AssertionError(f"seed routing mismatch for {key}/{student}: planned {status}, computed {computed}")
            graded_at = (now - timedelta(minutes=30 + n)) if student in plan["graded_today"] else (when["yesterday"] - timedelta(hours=2, minutes=n))
            if key in ("grammar", "fractions"):
                graded_at = when[plan["approved_when"]] - timedelta(hours=3, minutes=n)
            subs.append(
                {
                    "id": sub_id,
                    "activity_id": spec["id"],
                    "student_id": student,
                    "image_path": image_path,
                    "image_hash": image_hash,
                    "status": status,
                    "quality": {"ok": not blurry, "reason": "Image is blurry" if blurry else None},
                    "created_at": (graded_at - timedelta(minutes=5)).isoformat(),
                    "updated_at": graded_at.isoformat(),
                }
            )
            ai_rows.append(
                {
                    "id": f"ai-{sub_id}",
                    "submission_id": sub_id,
                    "problem_results": results,
                    "suggested_score": round(sum(r["suggested_score"] for r in results), 2),
                    "max_score": total,
                    "overall_confidence": paper_confidence(results),
                    "flags": paper_flags(results),
                    "model": SEED_MODEL,
                    "prompt_version": SEED_PROMPT,
                    "raw_json": None,
                    "created_at": graded_at.isoformat(),
                }
            )
            problem_scores = {}
            edits = plan["edited"].get(student, {})
            for pi, score in edits.items():
                problem_scores[problems[pi]["id"]] = score
            feedback = {r["problem_id"]: r["student_hint"] for r in results}
            approved = status == "approved"
            final = round(sum(problem_scores.get(r["problem_id"], r["suggested_score"]) for r in results), 2)
            approved_at = None
            if approved:
                base = when[plan["approved_when"]]
                approved_at = (base - timedelta(minutes=3 * n)).isoformat()
                approved_seq += 1
                if key == "science" and approved_seq > 18:  # 18 science approvals yesterday, the rest two days ago
                    approved_at = (now - timedelta(days=2, hours=2, minutes=n)).isoformat()
            reviews.append(
                {
                    "id": f"rev-{sub_id}",
                    "submission_id": sub_id,
                    "final_score": final if approved else None,
                    "unit_edits": {},
                    "problem_scores": problem_scores,
                    "feedback": feedback,
                    "edit_log": [
                        {"at": approved_at or graded_at.isoformat(), "field": f"problem_scores.{pid}", "from": None, "to": sc}
                        for pid, sc in problem_scores.items()
                    ],
                    "approved": approved,
                    "approved_at": approved_at,
                    "created_at": graded_at.isoformat(),
                    "updated_at": approved_at or graded_at.isoformat(),
                }
            )
        store.insert("submissions", subs)
        store.insert("ai_results", ai_rows)
        store.insert("teacher_reviews", reviews)
        if spec["clusters"]:
            store.insert(
                "class_summaries",
                {
                    "id": spec["id"],
                    "activity_id": spec["id"],
                    "signature": "seed",
                    "misconceptions": [
                        {"label": c["label"], "error_type": c["error_type"], "ids": cluster_members.get(ck, [])} for ck, c in spec["clusters"].items()
                    ],
                    "reteach_focus": spec["reteach_focus"],
                    "model": SEED_MODEL,
                    "prompt_version": "v1.0",
                    "created_at": now.isoformat(),
                },
            )
        counts[key] = {st: sum(1 for s in subs if s["status"] == st) for st in ("needs_review", "ready", "approved")}
    return counts


def reset_and_seed(store: Store, with_images: bool = True) -> dict:
    store.reset()
    return build(store, with_images=with_images)


__all__ = ["build", "reset_and_seed", "MATH", "SCIENCE", "GRAMMAR", "FRACTIONS"]
