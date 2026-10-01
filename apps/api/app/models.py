"""Pydantic models: API inputs and the AI output schema (document Section 6.4)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Subject = Literal["math", "science", "grammar"]
Verdict = Literal["correct", "error", "unclear"]
FlagT = Literal[
    "unclear_handwriting",
    "step_mismatch",
    "alternate_method",
    "low_confidence_final_answer",
    "grading_failed",
]

ERROR_TYPES: dict[str, list[str]] = {
    "math": ["computational", "conceptual", "notation", "presentation"],
    "science": ["computational", "conceptual", "units_and_notation", "presentation"],
    "grammar": ["grammar_rule", "spelling", "punctuation_capitalization", "word_choice"],
}

UNIT_NOUN = {"math": "step", "science": "step", "grammar": "correction"}


class Criterion(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    points: float = Field(gt=0)


class ActivitySettings(BaseModel):
    accept_alternate: bool = True
    require_units: bool = False
    feedback_style: Literal["hint_only", "full_solution"] = "hint_only"


class ProblemIn(BaseModel):
    order: int
    text: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    sample_solution: str = ""
    rule: str = ""


class ActivityIn(BaseModel):
    title: str = Field(min_length=1)
    subject: Subject
    class_name: str = Field(min_length=1)
    date: str
    settings: ActivitySettings = ActivitySettings()
    problems: list[ProblemIn] = Field(min_length=1)
    rubric: list[Criterion] = Field(min_length=1)


# ---------- AI output schema ----------


class UnitOut(BaseModel):
    index: int
    transcribed_text: str
    alt_reading: str | None = None
    verdict: Verdict
    error_type: str | None = None
    criterion: str
    points_awarded: float
    points_max: float
    confidence: float = Field(ge=0, le=1)
    comment: str = ""
    bbox: list[float] | None = None

    @field_validator("bbox")
    @classmethod
    def _bbox(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return None
        if len(v) != 4 or any(x < 0 or x > 1 for x in v):
            return None  # best effort: drop malformed boxes instead of failing the paper
        return v


class ProblemOut(BaseModel):
    problem_id: str
    expected_answer: str
    units: list[UnitOut]
    suggested_score: float
    max_score: float
    overall_confidence: float = Field(ge=0, le=1)
    flags: list[FlagT] = []
    student_hint: str = ""


class PaperOut(BaseModel):
    problems: list[ProblemOut]

    def check_against(self, subject: str, problem_ids: list[str], criteria: list[str]) -> None:
        """Extra validation that needs the activity context. Raises ValueError with a readable message."""
        allowed = set(ERROR_TYPES[subject])
        crit = {c.lower() for c in criteria}
        seen = [p.problem_id for p in self.problems]
        missing = [pid for pid in problem_ids if pid not in seen]
        unknown = [pid for pid in seen if pid not in problem_ids]
        errs: list[str] = []
        if missing:
            errs.append(f"missing problem_id(s): {missing}")
        if unknown:
            errs.append(f"unknown problem_id(s): {unknown}")
        for p in self.problems:
            for u in p.units:
                if u.error_type is not None and u.error_type not in allowed:
                    errs.append(f"{p.problem_id} unit {u.index}: error_type '{u.error_type}' not in {sorted(allowed)}")
                if u.criterion.lower() not in crit:
                    errs.append(f"{p.problem_id} unit {u.index}: criterion '{u.criterion}' not in rubric {criteria}")
        if errs:
            raise ValueError("; ".join(errs))


class ReviewPatch(BaseModel):
    unit_edits: dict[str, dict] | None = None
    problem_scores: dict[str, float | None] | None = None
    feedback: dict[str, str] | None = None

    @model_validator(mode="after")
    def _nonempty(self) -> "ReviewPatch":
        if self.unit_edits is None and self.problem_scores is None and self.feedback is None:
            raise ValueError("Nothing to update")
        return self


class SignIn(BaseModel):
    email: str
    password: str
