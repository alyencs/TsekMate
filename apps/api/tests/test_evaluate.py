"""The evaluation pipeline, run against synthetic papers with a stubbed model that answers from ground truth."""
import json

from app.config import get_settings
from app.grading import llm


def test_evaluate_metrics_with_stub(monkeypatch):
    import evaluate

    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "test-key")
    monkeypatch.setattr(s, "demo_mode", False)
    items = [i for i in evaluate.collect(include_synthetic=True) if i[1]["activity_id"] == "act-linear-eq-quiz1"][:2]
    assert items, "run scripts/make_synthetic.py first"
    queue = []
    for _img, gt in items:
        probs = []
        for gp in gt["problems"]:
            units = [
                {"index": i + 1, "transcribed_text": gp["transcript"][i], "alt_reading": None, "verdict": u["verdict"], "error_type": u["error_type"],
                 "criterion": u["criterion"], "points_awarded": u["points"], "points_max": 3, "confidence": 0.9, "comment": "", "bbox": None}
                for i, u in enumerate(gp["units"])
            ]
            probs.append({"problem_id": gp["problem_id"], "expected_answer": "", "units": units, "suggested_score": 0, "max_score": 10, "overall_confidence": 0.9, "flags": [], "student_hint": ""})
        queue.append(json.dumps({"problems": probs}))
    monkeypatch.setattr(llm, "call", lambda messages, max_tokens=16000, system=None: queue.pop(0))
    r = evaluate.evaluate(items, write_cache=False)
    assert r["rubric_item_agreement"]["rate"] == 1.0
    assert r["transcription_by_style"]["synthetic"]["mean_similarity"] == 1.0
    for v in r["catch_rate_by_error_type"].values():
        assert v["catch_rate"] == 1.0
    assert "SMOKE TEST" in evaluate.markdown(r, True, "stub")
