"""Render SYNTHETIC handwriting-font papers for pipeline smoke tests only (checkpoint a, demo cache).

    python scripts/make_synthetic.py

Writes samples/synthetic/*.jpg plus ground-truth JSON. These are NEVER used in the reported evaluation
(evaluate.py skips files whose ground truth says "synthetic": true unless --include-synthetic is passed,
and then labels the run as a smoke test).
"""
import json
import random

import _path  # noqa: F401
from _path import ROOT
from app.seed_data import GRAMMAR, MATH, SCIENCE
from app.seed import NAMES, _apply_variant, _base_units, _wrap
from app.services.paper import render_paper

OUT = ROOT / "samples" / "synthetic"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)
    n = 0
    for spec in (MATH, SCIENCE, GRAMMAR):
        for k in range(4):
            gt_problems, blocks = [], []
            for i, prob in enumerate(spec["problems"]):
                units, keys = _base_units(spec, prob, spec["rubric"])
                planted = []
                if rnd.random() < 0.45 and prob["variants"]:
                    vname = rnd.choice(list(prob["variants"]))
                    _apply_variant(units, keys, prob["variants"][vname])
                    planted = [{"criterion": u["criterion"], "error_type": u["error_type"]} for u in units if u["verdict"] == "error" and u["error_type"]]
                pid = f"{spec['id']}-p{i + 1}"
                if spec["subject"] == "grammar":
                    rev = units[keys["rev"]]["transcribed_text"]
                    rule = units[keys["rule"]]["transcribed_text"].strip('"')
                    lines = [(f"{pid}:rev", _wrap(rev, 44), False), (f"{pid}:rule", "Rule: " + rule, False)]
                    transcript = [rev, rule]
                else:
                    lines = [(f"{pid}:{u['index']}", u["transcribed_text"], False) for u in units]
                    transcript = [u["transcribed_text"] for u in units]
                blocks.append((f"{i + 1}.", lines))
                gt_problems.append(
                    {
                        "problem_id": pid,
                        "transcript": transcript,
                        "units": [{"criterion": u["criterion"], "verdict": u["verdict"], "error_type": u["error_type"], "points": u["points_awarded"]} for u in units],
                        "planted_errors": planted,
                    }
                )
            name = f"{spec['key']}-synthetic-{k + 1:02d}"
            sid = ["2026-002", "2026-009", "2026-019"][k % 3]  # students whose seeded papers are not approved yet (retake demo)
            header = f"Name: {NAMES[sid]}    ID: {sid}" if k != 3 else "Name:            ID:"  # every 4th paper has no name
            img, _ = render_paper(header, blocks, seed=100 + n, line_font=44 if spec["subject"] == "grammar" else 50)
            (OUT / f"{name}.jpg").write_bytes(img)
            gt = {"activity_id": spec["id"], "writer": "font:Caveat", "style": "synthetic", "synthetic": True,
                  "student_name": NAMES[sid] if k != 3 else None, "student_id": sid if k != 3 else None, "problems": gt_problems}
            (OUT / f"{name}.json").write_text(json.dumps(gt, indent=2, ensure_ascii=False))
            n += 1
    print(f"Wrote {n} synthetic papers to {OUT} (smoke tests only, not for the evaluation report).")


if __name__ == "__main__":
    main()
