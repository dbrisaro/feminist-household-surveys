"""Parse the analytical framework out of framework/gender_survey_framework.html.

The HTML is the single source of truth for everything the model is sent: the
subdimensions and indicators live in the `content` object inside its <script>
tag, and the prompt scaffold (role / inputs / constraints / method) lives in the
`scaffold` object beside it. This script converts both to framework.json so the
prompt pipeline never holds a second, drifting copy.

Re-run it whenever the HTML changes.

    python scripts/llm/parse_framework.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "framework" / "gender_survey_framework.html"
OUT = ROOT / "framework" / "framework.json"

# A single-quoted JS string, allowing backslash escapes (e.g. respondent\'s).
JS_STR = r"'((?:[^'\\]|\\.)*)'"

# Entries sit at two spaces of indentation and close on a line that is exactly
# `  }`; the indicator objects nested inside them close on their own line, so the
# indentation is what tells the two apart.
ENTRY = re.compile(r"^  (?P<key>\w+):\s*\{\n(?P<body>.*?)\n  \}", re.S | re.M)
# `indicators` is the last key of every entry, so this may run to the last `]`.
INDICATORS = re.compile(r"indicators:\s*\[(?P<arr>.*)\]\s*$", re.S)
# One indicator object: `id` always comes first, and the closing brace is the one
# followed by a comma or the end of the array. Matching the brace that way rather
# than by "no nested braces" is what keeps `{element}` inside a text from ending
# the object early.
OBJECT = re.compile(r"\{\s*(?P<obj>id:\s*'.*?)\s*\}(?=\s*(?:,|$))", re.S)
FIELD = re.compile(rf"(?P<key>\w+):\s*(?:{JS_STR}|\[(?P<arr>[^\]]*)\])", re.S)
ITEM = re.compile(JS_STR)

# Indicator types the pipeline knows how to prompt for. `draft` marks a candidate
# that has not been worked on yet (all of dimension 2), and is skipped.
TYPES = {"criterion", "criterion_list", "categorical", "record"}
DRAFT = "draft"
# The array field each type carries, if any, and whether it is required.
TYPE_FIELD = {"criterion_list": "elements", "categorical": "options", "record": "fields"}
REQUIRED_FIELD = {"criterion_list"}
# A criterion_list may give each element a full statement to assess, parallel to
# `elements`. The elements then stay short keys — the JSON keys the model must
# copy back exactly, which a long sentence with quotes in it is a poor fit for —
# and the statement is what the model reads. Without `statements`, the element
# is substituted into the text through {element}, as before.
STATEMENTS = "statements"
ELEMENT_PLACEHOLDER = "{element}"

# The scaffold keys are backtick template literals so the prose can hold quotes
# and blank lines. Nothing in them may contain a backtick or a ${...} expression.
SCAFFOLD_KEYS = ["role", "inputs", "constraints", "method"]
SCAFFOLD_ENTRY = {k: re.compile(rf"^{k}:\s*`([^`]*)`", re.M) for k in SCAFFOLD_KEYS}

# Filled in per call with the documents actually supplied to that call.
DOCUMENTS_PLACEHOLDER = "{documents}"

# Source codes declared on each indicator in the HTML.
SOURCE_NAMES = {
    "C": "questionnaire / data collection instrument",
    "M": "methodological notes and technical reports",
    "G": "interviewer guides and manuals",
}


def unescape(s: str) -> str:
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")


def parse_scaffold(html: str) -> dict:
    """The four prompt blocks, verbatim, from the `scaffold` object."""
    out = {}
    for key, rx in SCAFFOLD_ENTRY.items():
        m = rx.search(html)
        if not m:
            sys.exit(f"scaffold.{key} not found in {HTML} (must be a backtick literal)")
        out[key] = m.group(1).strip()

    if DOCUMENTS_PLACEHOLDER not in out["inputs"]:
        sys.exit(
            f"scaffold.inputs must contain {DOCUMENTS_PLACEHOLDER} — that is where "
            "the runner lists the documents actually supplied to each call."
        )
    return out


def parse_scalar(body: str, key: str) -> str:
    m = re.search(rf"\b{key}:\s*{JS_STR}", body)
    return unescape(m.group(1)) if m else ""


def parse_indicators(key: str, body: str) -> list[dict]:
    """The indicator objects of one entry, in source order, drafts dropped.

    `id` and `doc` are renamed to `indicator_id` and `source_code` — the names
    the rest of the pipeline reads — and every other field of the object is
    carried through unchanged.
    """
    m = INDICATORS.search(body)
    if not m:
        sys.exit(f"content.{key} has no `indicators` array")

    out = []
    for om in OBJECT.finditer(m.group("arr")):
        fields = {}
        for fm in FIELD.finditer(om.group("obj")):
            if fm.group("arr") is not None:
                fields[fm.group("key")] = [unescape(v) for v in ITEM.findall(fm.group("arr"))]
            else:
                fields[fm.group("key")] = unescape(fm.group(2))

        missing = [k for k in ("id", "doc", "type", "text") if not fields.get(k)]
        if missing:
            sys.exit(f"content.{key}: indicator {fields.get('id', '?')} is missing {missing}")

        kind = fields["type"]
        if kind == DRAFT:
            continue
        if kind not in TYPES:
            sys.exit(f"content.{key}: indicator {fields['id']} has unknown type {kind!r}")

        ind = {
            "indicator_id": fields["id"],
            "source_code": fields["doc"],
            "type": kind,
            "text": fields["text"],
        }
        bad_codes = [c for c in fields["doc"].split("+") if c not in SOURCE_NAMES]
        if bad_codes:
            sys.exit(f"content.{key}: indicator {fields['id']} has unknown source {fields['doc']!r}")

        extra = TYPE_FIELD.get(kind)
        if extra and fields.get(extra):
            ind[extra] = fields[extra]
        elif extra and kind in REQUIRED_FIELD:
            sys.exit(f"content.{key}: indicator {fields['id']} is {kind} but has no `{extra}`")

        if kind == "criterion_list" and fields.get(STATEMENTS):
            if len(fields[STATEMENTS]) != len(ind["elements"]):
                sys.exit(
                    f"content.{key}: indicator {fields['id']} has {len(ind['elements'])} "
                    f"elements but {len(fields[STATEMENTS])} statements"
                )
            ind[STATEMENTS] = fields[STATEMENTS]
        elif kind == "criterion_list" and ELEMENT_PLACEHOLDER not in ind["text"]:
            sys.exit(
                f"content.{key}: indicator {fields['id']} is criterion_list but its text "
                f"has no {ELEMENT_PLACEHOLDER} to substitute and no `{STATEMENTS}`"
            )
        out.append(ind)
    return out


def parse(html: str) -> dict:
    entries = {}
    order = []
    for m in ENTRY.finditer(html):
        key = m.group("key")
        body = m.group("body")
        entries[key] = {
            "tag": parse_scalar(body, "tag"),
            "tag_class": parse_scalar(body, "tagClass"),
            "title": parse_scalar(body, "title"),
            "variable": parse_scalar(body, "question"),
            "indicators": parse_indicators(key, body),
        }
        order.append(key)

    if not entries:
        sys.exit(f"No parseable `content` object found in {HTML}")

    # Dimension headings are the coral entries; subdimensions are purple.
    # Dimension 2 (`c1`) is still a candidate list in the HTML, so it is excluded.
    dimension_title = entries.get("c0", {}).get("title", "Dimension 1")

    subdimensions = []
    for key in order:
        e = entries[key]
        if e["tag_class"] != "tag-purple":
            continue
        indicators = e["indicators"]
        if indicators:
            subdimensions.append(
                {
                    "subdimension_id": key,
                    "tag": e["tag"],
                    "title": e["title"],
                    # The HTML writes these as "Variable: ..."; "///" is a manual line break.
                    "variable": re.sub(
                        r"\s+", " ", re.sub(r"^Variable:\s*", "", e["variable"].replace("///", " "))
                    ).strip(),
                    "indicators": indicators,
                }
            )

    return {
        "source_file": str(HTML.relative_to(ROOT)),
        "dimension": dimension_title,
        "scaffold": parse_scaffold(html),
        "source_codes": SOURCE_NAMES,
        "subdimensions": subdimensions,
    }


def main() -> None:
    fw = parse(HTML.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(fw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    n_ind = sum(len(s["indicators"]) for s in fw["subdimensions"])
    print(f"{fw['dimension']}")
    scaf = "  ".join(f"{k} {len(v):,}ch" for k, v in fw["scaffold"].items())
    print(f"scaffold: {scaf}")
    print(f"-> {OUT.relative_to(ROOT)}: {len(fw['subdimensions'])} subdimensions, {n_ind} indicators\n")
    for s in fw["subdimensions"]:
        codes = " ".join(i["source_code"] for i in s["indicators"])
        print(f"  {s['subdimension_id']}  {s['title']:<38} {len(s['indicators'])} indicators  [{codes}]")


if __name__ == "__main__":
    main()
