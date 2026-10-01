"""One vision call per paper: transcribe + split into units + grade against the rubric (document Section 6.4)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..config import API_DIR, get_settings
from ..models import ERROR_TYPES, PaperOut
from . import images, llm
from .scoring import clean_problem, paper_confidence, paper_flags, route

PROMPT_VERSION = "v1.3"  # v1.1: student identity; v1.2: every rubric criterion must be assessed; v1.3: no totals, compact JSON
PROMPT_FILE = API_DIR / "prompts" / f"grade_{PROMPT_VERSION}.txt"

NOUNS = {
    "math": ("problem", "problems", "step", "steps"),
    "science": ("problem", "problems", "step", "steps"),
    "grammar": ("item", "items", "correction", "corrections"),
}


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_prompt(activity: dict, problems: list[dict], rubric: list[dict]) -> str:
    subject = activity["subject"]
    settings = activity.get("settings") or {}
    pn, pns, un, uns = NOUNS[subject]
    if subject == "grammar":
        unit_rule = (
            "A correction is one error the student found and fixed in the sentence (for example \"are\" to \"is\"), "
            "or one error the student missed. Also add one unit for the student's rule explanation (criterion 'Rule explanation') "
            "and one for spelling and punctuation of the whole revision (criterion 'Spelling and punctuation')."
        )
        alt_rule = (
            "Accept other valid corrections that are grammatical and keep the meaning, and add the flag \"alternate_method\"."
            if settings.get("accept_alternate", True)
            else "Only the corrected version in the answer key is correct."
        )
    else:
        unit_rule = "A step is one line or one transformation of the student's work. Keep the student's notation."
        alt_rule = (
            "Accept alternate valid methods that reach a correct result with correct reasoning; give full credit and add the flag \"alternate_method\"."
            if settings.get("accept_alternate", True)
            else "Grade against the method in the sample solution."
        )
    units_rule = (
        "Units are required: a final answer with missing or wrong units is an error of type \"units_and_notation\"."
        if subject == "science" and settings.get("require_units")
        else "Follow the rubric for answer formatting."
    )
    if settings.get("feedback_style") == "full_solution":
        feedback_rule = "The teacher allows full solutions: point to the first error and show the corrected step."
    else:
        feedback_rule = (
            "HINT ONLY: point to where the first error is and ask a guiding question. Never give the correct answer, "
            "the corrected line, or the full solution."
        )
    payload = {
        "title": activity["title"],
        "subject": subject,
        "settings": settings,
        "rubric": [{"criterion": c["name"], "points": c["points"], "description": c.get("description", "")} for c in rubric],
        pns: [
            {
                "problem_id": p["id"],
                "number": p["position"],
                "text": p["text"],
                "expected_answer": p["expected_answer"],
                "sample_solution": p.get("sample_solution") or "",
                **({"grammar_rule_tested": p.get("rule")} if p.get("rule") else {}),
            }
            for p in problems
        ],
    }
    return llm.render(
        PROMPT_FILE.read_text(),
        PROBLEM_NOUN=pn,
        UNIT_NOUN=un,
        UNIT_NOUN_PLURAL=uns,
        UNIT_RULE=unit_rule,
        ALTERNATE_RULE=alt_rule,
        UNITS_RULE=units_rule,
        FEEDBACK_RULE=feedback_rule,
        ACTIVITY_JSON=json.dumps(payload, indent=2, ensure_ascii=False),
        ERROR_TYPES=json.dumps(ERROR_TYPES[subject]),
    )


def _validate(raw: dict, activity: dict, problems: list[dict], rubric: list[dict]) -> PaperOut:
    out = PaperOut.model_validate(raw)
    out.check_against(activity["subject"], [p["id"] for p in problems], [c["name"] for c in rubric])
    return out


def missing_criteria(out: PaperOut, rubric: list[dict]) -> dict[str, list[str]]:
    """Rubric criteria with no unit, per problem."""
    gaps: dict[str, list[str]] = {}
    for p in out.problems:
        have = {u.criterion.strip().lower() for u in p.units}
        miss = [c["name"] for c in rubric if c["name"].strip().lower() not in have]
        if miss:
            gaps[p.problem_id] = miss
    return gaps


def fill_missing(raw: dict, rubric: list[dict]) -> dict:
    """Add an 'unclear', 0-point unit for every criterion the model did not assess, so the teacher scores it.

    Points are never invented: the placeholder earns 0 and routes the paper to Needs review."""
    import copy

    raw = copy.deepcopy(raw)
    for p in raw.get("problems", []):
        have = {str(u.get("criterion", "")).strip().lower() for u in p.get("units", [])}
        nxt = max([int(u.get("index") or 0) for u in p.get("units", [])] + [0]) + 1
        for c in rubric:
            if c["name"].strip().lower() not in have:
                p.setdefault("units", []).append({
                    "index": nxt, "transcribed_text": "", "alt_reading": None, "verdict": "unclear", "error_type": None,
                    "criterion": c["name"], "points_awarded": 0, "points_max": c["points"], "confidence": 0.0,
                    "comment": "Not scored by the AI. Please check the paper and score this criterion.", "bbox": None,
                })
                nxt += 1
    return raw


def _cache_path(h: str) -> Path:
    return get_settings().demo_cache_dir / f"{h}.json"


def demo_cached(data: bytes) -> bool:
    """True when DEMO_MODE will answer this paper from samples/cache without calling the AI."""
    return get_settings().demo_mode and _cache_path(image_hash(data)).exists()


def build_messages(data: bytes, media_type: str, activity: dict, problems: list[dict], rubric: list[dict]) -> list[dict]:
    """The grading request for one paper: the (shrunk) photo, then the prompt."""
    data, media_type = images.prepare(data, media_type)
    block = llm.pdf_block(data) if media_type == "application/pdf" else llm.image_block(data, media_type)
    return [{"role": "user", "content": [block, {"type": "text", "text": build_prompt(activity, problems, rubric)}]}]


def grade_image(data: bytes, media_type: str, activity: dict, problems: list[dict], rubric: list[dict],
                first_response=None, usage: dict | None = None) -> dict:
    """Grade one paper. Returns an ai_results-shaped dict (without ids) plus 'status'.

    `first_response` is a Messages API response that was already produced (by the Batch API, see services/batches.py);
    it is checked like a live reply, and only the retry, if one is needed, is a live call.
    `usage` collects token counts and is stored with the result.

    On invalid JSON: retry once with the validation error appended. If that fails too, the paper is marked
    'failed' with the flag 'grading_failed' so the teacher grades it by hand.
    """
    s = get_settings()
    h = image_hash(data)
    started = datetime.now(timezone.utc).isoformat()
    usage = {} if usage is None else usage

    if s.demo_mode and _cache_path(h).exists():
        cached = json.loads(_cache_path(h).read_text())
        return _finish(fill_missing(cached["raw_json"], rubric), activity, problems, rubric, cached.get("model", "demo-cache"), started, cached=True)

    messages = build_messages(data, media_type, activity, problems, rubric)
    last_error = ""
    reply = ""
    for attempt in range(2):
        try:
            if attempt == 0 and first_response is not None:
                llm.add_usage(usage, getattr(first_response, "usage", None), batch=True)
                reply = llm.reply_text(first_response)
            else:
                reply = llm.call(messages, usage=usage)
            raw = llm.extract_json(reply)
            out = _validate(raw, activity, problems, rubric)
            gaps = missing_criteria(out, rubric)
            if gaps and attempt == 0:
                raise ValueError("Every rubric criterion must be assessed. Missing: " + "; ".join(f"{pid}: {', '.join(c)}" for pid, c in gaps.items()))
            if gaps:
                raw = fill_missing(raw, rubric)
            result = _finish(raw, activity, problems, rubric, s.anthropic_model, started, usage=usage)
            if s.demo_mode:
                s.demo_cache_dir.mkdir(parents=True, exist_ok=True)
                _cache_path(h).write_text(json.dumps({"model": s.anthropic_model, "raw_json": raw}, indent=1))
            return result
        except llm.LLMUnavailable:
            raise
        except (ValueError, ValidationError, json.JSONDecodeError) as e:
            last_error = str(e)[:2000]
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": reply or "(no reply)"},
                    {
                        "role": "user",
                        "content": f"Your reply did not pass validation:\n{last_error}\nReturn the corrected JSON object only.",
                    },
                ]
    return failed_result(activity, problems, rubric, s.anthropic_model, started, last_error, reply, usage=usage)


def _finish(raw: dict, activity: dict, problems: list[dict], rubric: list[dict], model: str, started: str, cached: bool = False,
            usage: dict | None = None) -> dict:
    out = _validate(raw, activity, problems, rubric)
    by_id = {p["id"]: p for p in problems}
    cleaned = []
    for p in sorted(out.problems, key=lambda p: by_id[p.problem_id]["position"]):
        d = p.model_dump()
        d["expected_answer"] = by_id[p.problem_id]["expected_answer"]  # from the answer key, not the model
        cleaned.append(clean_problem(d, rubric))
    return {
        "problem_results": cleaned,
        "suggested_score": round(sum(p["suggested_score"] for p in cleaned), 2),
        "max_score": round(sum(p["max_score"] for p in cleaned), 2),
        "overall_confidence": paper_confidence(cleaned),
        "flags": paper_flags(cleaned),
        "model": model + (" (demo cache)" if cached else ""),
        "prompt_version": PROMPT_VERSION,
        "raw_json": raw,
        "created_at": started,
        "identity": out.identity(),  # separate from grading confidence; never affects scores or routing
        "usage": usage or {},  # token counts for this paper (see llm.add_usage); empty for the demo cache
        "status": route(cleaned),
    }


INCOMPLETE = "The AI's answer for this paper was incomplete. Press Grade again, or grade it by hand."


def failed_result(activity: dict, problems: list[dict], rubric: list[dict], model: str, started: str, error: str, reply: str = "",
                  teacher_message: str = INCOMPLETE, usage: dict | None = None) -> dict:
    """A 'needs teacher' result. `error` is the technical reason (stored, backend only); `teacher_message` is shown."""
    total = sum(float(c["points"]) for c in rubric)
    cleaned = [
        {
            "problem_id": p["id"],
            "expected_answer": p["expected_answer"],
            "units": [],
            "criteria_scores": [{"name": c["name"], "description": c.get("description", ""), "awarded": 0.0, "points": float(c["points"]), "assessed": False} for c in rubric],
            "suggested_score": 0.0,
            "max_score": total,
            "overall_confidence": 0.0,
            "flags": ["grading_failed"],
            "student_hint": "",
        }
        for p in problems
    ]
    return {
        "problem_results": cleaned,
        "suggested_score": 0.0,
        "max_score": total * len(problems),
        "overall_confidence": 0.0,
        "flags": ["grading_failed"],
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "raw_json": {"error": error, "teacher_message": teacher_message, "reply": reply[:4000]},
        "identity": {"student_name": None, "student_id": None, "identity_confidence": 0.0},
        "usage": usage or {},
        "created_at": started,
        "status": "failed",
    }
