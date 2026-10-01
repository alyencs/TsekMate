"""Seed content: our own problems, rubrics, and planted error variants (no copyrighted material, no real students).

Each problem has a correct solution as a list of units (criterion, text) and named error variants. A variant overrides
units by index (0-based): verdict, error_type, points, text, comment. `cluster` links a variant to a named
misconception so the class summary can count it (the counting is done in code).
"""
from __future__ import annotations

RUBRIC_TEMPLATES = [
    {
        "id": "tpl-math-linear",
        "name": "Math: linear equations, 10 pts",
        "subject": "math",
        "criteria": [
            {"name": "Setup", "description": "Correctly expanding parentheses or organizing terms.", "points": 2},
            {"name": "Method", "description": "Correct algebraic operations performed on both sides.", "points": 3},
            {"name": "Computation", "description": "Arithmetic accuracy in additions, subtractions, etc.", "points": 3},
            {"name": "Final answer", "description": "The result is correct and clearly stated.", "points": 2},
        ],
    },
    {
        "id": "tpl-math-fractions",
        "name": "Math: fractions, 10 pts",
        "subject": "math",
        "criteria": [
            {"name": "Setup", "description": "Finds a common denominator or rewrites mixed numbers correctly.", "points": 2},
            {"name": "Method", "description": "Uses the correct operation on numerators and denominators.", "points": 3},
            {"name": "Computation", "description": "Arithmetic accuracy.", "points": 3},
            {"name": "Final answer", "description": "Answer is correct and in simplest form.", "points": 2},
        ],
    },
    {
        "id": "tpl-science-calc",
        "name": "Science calculation, 10 pts",
        "subject": "science",
        "criteria": [
            {"name": "Formula", "description": "Stating the correct physics formula (e.g., v = d/t).", "points": 2},
            {"name": "Substitution", "description": "Plugging in the given values correctly into the formula.", "points": 2},
            {"name": "Computation", "description": "Accurate arithmetic processing of the values.", "points": 3},
            {"name": "Answer with units", "description": "Final value is correct and includes proper units (m/s).", "points": 3},
        ],
    },
    {
        "id": "tpl-grammar-correction",
        "name": "Grammar correction, 10 pts",
        "subject": "grammar",
        "criteria": [
            {"name": "Finds the errors", "description": "Correctly identifying all grammar/spelling mistakes in the text.", "points": 3},
            {"name": "Correct revision", "description": "Providing the accurately corrected version of the text.", "points": 4},
            {"name": "Rule explanation", "description": "Providing a brief, accurate explanation of the grammar rule.", "points": 2},
            {"name": "Spelling and punctuation", "description": "No new errors introduced in the revision.", "points": 1},
        ],
    },
]


def _crit(tpl_id: str) -> list[dict]:
    return next(t for t in RUBRIC_TEMPLATES if t["id"] == tpl_id)["criteria"]


# ---------------------------------------------------------------- MATH: Solving Linear Equations: Quiz 1
MATH = {
    "key": "math",
    "id": "act-linear-eq-quiz1",
    "title": "Solving Linear Equations: Quiz 1",
    "subject": "math",
    "class_name": "Grade 8 Rizal",
    "date": "2024-05-28",
    "settings": {"accept_alternate": True, "require_units": False, "feedback_style": "hint_only"},
    "rubric": _crit("tpl-math-linear"),
    "problems": [
        {
            "text": "Simplify the expression, then solve for x: 4x + 2x - 5 = 13",
            "expected_answer": "x = 3",
            "sample_solution": "6x - 5 = 13, 6x = 18, x = 3",
            "units": [("Setup", "6x - 5 = 13"), ("Method", "6x = 13 + 5"), ("Computation", "6x = 18"), ("Final answer", "x = 3")],
            "hint": "Look at the line where -5 moves to the other side. What happens to its sign?",
            "variants": {
                "sub": {
                    "cluster": "math-sub",
                    "units": {
                        1: {"text": "6x = 13 - 5", "verdict": "error", "error_type": "computational", "points": 1, "comment": "-5 was moved across without changing its sign; it should become +5."},
                        2: {"text": "6x = 8", "points": 1, "comment": "Divides correctly from the previous line, but the value carries the earlier error."},
                        3: {"text": "x = 4/3", "verdict": "error", "points": 0, "comment": "Incorrect result."},
                    },
                },
                "pres": {
                    "units": {3: {"text": "3", "verdict": "error", "error_type": "presentation", "points": 1, "comment": "The final answer is not stated as x = 3."}},
                    "hint": "Your value is right. How should the final answer be written?",
                },
            },
        },
        {
            "text": "Solve for x: 3(x - 4) = 2x + 5",
            "expected_answer": "x = 17",
            "sample_solution": "3x - 12 = 2x + 5, then x = 17",
            "units": [("Setup", "3(x - 4) = 2x + 5"), ("Method", "3x - 12 = 2x + 5"), ("Computation", "x = 5 + 12 = 17"), ("Final answer", "Final answer: x = 17")],
            "hint": "Check the second line. Did you multiply 3 by both x and -4?",
            "variants": {
                "dist": {
                    "cluster": "math-dist",
                    "units": {
                        0: {"comment": "Correctly identified the starting equation."},
                        1: {"text": "3x - 4 = 2x + 5", "verdict": "error", "error_type": "conceptual", "points": 1, "comment": "3 was multiplied by x but not by -4."},
                        2: {"text": "x = 9", "points": 2, "comment": "Solves the line before it, but carries the earlier error."},
                        3: {"text": "Final answer: x = 9", "verdict": "error", "points": 0, "comment": "Incorrect result."},
                    },
                },
                "nota": {
                    "units": {3: {"text": "Final answer: x - 17", "verdict": "error", "error_type": "notation", "points": 1, "comment": "The equals sign is written as a minus sign."}},
                    "hint": "Look at the symbol between x and 17 in your final answer.",
                },
            },
        },
        {
            "text": "Find the value of y when 5y - 3 = 2y + 12",
            "expected_answer": "y = 5",
            "sample_solution": "3y - 3 = 12, 3y = 15, y = 5",
            "units": [("Setup", "5y - 2y - 3 = 12"), ("Method", "3y = 12 + 3"), ("Computation", "3y = 15"), ("Final answer", "y = 5")],
            "hint": "Add 12 + 3 again on the third line.",
            "variants": {
                "comp": {
                    "units": {
                        2: {"text": "3y = 18", "verdict": "error", "error_type": "computational", "points": 1, "comment": "12 + 3 was added as 18."},
                        3: {"text": "y = 6", "verdict": "error", "points": 0, "comment": "Incorrect result."},
                    },
                },
            },
        },
        {
            "text": "Solve for x: 4x - 9 = x + 6",
            "expected_answer": "x = 5",
            "sample_solution": "3x - 9 = 6, 3x = 15, x = 5",
            "units": [("Setup", "4x - x - 9 = 6"), ("Method", "3x = 6 + 9"), ("Computation", "3x = 15"), ("Final answer", "x = 5")],
            "hint": "When -9 moves to the right side, what should its sign be?",
            "variants": {
                "sub": {
                    "cluster": "math-sub",
                    "units": {
                        1: {"text": "3x = 6 - 9", "verdict": "error", "error_type": "computational", "points": 1, "comment": "-9 was moved across without changing its sign; it should become +9."},
                        2: {"text": "3x = -3", "points": 2, "comment": "Follows from the line before it."},
                        3: {"text": "x = -1", "verdict": "error", "points": 0, "comment": "Incorrect result."},
                    },
                },
                "nota": {
                    "units": {
                        2: {"text": "3x = 15", "comment": "Correct computation."},
                        3: {"text": "x 5", "verdict": "error", "error_type": "notation", "points": 1, "comment": "The equals sign is missing in the final answer."},
                    },
                    "hint": "Your value is right. What symbol is missing in the last line?",
                },
            },
        },
        {
            "text": "Solve for x: 2(x + 3) - 4 = 3x - 1",
            "expected_answer": "x = 3",
            "sample_solution": "2x + 6 - 4 = 3x - 1, 2x + 2 = 3x - 1, x = 3",
            "units": [("Setup", "2x + 6 - 4 = 3x - 1"), ("Method", "2x + 2 = 3x - 1"), ("Computation", "2 + 1 = 3x - 2x"), ("Final answer", "x = 3")],
            "hint": "Check the first line. Was every term inside the parentheses multiplied by 2?",
            "variants": {
                "dist": {
                    "cluster": "math-dist",
                    "units": {
                        0: {"text": "2x + 3 - 4 = 3x - 1", "verdict": "error", "error_type": "conceptual", "points": 0, "comment": "2 was multiplied by x but not by 3."},
                        1: {"text": "2x - 1 = 3x - 1", "points": 2, "comment": "Combines terms from the line before it."},
                        2: {"text": "0 = 3x - 2x", "points": 2, "comment": "Follows from the line before it."},
                        3: {"text": "x = 0", "verdict": "error", "points": 0, "comment": "Incorrect result."},
                    },
                },
                "pres": {
                    "units": {2: {"text": "3 = x", "comment": "Correct computation."}, 3: {"text": "(answer above)", "verdict": "error", "error_type": "presentation", "points": 1, "comment": "The final answer is not written as its own line."}},
                    "hint": "Your value is right. Write the final answer clearly on its own line.",
                },
            },
        },
    ],
    "clusters": {
        "math-dist": {"label": "did not multiply every term inside the parentheses", "error_type": "conceptual"},
        "math-sub": {"label": "made subtraction errors when moving terms", "error_type": "computational"},
    },
    "reteach_focus": "Recommend a 10-minute review of the distributive property with 2 practice problems focused on expanding parentheses.",
}

# ---------------------------------------------------------------- SCIENCE: Forces and Motion: Quiz 2
SCIENCE = {
    "key": "science",
    "id": "act-forces-motion-quiz2",
    "title": "Forces and Motion: Quiz 2",
    "subject": "science",
    "class_name": "Grade 8 Rizal",
    "date": "2024-05-27",
    "settings": {"accept_alternate": True, "require_units": True, "feedback_style": "full_solution"},
    "rubric": _crit("tpl-science-calc"),
    "problems": [
        {
            "text": "A car travels 240 m in 12 s. Find its average speed.",
            "expected_answer": "20 m/s",
            "sample_solution": "v = d / t, v = 240 / 12, v = 20 m/s",
            "units": [("Formula", "v = d / t"), ("Substitution", "v = 240 / 12"), ("Computation", "= 20"), ("Answer with units", "v = 20 m/s")],
            "hint": "Check the formula. Speed is distance divided by time.",
            "variants": {
                "inv": {
                    "cluster": "sci-inv",
                    "units": {
                        0: {"text": "v = t / d", "verdict": "error", "error_type": "conceptual", "points": 0, "comment": "Time was divided by distance; speed is distance divided by time."},
                        1: {"text": "v = 12 / 240", "points": 1, "comment": "Values substituted into the reversed formula."},
                        2: {"text": "= 0.05", "comment": "Arithmetic is correct for the line before it."},
                        3: {"text": "v = 0.05 m/s", "verdict": "error", "points": 0, "comment": "Incorrect value."},
                    },
                },
                "comp": {
                    "units": {2: {"text": "= 2", "verdict": "error", "error_type": "computational", "points": 1, "comment": "240 / 12 is 20, not 2."}, 3: {"text": "v = 2 m/s", "verdict": "error", "points": 1, "comment": "Value carries the computation error; units are correct."}},
                },
            },
        },
        {
            "text": "A cart is pushed with a net force of 12 N and accelerates at 3 m/s². Find its mass.",
            "expected_answer": "4 kg",
            "sample_solution": "m = F / a, m = 12 / 3, m = 4 kg",
            "units": [("Formula", "m = F / a"), ("Substitution", "m = 12 / 3"), ("Computation", "= 4"), ("Answer with units", "m = 4 kg")],
            "hint": "What unit is mass measured in?",
            "variants": {
                "units": {
                    "cluster": "sci-units",
                    "units": {3: {"text": "m = 4", "verdict": "error", "error_type": "units_and_notation", "points": 1, "comment": "The answer needs a unit (kg)."}},
                },
                "comp": {
                    "units": {2: {"text": "= 3", "verdict": "error", "error_type": "computational", "points": 1, "comment": "12 / 3 is 4, not 3."}, 3: {"text": "m = 3 kg", "verdict": "error", "points": 1, "comment": "Value carries the computation error; unit is correct."}},
                },
            },
        },
        {
            "text": "A cyclist travels 150 m in 30 s. Find her average speed.",
            "expected_answer": "5 m/s",
            "sample_solution": "speed = distance / time, speed = 150 / 30, speed = 5 m/s",
            "units": [("Formula", "v = d / t"), ("Substitution", "v = 150 / 30"), ("Computation", "= 5"), ("Answer with units", "Answer: 5 m/s")],
            "hint": "Check the unit of your answer. What does m/s tell us?",
            "variants": {
                "units": {
                    "cluster": "sci-units",
                    "units": {
                        0: {"comment": "Correct physics formula identified."},
                        1: {"comment": "Values substituted correctly into formula."},
                        3: {"text": "Answer: 5 m", "verdict": "error", "error_type": "units_and_notation", "points": 1, "comment": "Speed is measured in m/s, not m."},
                    },
                },
                "inv": {
                    "cluster": "sci-inv",
                    "units": {
                        0: {"text": "v = t / d", "verdict": "error", "error_type": "conceptual", "points": 0, "comment": "Time was divided by distance; speed is distance divided by time."},
                        1: {"text": "v = 30 / 150", "points": 1, "comment": "Values substituted into the reversed formula."},
                        2: {"text": "= 0.2", "comment": "Arithmetic is correct for the line before it."},
                        3: {"text": "Answer: 0.2 m/s", "verdict": "error", "points": 0, "comment": "Incorrect value."},
                    },
                },
                "comp": {"units": {2: {"text": "= 50", "verdict": "error", "error_type": "computational", "points": 1, "comment": "150 / 30 is 5, not 50."}, 3: {"text": "Answer: 50 m/s", "verdict": "error", "points": 1, "comment": "Value carries the computation error."}}},
            },
        },
        {
            "text": "A box with a mass of 5 kg accelerates at 2 m/s². Find the net force on it.",
            "expected_answer": "10 N",
            "sample_solution": "F = m × a, F = 5 × 2, F = 10 N",
            "units": [("Formula", "F = m × a"), ("Substitution", "F = 5 × 2"), ("Computation", "= 10"), ("Answer with units", "F = 10 N")],
            "hint": "Force is measured in newtons. Check your unit.",
            "variants": {
                "units": {"cluster": "sci-units", "units": {3: {"text": "F = 10 kg", "verdict": "error", "error_type": "units_and_notation", "points": 1, "comment": "Force is measured in newtons (N), not kg."}}},
                "pres": {"units": {3: {"text": "10", "verdict": "error", "error_type": "presentation", "points": 2, "comment": "The answer is not labeled as F = 10 N."}}},
                "comp": {"units": {2: {"text": "= 7", "verdict": "error", "error_type": "computational", "points": 1, "comment": "5 × 2 was added instead of multiplied."}, 3: {"text": "F = 7 N", "verdict": "error", "points": 1, "comment": "Value carries the computation error."}}},
            },
        },
    ],
    "clusters": {
        "sci-units": {"label": "left out units or wrote m instead of m/s", "error_type": "units_and_notation"},
        "sci-inv": {"label": "divided time by distance", "error_type": "conceptual"},
    },
    "reteach_focus": "A 10-minute review of speed units with 2 practice problems focused on identifying correct units for distance, time, and speed.",
}

# ---------------------------------------------------------------- GRAMMAR: Subject-Verb Agreement: Worksheet 3
# Grammar units: one "Finds the errors" unit per error in the sentence (3 pts split across them), one "Correct revision"
# unit for the student's rewritten sentence, one "Rule explanation" unit, one "Spelling and punctuation" unit.
GRAMMAR = {
    "key": "grammar",
    "id": "act-sva-worksheet3",
    "title": "Subject-Verb Agreement: Worksheet 3",
    "subject": "grammar",
    "class_name": "Grade 8 Rizal",
    "date": "2024-05-27",
    "settings": {"accept_alternate": True, "require_units": False, "feedback_style": "hint_only"},
    "rubric": _crit("tpl-grammar-correction"),
    "problems": [
        {
            "text": "Each of the students have a notebook.",
            "expected_answer": "Each of the students has a notebook.",
            "rule": "Indefinite pronouns like 'each' are singular",
            "corrections": [('"have" to "has"', "have")],
            "revision": "Each of the students has a notebook.",
            "explanation": '"Each" is singular, so the verb is "has."',
            "hint": "Who is the subject: 'each' or 'students'?",
            "variants": {
                "miss": {"cluster": "gr-nearest", "units": {0: {"text": '"have" not changed', "verdict": "error", "error_type": "grammar_rule", "points": 0, "comment": "The subject is 'each', which is singular, so the verb should be 'has'."}}, "revision": "Each of the students have a notebook.", "rev_points": 2},
                "punct": {"units": {"spell": {"text": "each of the students has a notebook", "verdict": "error", "error_type": "punctuation_capitalization", "points": 0, "comment": "The revision is missing the capital letter and the period."}}, "revision": "each of the students has a notebook"},
            },
        },
        {
            "text": "My sister walk to school every day.",
            "expected_answer": "My sister walks to school every day.",
            "rule": "A singular subject takes a verb ending in -s",
            "corrections": [('"walk" to "walks"', "walk")],
            "revision": "My sister walks to school every day.",
            "explanation": '"Sister" is one person, so the verb needs -s.',
            "hint": "How many people is 'my sister'? What ending does the verb need?",
            "variants": {
                "miss_s": {"cluster": "gr-s", "units": {0: {"text": '"walk" not changed', "verdict": "error", "error_type": "grammar_rule", "points": 0, "comment": "'Sister' is singular, so the verb needs -s: walks."}}, "revision": "My sister walk to school every day.", "rev_points": 2},
                "spell": {"units": {"spell": {"text": "My sistar walks to school every day.", "verdict": "error", "error_type": "spelling", "points": 0, "comment": "'Sister' is misspelled in the revision."}}, "revision": "My sistar walks to school every day."},
                "word": {"units": {"rev": {"text": "My sister goes to school every day.", "verdict": "error", "error_type": "word_choice", "points": 3, "comment": "The verb was replaced with a different word instead of being corrected."}}, "revision": "My sister goes to school every day."},
            },
        },
        {
            "text": "The dogs in the yard barks loudly.",
            "expected_answer": "The dogs in the yard bark loudly.",
            "rule": "A plural subject takes a plural verb, even with a phrase in between",
            "corrections": [('"barks" to "bark"', "barks")],
            "revision": "The dogs in the yard bark loudly.",
            "explanation": "The subject is \"dogs,\" which is plural.",
            "hint": "Find the subject first. Is it 'dogs' or 'yard'?",
            "variants": {
                "punct": {"units": {"spell": {"text": "the dogs in the yard bark loudly", "verdict": "error", "error_type": "punctuation_capitalization", "points": 0, "comment": "The revision is missing the capital letter and the period."}}, "revision": "the dogs in the yard bark loudly"},
                "spell": {"units": {"spell": {"text": "The dogs in the yard bark loudley.", "verdict": "error", "error_type": "spelling", "points": 0, "comment": "'Loudly' is misspelled in the revision."}}, "revision": "The dogs in the yard bark loudley."},
            },
        },
        {
            "text": "The team of players are practicing, and their coach say they is ready.",
            "expected_answer": "The team of players is practicing, and their coach says they are ready.",
            "rule": "Subject-verb agreement (collective noun & singular subjects)",
            "corrections": [('"are" to "is"', "are"), ('"say" to "says"', "say"), ('"is" to "are"', "is")],
            "revision": "The team of players is practicing, and their coach says they are ready.",
            "explanation": '"The subject is team, not players."',
            "hint": "Read the sentence again. Who does 'say' belong to?",
            "variants": {
                "nearest": {"cluster": "gr-nearest", "units": {0: {"text": '"are" not changed', "verdict": "error", "error_type": "grammar_rule", "points": 0, "comment": "The verb was matched to 'players'; the subject is 'team', so it should be 'is'."}}, "revision": "The team of players are practicing, and their coach says they are ready.", "rev_points": 3},
                "miss_s": {
                    "cluster": "gr-s",
                    "units": {1: {"text": '"say" not changed', "verdict": "error", "error_type": "grammar_rule", "points": 0, "comment": "The coach is one person, so the verb needs -s: says."}},
                    "revision": "The team of players is practicing, and their coach say they are ready.",
                    "rev_points": 3,
                },
                "punct": {"units": {"spell": {"text": "The team of players is practicing and their coach says they are ready", "verdict": "error", "error_type": "punctuation_capitalization", "points": 0, "comment": "The comma and the period are missing in the revision."}}, "revision": "The team of players is practicing and their coach says they are ready"},
            },
        },
        {
            "text": "Neither the teacher nor the students was late.",
            "expected_answer": "Neither the teacher nor the students were late.",
            "rule": "With neither/nor, the verb agrees with the nearer subject",
            "corrections": [('"was" to "were"', "was")],
            "revision": "Neither the teacher nor the students were late.",
            "explanation": 'The verb agrees with "students," the nearer subject.',
            "hint": "With 'neither ... nor', which subject is closer to the verb?",
            "variants": {
                "word": {"units": {"rev": {"text": "Neither the teacher nor the pupils were late.", "verdict": "error", "error_type": "word_choice", "points": 3, "comment": "A word was changed that did not need changing."}}, "revision": "Neither the teacher nor the pupils were late."},
                "punct": {"units": {"spell": {"text": "neither the teacher nor the students were late", "verdict": "error", "error_type": "punctuation_capitalization", "points": 0, "comment": "The revision is missing the capital letter and the period."}}, "revision": "neither the teacher nor the students were late"},
                "rule": {"units": {"rule": {"text": '"Students is plural."', "verdict": "error", "error_type": "grammar_rule", "points": 1, "comment": "The explanation does not mention the neither/nor rule."}}},
            },
        },
    ],
    "clusters": {
        "gr-nearest": {"label": "matched the verb to the nearest noun (players) instead of the subject (team)", "error_type": "grammar_rule"},
        "gr-s": {"label": "missed the -s on singular verbs", "error_type": "grammar_rule"},
    },
    "reteach_focus": "A 10-minute lesson on finding the true subject in sentences with prepositional phrases, with 3 practice sentences.",
}

# ---------------------------------------------------------------- MATH: Fractions Review (Grade 7 Mabini, done)
FRACTIONS = {
    "key": "fractions",
    "id": "act-fractions-review",
    "title": "Fractions Review",
    "subject": "math",
    "class_name": "Grade 7 Mabini",
    "date": "2024-05-24",
    "settings": {"accept_alternate": True, "require_units": False, "feedback_style": "hint_only"},
    "rubric": _crit("tpl-math-fractions"),
    "problems": [
        {"text": "Add: 1/2 + 1/3", "expected_answer": "5/6", "sample_solution": "3/6 + 2/6 = 5/6", "units": [("Setup", "3/6 + 2/6"), ("Method", "(3 + 2)/6"), ("Computation", "= 5/6"), ("Final answer", "5/6")], "hint": "Find a common denominator first.",
         "variants": {"comp": {"units": {2: {"text": "= 6/6", "verdict": "error", "error_type": "computational", "points": 1, "comment": "3 + 2 was added as 6."}, 3: {"text": "1", "verdict": "error", "points": 0, "comment": "Incorrect result."}}}}},
        {"text": "Subtract: 3/4 - 1/8", "expected_answer": "5/8", "sample_solution": "6/8 - 1/8 = 5/8", "units": [("Setup", "6/8 - 1/8"), ("Method", "(6 - 1)/8"), ("Computation", "= 5/8"), ("Final answer", "5/8")], "hint": "Rewrite 3/4 with denominator 8.",
         "variants": {"conc": {"units": {0: {"text": "3/4 - 1/8 = 2/4", "verdict": "error", "error_type": "conceptual", "points": 0, "comment": "Numerators and denominators were subtracted separately."}, 3: {"text": "1/2", "verdict": "error", "points": 0, "comment": "Incorrect result."}}}}},
        {"text": "Multiply: 2/3 × 3/5", "expected_answer": "2/5", "sample_solution": "6/15 = 2/5", "units": [("Setup", "2/3 × 3/5"), ("Method", "(2 × 3)/(3 × 5)"), ("Computation", "= 6/15"), ("Final answer", "2/5")], "hint": "Simplify your answer.",
         "variants": {"pres": {"units": {3: {"text": "6/15", "verdict": "error", "error_type": "presentation", "points": 1, "comment": "The answer is not in simplest form."}}}}},
        {"text": "Divide: 3/4 ÷ 1/2", "expected_answer": "3/2", "sample_solution": "3/4 × 2/1 = 6/4 = 3/2", "units": [("Setup", "3/4 × 2/1"), ("Method", "multiply by the reciprocal"), ("Computation", "= 6/4"), ("Final answer", "3/2")], "hint": "Dividing by a fraction means multiplying by its reciprocal.",
         "variants": {"conc": {"units": {0: {"text": "3/4 × 1/2", "verdict": "error", "error_type": "conceptual", "points": 0, "comment": "The second fraction was not flipped."}, 2: {"text": "= 3/8", "points": 2}, 3: {"text": "3/8", "verdict": "error", "points": 0, "comment": "Incorrect result."}}}}},
        {"text": "Write 2 1/4 as an improper fraction.", "expected_answer": "9/4", "sample_solution": "(2 × 4 + 1)/4 = 9/4", "units": [("Setup", "2 × 4 + 1"), ("Method", "(8 + 1)/4"), ("Computation", "= 9/4"), ("Final answer", "9/4")], "hint": "Multiply the whole number by the denominator, then add the numerator.",
         "variants": {"comp": {"units": {2: {"text": "= 10/4", "verdict": "error", "error_type": "computational", "points": 1, "comment": "8 + 1 was added as 10."}, 3: {"text": "10/4", "verdict": "error", "points": 0, "comment": "Incorrect result."}}}}},
    ],
    "clusters": {},
    "reteach_focus": "A short review of finding common denominators before adding or subtracting.",
}

ACTIVITIES = [MATH, SCIENCE, GRAMMAR, FRACTIONS]
