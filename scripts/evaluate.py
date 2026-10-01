"""Run the grader on every sample with ground truth and write an honest report (markdown + JSON).

    python scripts/evaluate.py                 # real samples in samples/{math,science,grammar}
    python scripts/evaluate.py --write-cache   # also store results for DEMO_MODE
    python scripts/evaluate.py --include-synthetic   # smoke test only; labeled as such, never the reported result

Metrics (document Section 11):
- transcription accuracy per handwriting style (character similarity of AI lines vs ground truth lines)
- rubric-item agreement (AI points per criterion == ground truth points per criterion)
- catch rate per planted error type (AI marked an error or unclear on that criterion) and type match
- flag usefulness: disagreement rate for flagged vs unflagged rubric items
"""
import argparse
import difflib
import json
import mimetypes
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import _path  # noqa: F401
from _path import ROOT

SUBJECT_DIRS = ["math", "science", "grammar"]


def norm(s: str) -> str:
    return " ".join(s.replace("×", "x").replace("−", "-").lower().split())


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def collect(include_synthetic: bool) -> list[tuple[Path, dict]]:
    items = []
    dirs = SUBJECT_DIRS + (["synthetic"] if include_synthetic else [])
    for d in dirs:
        for gt_path in sorted((ROOT / "samples" / d).glob("*.json")):
            gt = json.loads(gt_path.read_text())
            img = next((gt_path.with_suffix(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".pdf") if gt_path.with_suffix(ext).exists()), None)
            if not img:
                print(f"skip {gt_path.name}: no image next to it")
                continue
            if gt.get("synthetic") and not include_synthetic:
                continue
            items.append((img, gt))
    return items


def evaluate(items, write_cache: bool) -> dict:
    from grade import grade_file

    if write_cache:
        os.environ["DEMO_MODE"] = "true"
        from app.config import get_settings

        get_settings.cache_clear()
    per_paper = []
    trans = defaultdict(list)
    crit_total = crit_agree = 0
    flagged = {"n": 0, "disagree": 0}
    unflagged = {"n": 0, "disagree": 0}
    catches = defaultdict(lambda: {"planted": 0, "caught": 0, "type_match": 0})
    abs_err = []
    failures = 0
    ident = {"papers": 0, "name_correct": 0, "id_correct": 0, "missing_handled": 0, "missing": 0}
    for img, gt in items:
        t = time.time()
        res = grade_file(img, gt["activity_id"])
        dt = time.time() - t
        if res["status"] == "failed":
            failures += 1
            per_paper.append({"file": img.name, "status": "failed", "error": str(res["raw_json"].get("error", ""))[:300]})
            continue
        by_pid = {p["problem_id"]: p for p in res["problem_results"]}
        if "student_name" in gt:  # identity reading is measured separately from grading
            got = res.get("identity") or {}
            from app.services.roster import norm_id, norm_name

            if gt["student_name"] or gt.get("student_id"):
                ident["papers"] += 1
                ident["name_correct"] += norm_name(got.get("student_name")) == norm_name(gt["student_name"])
                ident["id_correct"] += norm_id(got.get("student_id")) == norm_id(gt.get("student_id"))
            else:
                ident["missing"] += 1
                ident["missing_handled"] += not got.get("student_name") and not got.get("student_id")
        paper = {"file": img.name, "style": gt.get("style", "unknown"), "writer": gt.get("writer"), "status": res["status"], "seconds": round(dt, 1), "problems": []}
        for gp in gt["problems"]:
            ap = by_pid.get(gp["problem_id"])
            if not ap:
                continue
            ai_lines = [u["transcribed_text"] for u in ap["units"]]
            sim = similarity(" | ".join(gp["transcript"]), " | ".join(ai_lines))
            trans[gt.get("style", "unknown")].append(sim)
            gt_crit = defaultdict(float)
            for u in gp["units"]:
                gt_crit[u["criterion"].lower()] += float(u["points"])
            ai_crit = {c["name"].lower(): c["awarded"] for c in ap["criteria_scores"]}
            for c, pts in gt_crit.items():
                agree = abs(ai_crit.get(c, 0) - pts) < 0.01
                crit_total += 1
                crit_agree += agree
                units_c = [u for u in ap["units"] if u["criterion"].lower() == c]
                is_flagged = any(u["verdict"] == "unclear" or u["confidence"] < 0.75 for u in units_c)
                bucket = flagged if is_flagged else unflagged
                bucket["n"] += 1
                bucket["disagree"] += not agree
            abs_err.append(abs(sum(gt_crit.values()) - ap["suggested_score"]))
            for pe in gp.get("planted_errors", []):
                c = catches[pe["error_type"]]
                c["planted"] += 1
                hit = [u for u in ap["units"] if u["criterion"].lower() == pe["criterion"].lower() and u["verdict"] in ("error", "unclear")]
                if hit:
                    c["caught"] += 1
                    c["type_match"] += any(u.get("error_type") == pe["error_type"] for u in hit)
            paper["problems"].append({"problem_id": gp["problem_id"], "transcription_similarity": round(sim, 3), "ai_score": ap["suggested_score"], "gt_score": sum(gt_crit.values())})
        per_paper.append(paper)

    def rate(a, b):
        return round(a / b, 3) if b else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "papers": len(items),
        "grading_failures": failures,
        "transcription_by_style": {k: {"n_problems": len(v), "mean_similarity": rate(sum(v), len(v))} for k, v in sorted(trans.items())},
        "rubric_item_agreement": {"items": crit_total, "agree": crit_agree, "rate": rate(crit_agree, crit_total)},
        "problem_score_mae": rate(sum(abs_err), len(abs_err)),
        "catch_rate_by_error_type": {k: {**v, "catch_rate": rate(v["caught"], v["planted"]), "type_match_rate": rate(v["type_match"], v["planted"])} for k, v in sorted(catches.items())},
        "flag_usefulness": {
            "flagged_items": flagged["n"],
            "flagged_disagreement_rate": rate(flagged["disagree"], flagged["n"]),
            "unflagged_items": unflagged["n"],
            "unflagged_disagreement_rate": rate(unflagged["disagree"], unflagged["n"]),
        },
        "identity": {**ident, "name_accuracy": rate(ident["name_correct"], ident["papers"]), "id_accuracy": rate(ident["id_correct"], ident["papers"])},
        "per_paper": per_paper,
    }


def markdown(r: dict, smoke: bool, model: str) -> str:
    def f(x):
        return "n/a" if x is None else f"{x * 100:.0f}%"

    lines = [
        "# TsekMate evaluation report" + (" (SMOKE TEST, synthetic font images, not a real result)" if smoke else ""),
        "",
        f"Generated {r['generated_at']} with model `{model}`. Papers: **{r['papers']}**. Grading failures: {r['grading_failures']}.",
        "",
        f"> Small sample: {r['papers']} papers. These numbers are indicative only and should not be read as accuracy on real classrooms.",
        "",
        "## Transcription accuracy by handwriting style",
        "",
        "| Style | Problems | Mean character similarity |",
        "|---|---|---|",
    ]
    lines += [f"| {k} | {v['n_problems']} | {f(v['mean_similarity'])} |" for k, v in r["transcription_by_style"].items()]
    a = r["rubric_item_agreement"]
    lines += [
        "",
        "## Rubric-item agreement",
        "",
        f"AI points matched the ground truth on **{a['agree']} of {a['items']}** rubric items ({f(a['rate'])}). Mean absolute error per problem score: {r['problem_score_mae']} points.",
        "",
        "## Planted errors caught",
        "",
        "| Error type | Planted | Caught (error or unclear) | Catch rate | Correct type |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {k} | {v['planted']} | {v['caught']} | {f(v['catch_rate'])} | {f(v['type_match_rate'])} |" for k, v in r["catch_rate_by_error_type"].items()]
    fl = r["flag_usefulness"]
    lines += [
        "",
        "## Do low-confidence flags point at real mistakes?",
        "",
        f"- Flagged rubric items (unclear or confidence below 75%): {fl['flagged_items']}, AI disagreed with ground truth on {f(fl['flagged_disagreement_rate'])}.",
        f"- Unflagged rubric items: {fl['unflagged_items']}, AI disagreed with ground truth on {f(fl['unflagged_disagreement_rate'])}.",
        "",
        "Flags are useful if the flagged disagreement rate is clearly higher than the unflagged one.",
        "",
        "## Student identity (name and ID read from the paper)",
        "",
        f"- Papers with a name or ID: {r['identity']['papers']}. Name read correctly: {f(r['identity']['name_accuracy'])}. ID read correctly: {f(r['identity']['id_accuracy'])}.",
        f"- Papers without a name: {r['identity']['missing']}, reported as not identified: {r['identity']['missing_handled']}. Identity never changes the grade.",
        "",
        "## Limits",
        "",
        "- Very small sample from a few writers; per-style numbers rest on a handful of problems each.",
        "- Ground truth was written by our team; a second marker was not used.",
        "- Character similarity is a rough proxy for transcription accuracy (it ignores which errors matter).",
        "- Every grade still goes through teacher review; these numbers describe the draft, not the final grade.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-synthetic", action="store_true")
    ap.add_argument("--write-cache", action="store_true", help="store results in samples/cache for DEMO_MODE")
    a = ap.parse_args()
    items = collect(a.include_synthetic)
    if not items:
        raise SystemExit("No samples with ground truth found. See samples/README.md.")
    from app.config import get_settings

    if not get_settings().anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set; the evaluation needs live AI calls.")
    r = evaluate(items, a.write_cache)
    out = ROOT / "samples" / "eval"
    out.mkdir(exist_ok=True)
    stem = "smoke_test" if a.include_synthetic else "report"
    (out / f"{stem}.json").write_text(json.dumps(r, indent=2))
    (out / f"{stem}.md").write_text(markdown(r, a.include_synthetic, get_settings().anthropic_model))
    print((out / f"{stem}.md").read_text())


if __name__ == "__main__":
    main()
