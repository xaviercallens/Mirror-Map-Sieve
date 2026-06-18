# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Mind Olympiad package — PIMS Adler Problem Collection challenge loop.

Patent: US-PAT-PEND-2026-0525
"""

from olympiad.adler_problem_bank import (
    ADLER_PROBLEMS_ALL,
    get_problems_by_chapter,
    get_problems_by_difficulty,
    get_problems_by_type,
    OlympiadProblemRecord,
)

__all__ = [
    "ADLER_PROBLEMS_ALL",
    "get_problems_by_chapter",
    "get_problems_by_difficulty",
    "get_problems_by_type",
    "OlympiadProblemRecord",
]
