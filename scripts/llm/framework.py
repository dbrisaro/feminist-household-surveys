"""Single entry point for the analytical framework.

The chain of custody is:

    framework/gender_survey_framework.html   <- source of truth, hand-edited
        -> parse_framework.py
    framework/framework.json                 <- generated, never hand-edited
        -> this module
    every consumer (run_eval, run_eval_gemini, triage_corpus, report, plots)

Nothing outside this module should name framework.json, so the path and the
shape of the file are stated in exactly one place. The prompt scaffold (role /
inputs / constraints / method) lives next door in prompts.py, which is likewise
the only place it is written down.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "framework" / "framework.json"


def load() -> dict:
    """The parsed framework: dimension, source_codes, subdimensions."""
    if not PATH.exists():
        raise SystemExit(
            f"{PATH.relative_to(ROOT)} is missing — regenerate it with:\n"
            "    python scripts/llm/parse_framework.py"
        )
    return json.loads(PATH.read_text(encoding="utf-8"))


def subdimensions(framework: dict | None = None) -> dict[str, dict]:
    """subdimension_id -> subdimension record."""
    fw = framework if framework is not None else load()
    return {s["subdimension_id"]: s for s in fw["subdimensions"]}


def source_codes(framework: dict | None = None) -> dict[str, str]:
    """Source code (C/M/G) -> human label."""
    fw = framework if framework is not None else load()
    return fw["source_codes"]


def codes_of(source_code: str) -> tuple[str, ...]:
    """The source codes an indicator reads, in declared order.

    Most indicators name one source (`C`); one that has to be judged across the
    instrument and its documentation names several joined by `+` (`C+M`). Every
    consumer splits through here so that the joined form is spelled once.
    """
    return tuple(c for c in source_code.split("+") if c)


def held_codes(indicator: dict, docs: dict) -> tuple[str, ...]:
    """The indicator's source codes for which the country holds a document.

    An indicator is asked when this is non-empty — a `C+M` indicator with only a
    questionnaire is still answerable from the questionnaire — and the call loads
    exactly these codes. Sorted, because corpus blocks are emitted in code order
    and the prompt cache keys on that order.
    """
    return tuple(sorted(c for c in codes_of(indicator["source_code"]) if docs.get(c)))
