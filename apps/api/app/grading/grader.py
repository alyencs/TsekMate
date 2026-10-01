"""One vision call per paper: transcribe + split into units + grade against the rubric (document Section 6.4)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..config import API_DIR, get_settings
from ..models import ERROR_TYPES, PaperOut
from . import llm
from .scoring import clean_problem, paper_confidence, paper_flags, route

PROMPT_VERSION = "v1.0"
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


def _cache_path(h: str) -> Path:
    return get_settings().demo_cache_dir / f"{h}.json"


def grade_image(data: bytes, media_type: str, activity: dict, problems: list[dict], rubric: list[dict]) -> dict:
    """Grade one paper. Returns an ai_results-shaped dict (without ids) plus 'status'.

    On invalid JSON: retry once with the validation error appended. If that fails too, the paper is marked
    'failed' with the flag 'grading_failed' so the teacher grades it by hand.
    """
    s = get_settings()
    h = image_hash(data)
    started = datetime.now(timezone.utc).isoformat()

    if s.demo_mode and _cache_path(h).exists():
        cached = json.loads(_cache_path(h).read_text())
        return _finish(cached["raw_json"], activity, problems, rubric, cached.get("model", "demo-cache"), started, cached=True)

    prompt = build_prompt(activity, problems, rubric)
    block = llm.pdf_block(data) if media_type == "application/pdf" else llm.image_block(data, media_type)
    messages: list[dict] = [{"role": "user", "content": [block, {"type": "text", "text": prompt}]}]
    last_error = ""
    reply = ""
    for attempt in range(2):
        try:
            reply = llm.call(messages)
            raw = llm.extract_json(reply)
            _validate(raw, activity, problems, rubric)
            result = _finish(raw, activity, problems, rubric, s.gemini_model, started)
            if s.demo_mode:
                s.demo_cache_dir.mkdir(parents=True, exist_ok=True)
                _cache_path(h).write_text(json.dumps({"model": s.gemini_model, "raw_json": raw}, indent=1))
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
    return failed_result(activity, problems, rubric, s.gemini_model, started, last_error, reply)


def _finish(raw: dict, activity: dict, problems: list[dict], rubric: list[dict], model: str, started: str, cached: bool = False) -> dict:
    out = _validate(raw, activity, problems, rubric)
    order = {p["id"]: p["position"] for p in problems}
    cleaned = [clean_problem(p.model_dump(), rubric) for p in sorted(out.problems, key=lambda p: order[p.problem_id])]
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
        "status": route(cleaned),
    }


def failed_result(activity: dict, problems: list[dict], rubric: list[dict], model: str, started: str, error: str, reply: str = "") -> dict:
    total = sum(float(c["points"]) for c in rubric)
    cleaned = [
        {
            "problem_id": p["id"],
            "expected_answer": p["expected_answer"],
            "units": [],
            "criteria_scores": [{"name": c["name"], "awarded": 0.0, "points": float(c["points"])} for c in rubric],
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
        "raw_json": {"error": error, "reply": reply[:4000]},
        "created_at": started,
        "status": "failed",
    }
