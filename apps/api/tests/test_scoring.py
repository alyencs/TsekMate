from app.grading.scoring import apply_edits, clean_problem, focus_problem, queue_chips, route

RUBRIC = [
    {"name": "Setup", "points": 2},
    {"name": "Method", "points": 3},
    {"name": "Computation", "points": 3},
    {"name": "Final answer", "points": 2},
]


def unit(i, crit, pts, pmax, verdict="correct", conf=0.95, et=None):
    return {"index": i, "transcribed_text": "x", "alt_reading": None, "verdict": verdict, "error_type": et, "criterion": crit,
            "points_awarded": pts, "points_max": pmax, "confidence": conf, "comment": "", "bbox": None}


def problem(units, conf=0.9, flags=None, score=99):
    return {"problem_id": "p1", "expected_answer": "x = 17", "units": units, "suggested_score": score, "max_score": 99,
            "overall_confidence": conf, "flags": flags or [], "student_hint": ""}


def test_score_is_recomputed_not_trusted():
    p = clean_problem(problem([unit(1, "Setup", 2, 2), unit(2, "Method", 1, 3), unit(3, "Computation", 2, 3), unit(4, "Final answer", 0, 2)], score=10), RUBRIC)
    assert p["suggested_score"] == 5
    assert p["max_score"] == 10


def test_points_clamped_to_unit_and_criterion_max():
    p = clean_problem(problem([unit(1, "Setup", 5, 4), unit(2, "Method", -1, 3)]), RUBRIC)
    assert p["units"][0]["points_max"] == 2  # capped at the criterion's points
    assert p["units"][0]["points_awarded"] == 2
    assert p["units"][1]["points_awarded"] == 0


def test_criterion_total_capped_when_several_units_share_it():
    p = clean_problem(problem([unit(1, "Method", 3, 3), unit(2, "Method", 3, 3)]), RUBRIC)
    method = next(c for c in p["criteria_scores"] if c["name"] == "Method")
    assert method["awarded"] == 3
    assert p["suggested_score"] == 3


def test_teacher_edit_changes_score():
    p = clean_problem(problem([unit(1, "Setup", 2, 2), unit(2, "Method", 1, 3)]), RUBRIC)
    e = apply_edits(p, {"p1:2": {"points_awarded": 2}}, RUBRIC)
    assert e["suggested_score"] == 4
    assert e["units"][1]["edited"] is True


def test_routing_rules():
    clean = [clean_problem(problem([unit(1, "Setup", 2, 2)]), RUBRIC)]
    assert route(clean) == "ready"
    assert route([clean_problem(problem([unit(1, "Setup", 2, 2, verdict="unclear")]), RUBRIC)]) == "needs_review"
    assert route([clean_problem(problem([unit(1, "Setup", 2, 2, conf=0.74)]), RUBRIC)]) == "needs_review"
    assert route([clean_problem(problem([unit(1, "Setup", 2, 2)], conf=0.7), RUBRIC)]) == "needs_review"
    assert route([clean_problem(problem([unit(1, "Setup", 2, 2)], flags=["alternate_method"]), RUBRIC)]) == "needs_review"
    # exactly 0.75 is not low
    assert route([clean_problem(problem([unit(1, "Setup", 2, 2, conf=0.75)], conf=0.75), RUBRIC)]) == "ready"


def test_focus_problem_and_chips():
    a = clean_problem({**problem([unit(1, "Setup", 2, 2)]), "problem_id": "a"}, RUBRIC)
    b = clean_problem({**problem([unit(1, "Final answer", 1, 2, verdict="error", conf=0.6, et="notation")], conf=0.62), "problem_id": "b"}, RUBRIC)
    assert focus_problem([a, b])["problem_id"] == "b"
    assert queue_chips([a, b], lambda k: k.capitalize()) == ["Notation error"]
