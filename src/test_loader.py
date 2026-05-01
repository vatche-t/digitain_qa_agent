"""
Test case loader.

Reads the Digitain assignment Excel directly so the test suite stays in sync
with what the QA team writes. No hardcoded test data — change the Excel,
re-run the agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

Difficulty = Literal["simple", "complex"]


@dataclass
class TestCase:
    """One test case as understood by the agent."""

    id: str                       # e.g. "simple-1", "complex-3"
    difficulty: Difficulty
    section: str                  # "Login fields", "Self-exclusion", etc.
    description: str              # What we're testing
    steps: str                    # Reproduction steps (free text from QA)
    expected: str                 # Expected outcome
    tags: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Render this test case as instructions for the LLM agent."""
        return (
            f"TEST CASE {self.id} — {self.section}\n"
            f"Description: {self.description}\n"
            f"Steps:\n{self.steps}\n"
            f"Expected result: {self.expected}\n"
        )


# Sheet names in the assignment Excel (Armenian).
# We match by position to be robust against renames.
SIMPLE_SHEET_KEYWORDS = ["Պարզ", "simple", "easy"]
COMPLEX_SHEET_KEYWORDS = ["Բարդ", "complex", "hard"]


def _classify_sheet(name: str) -> Difficulty | None:
    lowered = name.lower()
    if any(k.lower() in lowered for k in SIMPLE_SHEET_KEYWORDS):
        return "simple"
    if any(k.lower() in lowered for k in COMPLEX_SHEET_KEYWORDS):
        return "complex"
    return None


def _infer_tags(section: str, description: str) -> list[str]:
    """Auto-tag tests for filtering. Useful for CI: --tag responsible-gambling."""
    text = f"{section} {description}".lower()
    tags = []
    if any(k in text for k in ["self-exclusion", "ինքնաբացառ", "exclus"]):
        tags.append("responsible-gambling")
    if "time" in text and "out" in text or "դադար" in text:
        tags.append("responsible-gambling")
    if any(k in text for k in ["login", "մուտք"]):
        tags.append("auth")
    if "cnp" in text:
        tags.append("registration")
        tags.append("compliance")
    if any(k in text for k in ["bet", "խաղադրույք"]):
        tags.append("betting")
    if any(k in text for k in ["casino", "կազինո"]):
        tags.append("casino")
    if any(k in text for k in ["virtual", "վիրտուալ"]):
        tags.append("virtual-sports")
    if any(k in text for k in ["banner", "բաններ"]):
        tags.append("ui")
    return tags


def _normalize_case_num(value) -> str:
    """Keep Excel numeric IDs stable: 1.0 -> 1, 10 -> 10."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def load_test_cases(xlsx_path: str | Path) -> list[TestCase]:
    """Load every test case from the assignment workbook."""
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Test case file not found: {xlsx_path}")

    sheets = pd.read_excel(xlsx_path, sheet_name=None)
    cases: list[TestCase] = []

    for sheet_name, df in sheets.items():
        difficulty = _classify_sheet(sheet_name)
        if difficulty is None:
            continue

        # Standardize columns by position; the Armenian headers vary.
        # Expected layout: [#, Section, Description, Steps, Expected]
        if df.shape[1] < 5:
            continue

        df = df.copy()
        df.columns = ["num", "section", "description", "steps", "expected"][: df.shape[1]] + list(
            df.columns[5:]
        )
        df = df.dropna(subset=["section", "description"])

        for _, row in df.iterrows():
            num = _normalize_case_num(row["num"])
            section = str(row["section"]).strip()
            description = str(row["description"]).strip()
            steps = str(row["steps"]).strip()
            expected = str(row["expected"]).strip()

            cases.append(
                TestCase(
                    id=f"{difficulty}-{num}",
                    difficulty=difficulty,
                    section=section,
                    description=description,
                    steps=steps,
                    expected=expected,
                    tags=_infer_tags(section, description),
                )
            )

    return cases


def filter_cases(
    cases: list[TestCase],
    *,
    difficulty: Difficulty | None = None,
    tag: str | None = None,
    ids: list[str] | None = None,
) -> list[TestCase]:
    """Filter by difficulty / tag / id list. Used by the CLI."""
    out = cases
    if difficulty:
        out = [c for c in out if c.difficulty == difficulty]
    if tag:
        out = [c for c in out if tag in c.tags]
    if ids:
        out = [c for c in out if c.id in ids]
    return out
