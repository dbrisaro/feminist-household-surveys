"""Prompt assembly.

Every word sent to the model comes from framework/gender_survey_framework.html.
The scaffold (role / inputs / constraints / method) is lifted verbatim out of the
`scaffold` object there by parse_framework.py; this module only assembles it. To
change the wording, edit the HTML and re-run:

    python scripts/llm/parse_framework.py

Request shape:

    system   = [role + inputs + constraints]   varies only with the document set
    messages = [user: [ ...documents..., task block ]]
                        ^ cache breakpoint here, not at the end of the turn

The documents are the shared prefix; the task block is what varies. Putting the
breakpoint after the documents is the whole reason the run fits in budget. The
system block sits ahead of that breakpoint and is never cached, so listing the
supplied documents in it costs a few tokens per call and nothing in cache hits.
"""

from __future__ import annotations

import copy
import json
import re

import framework as framework_mod

_SCAFFOLD = framework_mod.load()["scaffold"]

ROLE = _SCAFFOLD["role"]
INPUTS = _SCAFFOLD["inputs"]
CONSTRAINTS = _SCAFFOLD["constraints"]
METHOD = _SCAFFOLD["method"]

DOCUMENTS_PLACEHOLDER = "{documents}"


def documents_supplied(manifest: list[dict], source_codes: dict[str, str] | None = None) -> str:
    """The bullet list that replaces {documents} in the inputs block.

    One line per document actually placed in this call's user turn, named exactly
    as its SOURCE DOCUMENT header names it, so a quote's attribution can be
    checked against the list. A sharded document says which part it is.
    """
    labels = source_codes if source_codes is not None else framework_mod.source_codes()
    if not manifest:
        return "- (none — this is a token-count probe, not a real call)"
    lines = []
    for m in manifest:
        code = m["source_code"]
        part = ""
        if m.get("n_parts", 1) > 1:
            part = f", part {m['part']} of {m['n_parts']}"
        lines.append(f"- [{code}] {m['doc']} — {labels.get(code, code)}{part}")
    return "\n".join(lines)


def system_prompt(manifest: list[dict], source_codes: dict[str, str] | None = None) -> str:
    """Role + inputs + constraints, with the supplied documents named in inputs."""
    inputs = INPUTS.replace(
        DOCUMENTS_PLACEHOLDER, documents_supplied(manifest, source_codes)
    )
    return "\n\n".join([ROLE, inputs, CONSTRAINTS])


AXIS = """\
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the \
instrument is designed and worded. Answerable from the questionnaire, the \
methodological notes and the interviewer manuals."""

# The model reports what the instrument does, per indicator type. It assigns no
# label of adequacy: `met` / `partially_met` / `unmet` are derived in report.py
# from the booleans below, which is what the method block means by "Do not assign
# an overall label, a score, or a verdict of adequacy."
#
# Field order in the item schema is load-bearing and must not be rearranged: the
# evidence comes first, the reasoning second, and only then the answer. A model
# that emits `value` before `reasoning` has decided before explaining, and the
# reasoning that follows is a rationalisation of a verdict already fixed.
QUOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation.",
        },
        "document": {
            "type": "string",
            "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it.",
        },
        "location": {
            "type": "string",
            "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none.",
        },
    },
    "required": ["text", "document", "location"],
    "additionalProperties": False,
}

# The fields every assessment carries, in the order they must be written.
BASE_PROPERTIES = {
    "indicator_id": {"type": "string"},
    "quotes": {
        "type": "array",
        "items": QUOTE_SCHEMA,
        # Filled in by output_schema(): the minimum and the description depend on
        # whether the call supplied every source the indicator needs.
    },
    "reasoning": {
        "type": "string",
        "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after.",
    },
}

# Every assessment quotes something, a negative one included (the Evidence
# paragraph of the constraints block). The one exception is a call that could not
# hold the evidence: a shard of a split corpus, or an indicator sent without one
# of the sources it declares. There the schema drops the minimum and says why.
QUOTES_DESCRIPTION = ("Every passage the answer rests on. For a negative answer, the "
                      "passages examined and set aside, or the section where the item "
                      "would be expected.")
QUOTES_EXEMPT_NOTE = (" Empty only when the evidence would be in a document, or a part "
                      "of a document, not supplied in this run.")


# The answer field(s) each indicator type adds after `reasoning`.
VALUE_PROPERTY = {
    "type": "boolean",
    "description": "criterion only: whether the proposition stated by the indicator holds, on the evidence quoted above.",
}
# How a negative criterion is negative. Replaced the boolean `excluded_by_text`
# (2026-10-07), which could not tell "the text reclassifies the item" from "the
# text never mentions it" -- the two ends of that scale were being stretched over
# three different situations, and repeats split over which end to pick.
EXCLUSION_TYPES = ["explicit", "treated_as_other", "not_mentioned"]
EXCLUSION_PROPERTY = {
    "type": "string",
    "enum": EXCLUSION_TYPES,
    "description": (
        "criterion only, and only when `value` is false. One of: "
        "\"explicit\": the text states that the item is excluded, for example by "
        "asking about work \"without counting\" household tasks, or by instructing "
        "the interviewer to reclassify it. "
        "\"treated_as_other\": the text mentions the item but places it in a "
        "different category, for example as a category of inactivity or as a "
        "reason for not working or not seeking work. "
        "\"not_mentioned\": the text does not mention the item at all."
    ),
}
SELECTED_PROPERTY = {
    "type": "string",
    "description": "categorical only: the one option chosen, copied exactly from the options listed for that indicator. Empty string if none of them applies.",
}
EXTRACTED_PROPERTY = {
    "type": "string",
    "description": "record only, when the indicator names no separate fields: the content requested, transcribed verbatim. Empty string if the documents do not contain it.",
}


def elements_property(indicators: list[dict]) -> dict:
    """The `elements` field: one boolean per element of a criterion_list.

    The booleans live inside the indicator's own assessment object — a
    criterion_list is one indicator, assessed once, not several, so there is no
    loose per-element value anywhere. The element names become the keys, spelled
    exactly as the framework declares them, so counting how many held is a
    lookup rather than a parse.

    The keys are named properties rather than a free map because the Gemini
    runner strips `additionalProperties` from the schema, which would leave it an
    object with no declared fields. `additionalProperties: false` is what stops a
    model from inventing an element that was never in the list.

    Every key is required, and that is safe even though one call covers several
    indicators of mixed type: `elements` itself is optional at the item level, and
    a JSON Schema `required` inside an object binds only when that object is
    present. So a criterion indicator in the same call omits the field entirely
    rather than sending an empty object, and the server refuses a criterion_list
    that answers only some of its elements — which is what previously let an
    indicator with three elements come back with one and still be counted whole.

    Requiring the union of every list's elements is deliberately blunt: a call
    covering two criterion_list indicators demands both lists of whichever one
    answers. read_elements() is still what checks the response against the
    elements the framework declares for that specific indicator, and the task
    block still names them per indicator.
    """
    lists = [i for i in indicators if i.get("type") == "criterion_list"]
    names = sorted({e for i in lists for e in (i.get("elements") or [])})
    return {
        "type": "object",
        "properties": {n: {"type": "boolean"} for n in names},
        "required": names,
        "additionalProperties": False,
        "description": (
            "criterion_list indicators only: one boolean per element of that "
            "indicator's list, keyed by the element name exactly as the task "
            "block gives it, and every element of that list answered. Each "
            "element is judged independently, on its own evidence. Omit this "
            "field entirely for indicators of any other type."
        ),
    }


def fields_property(indicators: list[dict]) -> dict:
    """The `fields` field: one string per declared field of a record indicator.

    Same construction as elements_property, and for the same reasons: the keys
    are the field names the framework declares, so the answer needs no parsing,
    and they are all required so that a partial answer is refused rather than
    read as a complete one. A field the documents do not contain is an empty
    string, which is an answer; a field left out is not.
    """
    names = sorted({f for i in indicators
                    if i.get("type") == "record"
                    for f in (i.get("fields") or [])})
    return {
        "type": "object",
        "properties": {n: {"type": "string"} for n in names},
        "required": names,
        "additionalProperties": False,
        "description": (
            "record indicators that name separate fields: the content requested "
            "for each, transcribed verbatim, keyed by the field name exactly as "
            "the task block gives it. Empty string for a field the documents do "
            "not contain. Omit this field entirely for every other indicator."
        ),
    }


def output_schema(indicators: list[dict] | None = None, complete: bool = True) -> dict:
    """The response schema for one call, given the indicators it covers.

    Each indicator type answers in its own field, so the item schema is the union
    of the fields the call's types need — one call covers several indicators and
    a JSON Schema array cannot vary its item shape per element.

    Only `indicator_id`, `quotes` and `reasoning` are required, because they are
    the three every type owes. The answer fields are optional *in the schema* and
    obligatory *in fact*: which one an indicator owes follows from its type, and
    read_assessment() is what enforces it. Requiring them here would instead force
    every indicator in a mixed call to answer in every other indicator's field.

    Insertion order is the wire order — quotes and reasoning ahead of any answer
    field — so these properties must be built in sequence, never merged in from a
    dict literal that happens to sort differently.
    """
    indicators = indicators or []
    types = {i.get("type") for i in indicators}

    properties = copy.deepcopy(BASE_PROPERTIES)
    # `complete` is False for a call that may legitimately hold no evidence --
    # see QUOTES_DESCRIPTION. Only a complete call is held to at least one quote.
    if complete:
        properties["quotes"]["minItems"] = 1
        properties["quotes"]["description"] = QUOTES_DESCRIPTION
    else:
        properties["quotes"]["description"] = QUOTES_DESCRIPTION + QUOTES_EXEMPT_NOTE
    if "criterion" in types:
        properties["value"] = copy.deepcopy(VALUE_PROPERTY)
        properties["exclusion_type"] = copy.deepcopy(EXCLUSION_PROPERTY)
    if "criterion_list" in types:
        properties["elements"] = elements_property(indicators)
    if "categorical" in types:
        properties["selected"] = copy.deepcopy(SELECTED_PROPERTY)
    if "record" in types:
        properties["extracted_text"] = copy.deepcopy(EXTRACTED_PROPERTY)
        if any(i.get("fields") for i in indicators if i.get("type") == "record"):
            properties["fields"] = fields_property(indicators)

    return {
        "type": "object",
        "properties": {
            "assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": ["indicator_id", "quotes", "reasoning"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["assessments"],
        "additionalProperties": False,
    }


def read_elements(indicator: dict, assessment: dict) -> tuple[dict, str]:
    """Pull the per-element booleans of a criterion_list out of one assessment.

    Returns (elements, error). The keys must be exactly the elements the
    framework declares for this indicator: a missing element is an unanswered
    statement and a stray one is an element the model invented, and either way
    the count of true elements — which is what the indicator is for — would be
    wrong. Both are reported rather than silently normalised.
    """
    if indicator.get("type") != "criterion_list":
        return {}, ""

    declared = list(indicator.get("elements") or [])
    got = assessment.get("elements")
    if not isinstance(got, dict):
        return {}, f"criterion_list {indicator['indicator_id']} returned no `elements` object"

    missing = [e for e in declared if e not in got]
    stray = [k for k in got if k not in declared]
    bad = [k for k, v in got.items() if not isinstance(v, bool)]
    problems = []
    if missing:
        problems.append(f"missing {missing}")
    if stray:
        problems.append(f"unexpected {stray}")
    if bad:
        problems.append(f"non-boolean {bad}")

    elements = {e: got[e] for e in declared if isinstance(got.get(e), bool)}
    err = ""
    if problems:
        err = f"criterion_list {indicator['indicator_id']} elements: " + ", ".join(problems)
    return elements, err


def read_quotes(assessment: dict) -> tuple[list[dict], str]:
    """The evidence list, normalised to {text, document, location} dicts.

    An empty list is legitimate — it is what "the documents contain nothing
    bearing on this indicator" looks like — so it is not an error. A quote with
    no text is: it claims evidence and supplies none.
    """
    got = assessment.get("quotes", [])
    if not isinstance(got, list):
        return [], "`quotes` is not a list"
    quotes, empty = [], 0
    for q in got:
        if not isinstance(q, dict):
            empty += 1
            continue
        text = str(q.get("text", "")).strip()
        if not text:
            empty += 1
            continue
        quotes.append({
            "text": text,
            "document": str(q.get("document", "")).strip(),
            "location": str(q.get("location", "")).strip(),
        })
    return quotes, (f"{empty} quote(s) with no text" if empty else "")


# What a reasoning field looks like when it points at the documents: a question,
# section or page marker, a questionnaire item code, or a passage in quotes. Used
# only to flag an answer whose reasoning cites the documents while `quotes` is
# empty -- the constraints block requires every statement to rest on a verbatim
# quote, and an empty list beside such a reasoning means the evidence was named
# but not supplied. Flagged, never rejected: the answer itself may still be right.
_REF_PATTERNS = [
    re.compile(r"\b(?:Questions?|Q|Preguntas?|Preg|Pgta|P)\.?\s*\d+[a-z]?\b", re.I),
    re.compile(r"\b(?:Section|Secci[oó]n|Sezione|Bloque|Block|M[oó]dulo|Module|Parte|Part)"
               r"\s+[0-9IVX]+[A-Z]?\b", re.I),
    re.compile(r"\b(?:p|pp|page|p[aá]gina)\.?\s*\d+\b", re.I),
    re.compile(r"\b[a-z]{1,2}\.\d{1,3}[a-z]?\b"),          # ECH-style items: f.82, e.19
    re.compile(r"\bQ[A-Z]{1,3}\d+[A-Z]?\b"),               # ISTAT-style items: QC29, QSF11
    # A quoted passage. The opening mark must follow a space or bracket, so the
    # apostrophe of a possessive ("person's") never opens a quote.
    re.compile(r"(?:(?<=\s)|(?<=\()|^)['‘\"“]([^'’\"”\n]{3,300}?)['’\"”](?=[\s,.;:)]|$)"),
]


def reasoning_refs(reasoning: str) -> list[str]:
    """Document references found in a reasoning field, in order, deduplicated."""
    found = []
    for rx in _REF_PATTERNS:
        for m in rx.finditer(reasoning or ""):
            s = m.group(0).strip()
            if s not in found:
                found.append(s)
    return found


def uncited_refs(reasoning: str, n_quotes, field_order) -> list[str]:
    """The references a reasoning makes when it came back with no quotes at all.

    Only a parsed model answer is checked -- `field_order` is empty when the call
    failed, and the reasoning column then holds the API's error text, whose JSON
    keys would otherwise read as quoted passages.
    """
    if not field_order or (isinstance(field_order, float)):  # NaN from a CSV
        return []
    try:
        if int(n_quotes or 0) > 0:
            return []
    except (TypeError, ValueError):
        return []
    return reasoning_refs(reasoning)


def read_assessment(indicator: dict, assessment: dict,
                    require_quotes: bool = False) -> tuple[dict, str]:
    """One assessment, normalised to the columns the run log stores.

    Returns (record, error). The answer an indicator owes follows from its type,
    and it is checked here rather than in the schema — a mixed call cannot demand
    per-type fields of every item. An indicator that answered in the wrong field,
    or did not answer at all, is reported: silently defaulting `value` to false
    would turn a missing answer into a finding of absence, which is the one
    mistake this whole framework is built to avoid.
    """
    kind = indicator.get("type", "criterion")
    quotes, err_q = read_quotes(assessment)
    problems = [err_q] if err_q else []
    # A complete call owes at least one quote. The schema asks for it, but not
    # every provider holds a response to the schema, so the reader checks too --
    # recorded as an error on the row, never a reason to drop the answer.
    if require_quotes and not quotes:
        problems.append("no quotes, though every source this indicator needs was supplied")

    # The order the fields actually arrived in. json.loads preserves it, so this
    # is the wire order, and the contract is that the evidence and the reasoning
    # precede the answer. Recording it makes that checkable after the fact from
    # the log alone, instead of resting on the schema having been obeyed.
    order = [k for k in assessment if k != "indicator_id"]
    answer_fields = ("value", "exclusion_type", "excluded_by_text", "elements", "selected",
                     "extracted_text", "fields")
    first_answer = next((i for i, k in enumerate(order) if k in answer_fields), None)
    for late in ("quotes", "reasoning"):
        if late in order and first_answer is not None and order.index(late) > first_answer:
            problems.append(f"`{late}` arrived after `{order[first_answer]}`")

    rec = {
        "type": kind,
        "field_order": order,
        "quotes": quotes,
        "n_quotes": len(quotes),
        "reasoning": str(assessment.get("reasoning", "")).strip(),
        "value": None,
        "exclusion_type": None,
        "elements": {},
        "selected": None,
        "extracted_text": None,
        "fields": {},
    }

    if kind == "criterion":
        v = assessment.get("value")
        if isinstance(v, bool):
            rec["value"] = v
            # Only meaningful on a false: it says how the text is negative --
            # it excludes the item, files it under something else, or never
            # mentions it. A distinction about the document, not the instrument.
            if v is False:
                x = assessment.get("exclusion_type")
                if x in EXCLUSION_TYPES:
                    rec["exclusion_type"] = x
                elif x is None:
                    problems.append("criterion is false but `exclusion_type` is missing")
                else:
                    problems.append(f"`exclusion_type` is not one of {EXCLUSION_TYPES}: {x!r}")
        else:
            problems.append("criterion returned no boolean `value`")

    elif kind == "criterion_list":
        rec["elements"], err_e = read_elements(indicator, assessment)
        if err_e:
            problems.append(err_e)

    elif kind == "categorical":
        sel = assessment.get("selected")
        if not isinstance(sel, str):
            problems.append("categorical returned no `selected` string")
        else:
            sel = sel.strip()
            options = indicator.get("options") or []
            # An empty selection is a real answer: none of the options applies.
            if sel and options and sel not in options:
                problems.append(f"`selected` is not one of the options: {sel!r}")
            rec["selected"] = sel

    elif kind == "record":
        declared = list(indicator.get("fields") or [])
        if declared:
            got = assessment.get("fields")
            if not isinstance(got, dict):
                problems.append("record with declared fields returned no `fields` object")
            else:
                missing = [f for f in declared if not str(got.get(f, "")).strip()]
                stray = [k for k in got if k not in declared]
                rec["fields"] = {f: str(got.get(f, "")).strip() for f in declared}
                if missing:
                    problems.append(f"record fields not filled: {missing}")
                if stray:
                    problems.append(f"record returned unexpected fields: {stray}")
        else:
            txt = assessment.get("extracted_text")
            if not isinstance(txt, str):
                problems.append("record returned no `extracted_text` string")
            else:
                rec["extracted_text"] = txt.strip()

    err = f"{indicator['indicator_id']}: " + "; ".join(problems) if problems else ""
    return rec, err


def empty_assessment(indicator: dict) -> dict:
    """The record for an indicator the model did not answer at all.

    Every answer field is None or empty — never False. A call that failed says
    nothing about the instrument, and must not be readable as a finding of
    absence.
    """
    return {
        "type": indicator.get("type", "criterion"),
        "field_order": [],
        "quotes": [], "n_quotes": 0, "reasoning": "",
        "value": None, "exclusion_type": None, "elements": {},
        "selected": None, "extracted_text": None, "fields": {},
    }


def assessment_columns(answer: dict) -> dict:
    """Flatten one assessment into the columns of the run log.

    Structured fields are stored as JSON text rather than as objects: the log is
    read back as a dataframe, and a column holding dicts is not something CSV or
    pandas can round-trip. `reasoning` is left out — the caller writes it, since
    it has the call-level error text to fall back on.
    """
    elements = answer["elements"]
    return {
        "type": answer["type"],
        # The wire order of the response fields, as received; empty when the
        # indicator was never asked or never answered.
        "field_order": "|".join(answer.get("field_order") or []),
        "quotes": json.dumps(answer["quotes"], ensure_ascii=False) if answer["quotes"] else "",
        "n_quotes": answer["n_quotes"],
        "value": answer["value"],
        "exclusion_type": answer["exclusion_type"],
        "elements": json.dumps(elements, ensure_ascii=False) if elements else "",
        # Null, not zero, for every other type: an indicator with no elements is
        # not an indicator whose elements all came back false.
        "n_elements": len(elements) if answer["type"] == "criterion_list" else None,
        "n_elements_true": sum(elements.values()) if elements else None,
        "selected": answer["selected"],
        "extracted_text": answer["extracted_text"],
        "fields": json.dumps(answer["fields"], ensure_ascii=False) if answer["fields"] else "",
        # Document references in a reasoning that came with no quotes; empty when
        # there are quotes or no references. Recorded, never a reason to reject.
        "uncited_refs": " | ".join(uncited_refs(
            answer["reasoning"], answer["n_quotes"], answer.get("field_order"))),
    }


ELEMENT_PLACEHOLDER = "{element}"


def indicator_lines(ind: dict) -> list[str]:
    """One indicator as it appears in the INDICATORS TO ASSESS list.

    The shape depends on the indicator's `type` as declared in the HTML:

    criterion       the statement, as written
    criterion_list  the statement once per element, {element} substituted, as
                    sub-bullets under the indicator — still one indicator, so
                    still one assessment object, whose `elements` field carries
                    one boolean per element. When the indicator declares
                    `statements`, its text is the question and is printed once,
                    and each sub-bullet is that element's own statement
    categorical     the statement, then the closed set of options to pick from
    record          the statement, then the keys to report under, when the
                    indicator asks for more than one

    An unknown type falls back to the bare statement rather than failing: the
    text alone is always a usable instruction.
    """
    head = f"- [{ind['indicator_id']}] ({ind['source_code']}) "
    kind = ind.get("type", "criterion")

    if kind == "criterion_list":
        elements = ind.get("elements") or []
        statements = ind.get("statements")
        lines = [
            head + "Assess each of the following statements independently. Do not "
            "let the answer to one affect the answer to another."
        ]
        if statements:
            lines.insert(1, "    Question: " + ind["text"])
            lines += [f"    - [{e}] {st}" for e, st in zip(elements, statements)]
        else:
            lines += [
                f"    - [{e}] " + ind["text"].replace(ELEMENT_PLACEHOLDER, e)
                for e in elements
            ]
        lines.append(
            "    Answer in `elements`, as one boolean per statement, keyed by the "
            "name in brackets: " + ", ".join(elements) + "."
        )
        return lines

    lines = [head + ind["text"]]
    if kind == "criterion":
        lines.append(
            "    Answer in `value`. If it is false, give `exclusion_type`: "
            "\"explicit\" if the text states that the item is excluded, "
            "\"treated_as_other\" if the text mentions the item but places it in a "
            "different category, or \"not_mentioned\" if the text does not mention "
            "the item at all."
        )
    elif kind == "categorical":
        if ind.get("options"):
            lines.append("    Options: " + "; ".join(ind["options"]))
        lines.append(
            "    Answer in `selected`, copying one option exactly. If none of "
            "these applies, leave the selection empty."
        )
    elif kind == "record":
        if len(ind.get("fields") or []) > 1:
            lines.append(
                "    Answer in `fields`, transcribing each separately under these "
                "exact keys: " + ", ".join(ind["fields"]) + "."
            )
        else:
            lines.append("    Answer in `extracted_text`, transcribed verbatim.")
    return lines


def dimension_block(dimension: str, subdimension: dict, indicators: list[dict]) -> str:
    """The part of the prompt that changes per call."""
    lines = [
        AXIS,
        "",
        f"DIMENSION: {dimension}",
        f"SUBDIMENSION: {subdimension['title']}",
        f"Variable: {subdimension['variable']}",
        "",
        "INDICATORS TO ASSESS:",
    ]
    for ind in indicators:
        lines += indicator_lines(ind)
    lines += [
        "",
        METHOD,
        "",
        "Return one assessment object per indicator listed above, using the "
        "indicator_id exactly as given.",
    ]
    return "\n".join(lines)


def build_request(
    *,
    dimension: str,
    subdimension: dict,
    indicators: list[dict],
    doc_blocks: list[str],
    manifest: list[dict],
    breakpoints: set[int] | None = None,
):
    """Return (system, messages) for the Messages API.

    `breakpoints` holds indices of document blocks to mark with cache_control.
    The runner marks the last block of each source-code group whose prefix is
    reused at least twice in the run — a cache write costs 1.25x, so caching a
    prefix used once is strictly more expensive than not caching it.

    Because documents are always emitted in sorted source-code order, a call over
    C+M shares its opening bytes with a call over C alone: with a breakpoint at
    the C/M boundary the wider call reads the C half from cache and only pays
    fresh for M.
    """
    breakpoints = breakpoints or set()
    content = []
    for i, b in enumerate(doc_blocks):
        block = {"type": "text", "text": b}
        if i in breakpoints:
            block["cache_control"] = {"type": "ephemeral"}
        content.append(block)
    content.append(
        {"type": "text", "text": dimension_block(dimension, subdimension, indicators)}
    )
    system = [{"type": "text", "text": system_prompt(manifest)}]
    return system, [{"role": "user", "content": content}]


def strip_cache_control(messages: list[dict]) -> list[dict]:
    """count_tokens has no notion of cache reads; send it the plain prefix."""
    out = []
    for m in messages:
        content = [
            {k: v for k, v in b.items() if k != "cache_control"} for b in m["content"]
        ]
        out.append({**m, "content": content})
    return out
