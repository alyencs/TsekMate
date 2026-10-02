"""Grade one photo from the command line (one vision call, validated JSON, routing computed in code).

    python scripts/grade.py samples/math/paper01.jpg --activity act-linear-eq-quiz1

Prints the cleaned result as JSON. Activity ids for the seeded demo: act-linear-eq-quiz1, act-forces-motion-quiz2,
act-sva-worksheet3, act-fractions-review.
"""
import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path

import _path  # noqa: F401
from app.grading import grader, llm
from app.seed import build
from app.services.core import Bundle
from app.store import get_store


def load_activity(activity_id: str):
    store = get_store()
    if store.kind == "memory" and not store.select("activities"):
        build(store, with_images=False)
    b = Bundle(store, activity_id)
    return b.activity, b.problems, b.rubric


def grade_file(path: Path, activity_id: str) -> dict:
    activity, problems, rubric = load_activity(activity_id)
    media = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return grader.grade_image(path.read_bytes(), media, activity, problems, rubric)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--activity", required=True)
    ap.add_argument("--raw", action="store_true", help="also print the raw model JSON")
    a = ap.parse_args()
    if not a.image.exists():
        sys.exit(f"File not found: {a.image}")
    t = time.time()
    try:
        res = grade_file(a.image, a.activity)
    except (llm.LLMUnavailable, llm.LLMError) as e:
        sys.exit(f"{e} ({e.detail})")  # command line: show the technical reason too
    raw = res.pop("raw_json")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if a.raw:
        print(json.dumps(raw, indent=2, ensure_ascii=False))
    print(f"\nstatus={res['status']} score={res['suggested_score']}/{res['max_score']} confidence={res['overall_confidence']:.2f} "
          f"flags={res['flags']} model={res['model']} prompt={res['prompt_version']} ({time.time() - t:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
