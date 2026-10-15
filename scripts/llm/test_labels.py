"""Tests for the label derivation and the framework shapes it depends on.

No API calls: every case is a synthetic row or a synthetic HTML fragment.

    python -m pytest scripts/llm/test_labels.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import framework as framework_mod  # noqa: E402
import parse_framework  # noqa: E402
import prompts as P  # noqa: E402
from report import label_of  # noqa: E402

NaN = float("nan")


def row(**kw):
    base = {"insufficient_evidence": False, "type": "criterion", "value": None,
            "n_elements_true": NaN, "n_elements": NaN, "n_elements_returned": NaN}
    return {**base, **kw}


def lst(n_true, n, returned=None):
    return row(type="criterion_list", n_elements_true=n_true, n_elements=n,
               n_elements_returned=n if returned is None else returned)


# --- label_of -------------------------------------------------------------

@pytest.mark.parametrize("r, expected", [
    (row(value=True), "met"),
    (row(value=False), "unmet"),
    (row(value=None), "not_labelled"),                 # no answer is not a false
    (lst(3, 3), "met"),
    (lst(1, 3), "partially_met"),
    (lst(0, 3), "unmet"),
    (lst(1, 3, returned=1), "not_labelled"),           # incomplete list
    (lst(5, 5), "met"),                                # d4_i5 has five elements
    (lst(4, 5), "partially_met"),
    (lst(4, 5, returned=4), "not_labelled"),
    (lst(NaN, 5), "not_labelled"),
    (row(type="categorical"), "not_labelled"),
    (row(type="record"), "not_labelled"),
    (row(insufficient_evidence=True, value=True), "insufficient_evidence"),
    (lst(3, 3) | {"insufficient_evidence": True}, "insufficient_evidence"),
])
def test_label_of(r, expected):
    assert label_of(r) == expected


# --- source codes ---------------------------------------------------------

def test_codes_of():
    assert framework_mod.codes_of("C") == ("C",)
    assert framework_mod.codes_of("C+M") == ("C", "M")


@pytest.mark.parametrize("code, docs, expected", [
    ("C+M", {"C": ["q"], "M": ["m"]}, ("C", "M")),
    ("C+M", {"C": ["q"], "M": []}, ("C",)),       # still asked, from what is held
    ("M+C", {"C": ["q"], "M": ["m"]}, ("C", "M")),  # sorted for the cache
    ("G", {"C": ["q"]}, ()),                       # never asked
])
def test_held_codes(code, docs, expected):
    assert framework_mod.held_codes({"source_code": code}, docs) == expected


# --- framework parsing ----------------------------------------------------

def body(indicator: str) -> str:
    return f"    indicators: [\n{indicator}\n    ]"


LIST_WITH_STATEMENTS = """      { id: 'x_i1', doc: 'C+M', type: 'criterion_list',
        text: 'Does the instrument\\'s design do this?',
        elements: ['a', 'b'],
        statements: ['First, with "quotes".', 'Second (mother\\'s ID).'] }"""


def test_statements_parsed():
    [ind] = parse_framework.parse_indicators("x", body(LIST_WITH_STATEMENTS))
    assert ind["source_code"] == "C+M"
    assert ind["elements"] == ["a", "b"]
    assert ind["statements"] == ['First, with "quotes".', "Second (mother's ID)."]


def test_statements_length_mismatch_fails():
    bad = LIST_WITH_STATEMENTS.replace("elements: ['a', 'b']", "elements: ['a', 'b', 'c']")
    with pytest.raises(SystemExit, match="3 elements but 2 statements"):
        parse_framework.parse_indicators("x", body(bad))


def test_list_without_placeholder_or_statements_fails():
    bad = """      { id: 'x_i1', doc: 'C', type: 'criterion_list',
        text: 'No placeholder here.',
        elements: ['a', 'b'] }"""
    with pytest.raises(SystemExit, match="no `statements`"):
        parse_framework.parse_indicators("x", body(bad))


def test_unknown_source_fails():
    bad = LIST_WITH_STATEMENTS.replace("doc: 'C+M'", "doc: 'C+X'")
    with pytest.raises(SystemExit, match="unknown source"):
        parse_framework.parse_indicators("x", body(bad))


# --- prompt rendering -----------------------------------------------------

def test_statements_rendered_under_question():
    [ind] = parse_framework.parse_indicators("x", body(LIST_WITH_STATEMENTS))
    lines = P.indicator_lines(ind)
    assert lines[1] == "    Question: Does the instrument's design do this?"
    assert '    - [a] First, with "quotes".' in lines
    assert "    - [b] Second (mother's ID)." in lines


def test_placeholder_list_unchanged():
    ind = {"indicator_id": "d3_i2", "source_code": "C", "type": "criterion_list",
           "text": "The time use questions cover {element}.",
           "elements": ["paid work", "leisure"]}
    lines = P.indicator_lines(ind)
    assert "    - [paid work] The time use questions cover paid work." in lines
    assert not any(l.startswith("    Question:") for l in lines)


def test_real_framework_d4():
    subs = framework_mod.subdimensions()
    d4 = {i["indicator_id"]: i for i in subs["d4"]["indicators"]}
    for iid in ("d4_i3", "d4_i4", "d4_i5", "d4_i6"):
        assert d4[iid]["type"] == "criterion_list"
        assert len(d4[iid]["statements"]) == len(d4[iid]["elements"])
    assert "d2_i6" not in {i["indicator_id"] for i in subs["d2"]["indicators"]}


# --- uncited reasoning check ----------------------------------------------

def test_uncited_flags_references_without_quotes():
    r = "Question f.82 includes 'quien realiza los quehaceres del hogar' (p. 13); QC29."
    assert P.uncited_refs(r, 0, ["quotes", "reasoning", "elements"]) == \
        ["p. 13", "f.82", "QC29", "'quien realiza los quehaceres del hogar'"]


def test_uncited_ignores_answers_with_quotes_or_no_references():
    order = ["quotes", "reasoning", "value"]
    assert P.uncited_refs("Question 2 asks it.", 1, order) == []
    assert P.uncited_refs("The instrument has no such module.", 0, order) == []
    # a possessive apostrophe never opens a quoted passage
    assert P.uncited_refs("The person's status and the household's head.", 0, order) == []


def test_uncited_ignores_failed_calls():
    err = '{"error": {"code": 503, "message": "The service is currently unavailable."}}'
    assert P.uncited_refs(err, 0, []) == []
    assert P.uncited_refs(err, 0, float("nan")) == []


# --- exclusion_type ---------------------------------------------------------

import run_eval  # noqa: E402

CRIT = {"indicator_id": "d2_i3", "source_code": "C", "type": "criterion",
        "text": "The definition includes X."}


def test_schema_offers_exclusion_type_not_the_old_boolean():
    props = P.output_schema([CRIT])["properties"]["assessments"]["items"]["properties"]
    assert props["exclusion_type"]["enum"] == ["explicit", "treated_as_other", "not_mentioned"]
    assert "excluded_by_text" not in props
    assert list(props)[:4] == ["indicator_id", "quotes", "reasoning", "value"]


@pytest.mark.parametrize("given, kept, problem", [
    ("treated_as_other", "treated_as_other", None),
    (None, None, "`exclusion_type` is missing"),
    ("silent", None, "not one of"),
])
def test_read_exclusion_type(given, kept, problem):
    a = {"indicator_id": "d2_i3", "quotes": [], "reasoning": "r", "value": False}
    if given is not None:
        a["exclusion_type"] = given
    rec, err = P.read_assessment(CRIT, a)
    assert rec["exclusion_type"] == kept
    assert (problem in err) if problem else err == ""


def _rep(n, value, kind=None, **kw):
    r = {"country": "x", "model": "m", "mode": "indicator", "indicator_id": "d2_i3",
         "type": "criterion", "rep": n, "n_reps": 3, "value": value,
         "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0,
         "reasoning": f"rep {n}"}
    if kind is not None:
        r["exclusion_type"] = kind
    return {**r, **kw}


@pytest.mark.parametrize("reps, want, stab, tie", [
    ([(False, "explicit"), (False, "explicit"), (False, "not_mentioned")], "explicit", 0.667, False),
    # one rep saying explicit no longer carries the vote
    ([(False, "explicit"), (False, "not_mentioned"), (False, "not_mentioned")], "not_mentioned", 0.667, False),
    ([(False, "explicit"), (False, "treated_as_other"), (False, "not_mentioned")], None, 0.333, True),
    # only the reps that answered false vote on how
    ([(True, None), (False, "explicit"), (False, "not_mentioned")], None, 0.5, True),
    ([(True, None), (True, None), (False, "explicit")], None, None, False),
])
def test_merge_reps_votes_exclusion_type(reps, want, stab, tie):
    recs = [_rep(i + 1, v, k) for i, (v, k) in enumerate(reps)]
    [m] = run_eval.merge_reps(recs)
    assert m["exclusion_type"] == want
    assert m["exclusion_stability"] == stab
    assert m["exclusion_tie"] is tie
    if want:
        assert m["reasoning"] in {r["reasoning"] for r in recs
                                  if r.get("exclusion_type") == want}


def test_merge_reps_reads_legacy_excluded_by_text():
    recs = [_rep(i + 1, False, excluded_by_text=b) for i, b in enumerate([True, False, False])]
    [m] = run_eval.merge_reps(recs)
    assert m["value"] is False
    assert m["exclusion_type"] is None and m["exclusion_stability"] is None


@pytest.mark.parametrize("kinds, want", [
    (["not_mentioned", "treated_as_other", "not_mentioned"], "treated_as_other"),
    (["treated_as_other", "explicit", "not_mentioned"], "explicit"),
    (["not_mentioned", "not_mentioned"], "not_mentioned"),
])
def test_merge_shards_strongest_exclusion(kinds, want):
    recs = [_rep(1, False, k, n_reps=1, shard=s + 1, n_shards=len(kinds), quotes="")
            for s, k in enumerate(kinds)]
    [m] = run_eval.merge_shards(recs)
    assert m["value"] is False and m["exclusion_type"] == want


# --- quotes are required, except where the evidence was not supplied --------

def _quotes(complete):
    return P.output_schema([CRIT], complete=complete)["properties"]["assessments"][
        "items"]["properties"]["quotes"]


def test_complete_call_requires_a_quote():
    q = _quotes(True)
    assert q["minItems"] == 1
    assert "Empty" not in q["description"]


def test_exempt_call_allows_no_quote_and_says_why():
    q = _quotes(False)
    assert "minItems" not in q
    assert q["description"].endswith("not supplied in this run.")


def test_gemini_schema_keeps_min_items():
    import run_eval_gemini
    s = run_eval_gemini.gemini_schema(P.output_schema([CRIT]))
    assert s["properties"]["assessments"]["items"]["properties"]["quotes"]["minItems"] == 1


def test_reader_flags_missing_quotes_only_when_required():
    a = {"indicator_id": "d2_i3", "quotes": [], "reasoning": "r", "value": True}
    assert "no quotes" in P.read_assessment(CRIT, a, require_quotes=True)[1]
    assert P.read_assessment(CRIT, a, require_quotes=False)[1] == ""


class _Call:
    def __init__(self, indicators, codes, n_shards=1):
        self.indicators, self.codes, self.n_shards = indicators, tuple(codes), n_shards


@pytest.mark.parametrize("source, codes, shards, want", [
    ("C", ["C"], 1, True),
    ("C", ["C"], 2, False),           # a shard may not hold the passage
    ("C+M", ["C"], 1, False),         # sent without one of its sources
    ("C+M", ["C", "M"], 1, True),
])
def test_has_all_sources(source, codes, shards, want):
    ind = {**CRIT, "source_code": source}
    call = _Call([ind], codes, shards)
    assert run_eval.has_all_sources(call, ind) is want
    assert run_eval.call_is_complete(call) is want


# --- categorical and record repeats -----------------------------------------

CAT = {"indicator_id": "d4_i2", "type": "categorical"}
REC = {"indicator_id": "d1_i4", "type": "record"}


def _r(n, ind, **kw):
    return {"country": "x", "model": "m", "mode": "indicator", "rep": n, "n_reps": 3,
            "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0,
            "reasoning": f"rep {n}", **ind, **kw}


@pytest.mark.parametrize("picks, want, stab, tie", [
    (["designated by the respondent"] * 2 + [""], "designated by the respondent", 0.667, False),
    (["", "", "designated by the respondent"], "", 0.667, False),   # empty is an answer
    (["a", "b", ""], None, 0.333, True),
    (["a", None, "a"], "a", 1.0, False),                             # a failed rep does not vote
])
def test_merge_reps_votes_categorical(picks, want, stab, tie):
    recs = [_r(i + 1, CAT, selected=p) for i, p in enumerate(picks)]
    [m] = run_eval.merge_reps(recs)
    assert m["selected"] == want and m["stability"] == stab and m["tie"] is tie
    if not tie:
        assert m["reasoning"] in {r["reasoning"] for r in recs if r["selected"] == want}


def test_merge_reps_record_keeps_the_most_central_text():
    texts = ["Jefe Cónyuge Hijo Nieto Suegro",
             "Jefe Cónyuge Hijo Nieto",
             "Persona referente del hogar"]
    recs = [_r(i + 1, REC, extracted_text=t) for i, t in enumerate(texts)]
    [m] = run_eval.merge_reps(recs)
    assert m["extracted_text"] == texts[0]          # closest to the other two
    assert m["rep_similarity"] == "1-2:0.800|1-3:0.000|2-3:0.000"
    assert m["text_similarity"] == 0.267
    assert m["stability"] is None                   # not a vote share
    import json
    assert [x["text"] for x in json.loads(m["rep_texts"])] == texts


def test_merge_reps_record_edge_cases():
    [m] = run_eval.merge_reps([_r(i + 1, REC, extracted_text="") for i in range(3)])
    assert m["text_similarity"] == 1.0              # all found nothing: agreement
    [m] = run_eval.merge_reps([_r(1, REC, extracted_text="a b c"),
                               _r(2, REC, extracted_text=None)])
    assert m["text_similarity"] is None             # one usable text measures nothing


def test_triage_word_set_unchanged():
    import triage_corpus
    assert triage_corpus.words_of("Cónyuge, HIJO/A y nieto") == frozenset({"conyuge", "hijo", "nieto"})


@pytest.mark.parametrize("picks, want, conflict", [
    (["a", "", "a"], "a", False),          # a shard that found nothing does not disagree
    (["", ""], "", False),
    (["a", "b"], None, True),              # no alphabetical tie-break any more
])
def test_merge_shards_categorical(picks, want, conflict):
    recs = [_r(1, CAT, n_reps=1, selected=p, shard=s + 1, n_shards=len(picks), quotes="")
            for s, p in enumerate(picks)]
    [m] = run_eval.merge_shards(recs)
    assert m["selected"] == want
    assert m["shard_values"] == "|".join(f"{s + 1}:{p}" for s, p in enumerate(picks))
    assert ("disagreed" in m.get("error", "")) is conflict
    assert bool(m.get("tie")) is conflict
