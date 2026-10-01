"""Match a graded paper to the class roster using the name / student ID read from the paper.

Rules (conservative on purpose; a wrong match is worse than "Not identified"):
1. A student ID that matches a roster ID exactly (digits compared) wins.
2. Otherwise a name that clearly matches one roster name (similarity >= 0.86 and clearly better than the next one).
3. If the ID and the name point at different students, or the reading is low-confidence, or the matched student
   already has another paper in this activity, the paper stays "Not identified" and the teacher assigns it.
Missing or unreadable identity never blocks grading.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

NAME_MATCH = 0.86
MIN_IDENTITY_CONFIDENCE = 0.5


def norm_name(name: str | None) -> str:
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    if "," in n:  # "Dela Cruz, Juan" -> "juan dela cruz"
        last, _, first = n.partition(",")
        n = f"{first} {last}"
    n = re.sub(r"[^a-z\s]", " ", n)
    return " ".join(sorted(n.split()))  # token order does not matter


def norm_id(sid: str | None) -> str:
    return re.sub(r"\D", "", sid or "")


def name_score(a: str | None, b: str | None) -> float:
    x, y = norm_name(a), norm_name(b)
    if not x or not y:
        return 0.0
    return difflib.SequenceMatcher(None, x, y).ratio()


def match(roster: list[dict], identity: dict, taken: dict[str, str], own_sub_id: str) -> dict:
    """roster: [{id, name}]; identity: {student_name, student_id, identity_confidence}; taken: student_id -> sub_id.

    Returns the submission identity record: {status, method, student_id, extracted_name, extracted_id,
    identity_confidence, suggested_student_id, reason}.
    """
    name, sid = identity.get("student_name"), identity.get("student_id")
    conf = float(identity.get("identity_confidence") or 0)
    base = {"extracted_name": name, "extracted_id": sid, "identity_confidence": round(conf, 2), "suggested_student_id": None}
    if not name and not sid:
        return {**base, "status": "unidentified", "method": None, "student_id": None, "reason": "No readable name or student ID on the paper."}

    by_id = {norm_id(s["id"]): s for s in roster}
    id_hit = by_id.get(norm_id(sid)) if norm_id(sid) else None
    scored = sorted(((name_score(name, s["name"]), s) for s in roster), key=lambda t: -t[0]) if name else []
    best = scored[0] if scored else (0.0, None)
    second = scored[1][0] if len(scored) > 1 else 0.0
    name_hit = best[1] if best[0] >= NAME_MATCH and best[0] - second >= 0.05 else None

    candidate, method = None, None
    if id_hit and name_hit and id_hit["id"] != name_hit["id"]:
        return {**base, "status": "unidentified", "method": None, "student_id": None, "suggested_student_id": id_hit["id"],
                "reason": f"The ID on the paper belongs to {id_hit['name']}, but the name looks like {name_hit['name']}."}
    if id_hit:
        candidate, method = id_hit, "id"
    elif name_hit:
        candidate, method = name_hit, "name"
    if not candidate:
        suggestion = best[1]["id"] if best[1] is not None and best[0] >= 0.7 else None
        return {**base, "status": "unidentified", "method": None, "student_id": None, "suggested_student_id": suggestion,
                "reason": "The name or ID on the paper does not match anyone on the class roster."}
    if conf < MIN_IDENTITY_CONFIDENCE:
        return {**base, "status": "unidentified", "method": None, "student_id": None, "suggested_student_id": candidate["id"],
                "reason": "The name on the paper is hard to read. Please confirm the student."}
    if taken.get(candidate["id"]) not in (None, own_sub_id):
        return {**base, "status": "unidentified", "method": None, "student_id": None, "suggested_student_id": candidate["id"],
                "reason": f"{candidate['name']} ({candidate['id']}) already has a paper for this activity."}
    return {**base, "status": "matched", "method": method, "student_id": candidate["id"], "reason": None}
