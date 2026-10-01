FLAG_LABELS = {
    "unclear_handwriting": "Unclear handwriting",
    "step_mismatch": "Step mismatch",
    "alternate_method": "Alternate method",
    "low_confidence_final_answer": "Low confidence answer",
    "grading_failed": "Grading failed",
}

ERROR_LABELS = {
    "computational": "Computational",
    "conceptual": "Conceptual",
    "notation": "Notation",
    "presentation": "Presentation",
    "units_and_notation": "Units and notation",
    "grammar_rule": "Grammar rule",
    "spelling": "Spelling",
    "punctuation_capitalization": "Punctuation",
    "word_choice": "Word choice",
}


def error_label(key: str | None) -> str:
    return ERROR_LABELS.get(key or "", (key or "").replace("_", " ").capitalize())
