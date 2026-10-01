"""Pydantic models: API inputs and the AI output schema (document Section 6.4)."""
from __future__ import annotations

from datetime import date as _date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class In(BaseModel):
    """Base for request bodies: NaN and +/-Infinity are rejected (422) before any value reaches the store."""

    model_config = ConfigDict(allow_inf_nan=False)


class Criterion(In):
    # Lenient on purpose: scoring.rubric_problems() gives the teacher a readable reason instead of a 422.
    name: str = ""
    description: str = ""
    points: float = 0


class ActivitySettings(In):
    accept_alternate: bool = True
    require_units: bool = False
    feedback_style: Literal["hint_only", "full_solution"] = "hint_only"


class ProblemIn(In):
    order: int
    text: str = Field(min_length=1, max_length=4000)
    expected_answer: str = Field(min_length=1, max_length=2000)
    sample_solution: str = Field(default="", max_length=8000)
    rule: str = Field(default="", max_length=1000)


class ActivityIn(In):
    title: str = Field(min_length=1, max_length=200)
    subject: Subject
    class_name: str = Field(min_length=1, max_length=120)
    date: str
    settings: ActivitySettings = ActivitySettings()
    problems: list[ProblemIn] = Field(min_length=1)
    rubric: list[Criterion] = []
    rubric_total: float | None = None  # points per problem; must equal the sum of the criteria

    @field_validator("date")
    @classmethod
    def _iso_date(cls, v: str) -> str:
        try:
            return _date.fromisoformat(v.strip()).isoformat()
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD") from None


class RubricUpdate(In):
    criteria: list[Criterion] = []
    total_points: float | None = None


# ---------- AI output schema ----------


class UnitOut(BaseModel):
    index: int
    transcribed_text: str
    alt_reading: str | None = None
    verdict: Verdict
    error_type: str | None = None
    criterion: str
    points_awarded: float
    points_max: float = 0  # not asked for since prompt v1.3; the rubric decides it (scoring.clean_problem)
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
    # Not asked for since prompt v1.3: the answer key and the scores come from the activity and are recomputed.
    expected_answer: str = ""
    units: list[UnitOut]
    suggested_score: float = 0
    max_score: float = 0
    overall_confidence: float = Field(ge=0, le=1)
    flags: list[FlagT] = []
    student_hint: str = ""


class PaperOut(BaseModel):
    # Student identity read from the paper. Lenient on purpose: identity problems never fail grading.
    student_name: str | None = None
    student_id: str | None = None
    identity_confidence: float = 0.0
    problems: list[ProblemOut]

    @field_validator("student_name", "student_id", mode="before")
    @classmethod
    def _identity_text(cls, v: object) -> str | None:
        if v is None or not isinstance(v, (str, int)):
            return None
        v = " ".join(str(v).split())[:120]
        return v if v and v.lower() not in {"null", "none", "unknown", "n/a", "not found"} else None

    @field_validator("identity_confidence", mode="before")
    @classmethod
    def _identity_conf(cls, v: object) -> float:
        try:
            return min(max(float(v), 0.0), 1.0)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    def identity(self) -> dict:
        conf = self.identity_confidence if (self.student_name or self.student_id) else 0.0
        return {"student_name": self.student_name, "student_id": self.student_id, "identity_confidence": round(conf, 2)}

    def check_against(self, subject: str, problem_ids: list[str], criteria: list[str]) -> None:
        """Extra validation that needs the activity context. Raises ValueError with a readable message."""
        allowed = set(ERROR_TYPES[subject])
        crit = {c.strip().lower() for c in criteria}
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
                if u.criterion.strip().lower() not in crit:
                    errs.append(f"{p.problem_id} unit {u.index}: criterion '{u.criterion}' not in rubric {criteria}")
        if errs:
            raise ValueError("; ".join(errs))


class UnitEdit(In):
    """A teacher's change to one AI unit. Omitted fields stay as they are; explicit null is only allowed for error_type.

    The fields are typed without None on purpose: `"points_awarded": null` or `"x"` is a 422, not a server error."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    points_awarded: float = Field(default=None, ge=0, le=1000)  # type: ignore[assignment]
    verdict: Verdict = None  # type: ignore[assignment]
    error_type: str | None = Field(default=None, max_length=60)
    transcribed_text: str = Field(default=None, max_length=4000)  # type: ignore[assignment]
    comment: str = Field(default=None, max_length=4000)  # type: ignore[assignment]


class ReviewPatch(In):
    unit_edits: dict[str, UnitEdit] | None = None
    # "problem_id::criterion name" -> points (None = use the AI's points). Range is checked against the rubric.
    criterion_scores: dict[str, float | None] | None = None
    feedback: dict[str, str] | None = None

    @field_validator("feedback")
    @classmethod
    def _feedback_len(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v and any(len(t) > 4000 for t in v.values()):
            raise ValueError("feedback is limited to 4000 characters per problem")
        return v

    @model_validator(mode="after")
    def _nonempty(self) -> "ReviewPatch":
        if self.unit_edits is None and self.criterion_scores is None and self.feedback is None:
            raise ValueError("Nothing to update")
        return self


class AssignStudent(In):
    student_id: str = Field(min_length=1)


class RubricProblem(In):
    text: str = ""
    expected_answer: str = ""
    rule: str = ""


class RubricRequest(In):
    subject: Subject
    title: str = ""
    problems: list[RubricProblem] = []
    learning_outcome: str = ""
    points_per_problem: float = Field(default=10, gt=0, le=100)


class ProfilePatch(In):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    department: str | None = Field(default=None, max_length=120)


class SettingsPatch(In):
    confidence_threshold: float | None = Field(default=None, ge=0.5, le=0.95)
    default_feedback_style: Literal["hint_only", "full_solution"] | None = None
    default_accept_alternate: bool | None = None
    default_rubric_mode: Literal["manual", "ai"] | None = None
    delete_images_on_approve: bool | None = None
    grading_mode: Literal["fast", "saver"] | None = None


class SignIn(In):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class ParentApprove(In):
    language: Literal["en", "fil"]
    text: str = Field(max_length=4000)


class AdapterGradesRequest(In):
    activity_id: str = Field(min_length=1, max_length=120)


class AdapterNotification(In):
    submission_id: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=10)
