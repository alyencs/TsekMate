"""The non-grading LLM calls: class misconceptions, practice problems, parent messages. Counts never come from here."""
from __future__ import annotations

import logging

from ..config import API_DIR, get_settings
from ..grading import llm
from ..grading.flags import error_label
from ..models import ERROR_TYPES

log = logging.getLogger("tsekmate.ai_text")
PROMPTS = API_DIR / "prompts"
NOUNS = {"math": ("problem", "problems"), "science": ("problem", "problems"), "grammar": ("item", "items")}


def misconceptions(b, keys: dict[str, tuple]) -> dict | None:
    """One LLM call that names misconceptions from grouped error comments. Returns None if unavailable."""
    s = get_settings()
    if not s.anthropic_api_key:
        return None
    lines = []
    for k, (_st, pid, u) in list(keys.items())[:400]:
        lines.append(f"{k} | {b.problem_label(pid)} | {u['error_type']} | {u['criterion']} | {u.get('comment', '')[:160]}")
    pn, pns = NOUNS[b.subject]
    prompt = llm.render(
        (PROMPTS / "summary_v1.0.txt").read_text(),
        PROBLEM_NOUN=pn,
        PROBLEMS_NOUN=pns,
        SUBJECT=b.subject,
        TITLE=b.activity["title"],
        COMMENTS="\n".join(lines),
        ERROR_TYPES=", ".join(ERROR_TYPES[b.subject]),
    )
    try:
        data = llm.extract_json(llm.call([{"role": "user", "content": prompt}], max_tokens=4000))
        out = []
        for m in data.get("misconceptions", [])[:3]:
            ids = [i for i in m.get("ids", []) if i in keys]
            if ids and isinstance(m.get("label"), str):
                et = m.get("error_type") if m.get("error_type") in ERROR_TYPES[b.subject] else keys[ids[0]][2]["error_type"]
                out.append({"label": m["label"].strip().rstrip("."), "error_type": et, "ids": ids})
        return {"misconceptions": out, "reteach_focus": str(data.get("reteach_focus", "")).strip(), "model": s.anthropic_model, "prompt_version": "v1.0"}
    except Exception as e:  # keep the summary page working with cached or code-only data
        log.warning("misconception call failed: %s", e)
        return None


def practice(b, focus: str, n: int = 2) -> dict:
    s = get_settings()
    pn, pns = NOUNS[b.subject]
    prompt = llm.render(
        (PROMPTS / "practice_v1.0.txt").read_text(),
        N=str(n if b.subject != "grammar" else 3),
        PROBLEMS_NOUN=pns,
        FOCUS=focus,
        SUBJECT=b.subject,
        TITLE=b.activity["title"],
        ORIGINALS="\n".join(f"- {p['text']}" for p in b.problems),
    )
    data = llm.extract_json(llm.call([{"role": "user", "content": prompt}], max_tokens=2000))
    items = [str(x) for x in data.get("items", []) if str(x).strip()]
    return {"items": items, "model": s.anthropic_model}


def parent_message(b, sub_id: str) -> dict:
    s = get_settings()
    probs = b.effective(sub_id)
    strengths, gaps = [], []
    totals: dict[str, list[float]] = {}
    for p in probs:
        for c in p.get("criteria_scores", []):
            t = totals.setdefault(c["name"], [0.0, 0.0])
            t[0] += c["awarded"]
            t[1] += c["points"]
        for u in p["units"]:
            if u.get("verdict") == "error" and u.get("error_type"):
                gaps.append(f"{error_label(u['error_type'])}: {u.get('comment', '')}")
    strengths = [k for k, (got, mx) in totals.items() if mx and got / mx >= 0.85]
    prompt = llm.render(
        (PROMPTS / "parent_v1.0.txt").read_text(),
        SUBJECT=b.subject,
        TITLE=b.activity["title"],
        STRENGTHS=", ".join(strengths) or "steady effort across the activity",
        GAPS="; ".join(gaps[:4]) or "no major gaps; keep practicing",
    )
    data = llm.extract_json(llm.call([{"role": "user", "content": prompt}], max_tokens=1500))
    return {"en": str(data.get("en", "")).strip(), "fil": str(data.get("fil", "")).strip(), "model": s.anthropic_model}
