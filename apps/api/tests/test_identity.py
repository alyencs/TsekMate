from app.models import PaperOut
from app.services.roster import match, name_score

ROSTER = [{"id": "2026-001", "name": "Juan Dela Cruz"}, {"id": "2026-002", "name": "Maria Santos"}, {"id": "2026-003", "name": "Alex Reyes"}]


def ident(name=None, sid=None, conf=0.9):
    return {"student_name": name, "student_id": sid, "identity_confidence": conf}


def test_match_by_id_and_by_name():
    assert match(ROSTER, ident(sid="2026 - 002"), {}, "s1")["student_id"] == "2026-002"
    m = match(ROSTER, ident(name="Dela Cruz, Juan"), {}, "s1")
    assert m["status"] == "matched" and m["method"] == "name" and m["student_id"] == "2026-001"
    assert name_score("Maria Santos", "maria  santos") == 1.0


def test_missing_low_confidence_conflict_and_duplicate_stay_unidentified():
    assert match(ROSTER, ident(), {}, "s1")["status"] == "unidentified"
    low = match(ROSTER, ident(name="Alex Reyes", conf=0.3), {}, "s1")
    assert low["status"] == "unidentified" and low["suggested_student_id"] == "2026-003"
    conflict = match(ROSTER, ident(name="Maria Santos", sid="2026-001"), {}, "s1")
    assert conflict["status"] == "unidentified" and "ID on the paper" in conflict["reason"]
    dup = match(ROSTER, ident(sid="2026-003"), {"2026-003": "other"}, "s1")
    assert dup["status"] == "unidentified" and "already has a paper" in dup["reason"]
    assert match(ROSTER, ident(sid="2026-003"), {"2026-003": "s1"}, "s1")["status"] == "matched"  # its own paper
    assert match(ROSTER, ident(name="Someone Else"), {}, "s1")["status"] == "unidentified"


def test_identity_never_fails_validation():
    base = {"problems": []}
    for bad in [{"student_name": 42}, {"student_name": ["x"]}, {"identity_confidence": "high"}, {"student_id": "null"}, {}]:
        p = PaperOut.model_validate({**base, **bad})
        assert p.identity()["identity_confidence"] == 0.0 or p.student_name
    p = PaperOut.model_validate({**base, "student_name": "  Juan   Dela Cruz ", "identity_confidence": 1.7})
    assert p.student_name == "Juan Dela Cruz" and p.identity_confidence == 1.0
