"""Aggregate the raw run logs into the tables that go into the paper.

    python scripts/llm/report.py --country argentina

Writes to outputs/<country>/report/ — every run of the country pooled, keeping the
most recent answer for each indicator x model x mode. With --run, the same tables
for that run alone go to outputs/<country>/runs/<run>/report/.

  results_indicators.csv     one row per indicator x model x mode
  results_subdimensions.csv  verdict composition per subdimension
  token_usage.csv            one row per API call
  cost_summary.csv           cost and cache efficiency per model x mode
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import corpus as corpus_mod
from cost import cost_usd
import framework as framework_mod
import prompts as P

ROOT = Path(__file__).resolve().parents[2]

N_COUNTRIES_TOTAL = 13  # countries with a usable document set, for the scale-up projection

# The label is derived here, from what the model reported — it is never asked for
# and never returned by the model. That separation is the point: the model records
# what the instrument does, and the judgement about what that amounts to is made
# in this file, where it can be read, argued with and changed without re-running
# a single call.
LABEL_ORDER = ["met", "partially_met", "unmet", "insufficient_evidence", "not_labelled"]
# The three labels that are findings about the instrument, and the only ones that
# belong in a proportion. The other two are statements about our evidence:
# insufficient_evidence is a document we do not hold, not_labelled is an answer we
# did not get (or a type that carries no ranking). Neither counts as a numerator
# and neither belongs in a denominator — a survey is not penalised for a gap in
# our corpus, and not credited for one either.
FINDING_LABELS = ["met", "partially_met", "unmet"]
# Types that produce a label at all. categorical and record describe what the
# instrument does without ranking it, so they carry none: there is no sense in
# which "self-declared by the household" is met or unmet.
LABELLED_TYPES = {"criterion", "criterion_list"}


def answer_str(row) -> str:
    """What the model reported for one indicator, short enough for a table cell."""
    kind = row.get("type")
    if kind == "criterion":
        v = row.get("value")
        return "-" if v is None or pd.isna(v) else ("true" if v else "false")
    if kind == "criterion_list":
        # `n_elements` is the count the framework declares, not the count the
        # model returned — see declared_element_counts().
        n_true, n = row.get("n_elements_true"), row.get("n_elements")
        if pd.isna(n_true) or pd.isna(n):
            return "-"
        return f"{int(n_true)}/{int(n)}"
    if kind == "categorical":
        return row.get("selected") or "(none)"
    if kind == "record":
        # A column that is empty for every row of a run comes back as NaN, not as
        # "", and `str(nan)` is the truthy string "nan" — which would read as a
        # record that found something when nothing was found at all.
        def filled(col):
            v = row.get(col)
            return bool(v) and not pd.isna(v) and str(v).strip() not in ("", "{}")
        return "found" if (filled("extracted_text") or filled("fields")) else "(none)"
    return "-"


def label_of(row) -> str:
    """The derived label for one assessed indicator.

    insufficient_evidence outranks everything: it means the indicator's source
    document is not in this country's registry, so the indicator was never asked
    and there is nothing to label. It is a statement about our document
    collection, not about the survey.

    not_labelled is the other non-finding, and it is a different claim: the
    indicator was asked and the answer will not support a label — a type that
    carries no ranking, or a criterion_list whose answer left elements
    unanswered. Kept distinct from insufficient_evidence because the remedy
    differs: one needs a document, the other needs the call re-run.
    """
    if row.get("insufficient_evidence"):
        return "insufficient_evidence"
    kind = row.get("type")
    if kind == "criterion":
        v = row.get("value")
        return {True: "met", False: "unmet"}.get(v, "not_labelled")
    if kind == "criterion_list":
        # The denominator is the number of elements the framework declares, never
        # the number the model happened to return. Counting the returned dict made
        # a list of three answered with one element read as `met`, because 1 of 1
        # held: the label then asserted findings about elements nobody answered.
        n_true, n = row.get("n_elements_true"), row.get("n_elements")
        if pd.isna(n_true) or pd.isna(n) or not int(n):
            return "not_labelled"
        n_true, n = int(n_true), int(n)
        # An incomplete list is not a weak finding, it is an absent one. With one
        # of three elements answered there is no evidence either way about the
        # other two, so neither `partially_met` (which would report a finding
        # about them) nor `unmet` (which would report their absence) is available.
        n_returned = row.get("n_elements_returned")
        if not pd.isna(n_returned) and int(n_returned) < n:
            return "not_labelled"
        if n_true == 0:
            return "unmet"
        return "met" if n_true == n else "partially_met"
    return "not_labelled"


def declared_element_counts(framework: dict) -> dict[str, int]:
    """indicator_id -> how many elements the framework declares for it.

    The run log records `n_elements` as the number of elements the model returned,
    which is the right figure for auditing a response but the wrong denominator for
    a label: an answer that covers one of three declared elements is not an answer
    about a one-element indicator. The framework is the only authority on how many
    statements an indicator makes, so the denominator is taken from here and the
    logged value is overwritten — which also repairs the labels of runs already on
    disk, without re-billing a single call.
    """
    return {
        i["indicator_id"]: len(i.get("elements") or [])
        for s in framework["subdimensions"]
        for i in s["indicators"]
        if i.get("type") == "criterion_list"
    }


def load_runs(country: str, only_runs: list[str] | None = None) -> pd.DataFrame:
    """Read the raw log of every run folder for this country.

    Each run lives in `outputs/<country>/runs/<run>/raw.jsonl` and is tagged with
    its folder name, so a row can always be traced back to the run — and the
    settings that produced it — via that run's manifest.json.
    """
    runs_dir = ROOT / "outputs" / country / "runs"
    if not runs_dir.exists():
        raise SystemExit(f"No runs in {runs_dir.relative_to(ROOT)}")

    logs = sorted(runs_dir.glob("*/raw.jsonl"))
    if only_runs:
        found = {f.parent.name for f in logs}
        unknown = [r for r in only_runs if r not in found]
        if unknown:
            avail = "\n  ".join(p.name for p in sorted(runs_dir.iterdir()) if p.is_dir())
            raise SystemExit(f"No run named {unknown!r}. Available:\n  {avail}")
        logs = [f for f in logs if f.parent.name in only_runs]

    rows = []
    for f in logs:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append({**json.loads(line), "run": f.parent.name})
    if not rows:
        raise SystemExit(f"No assessments in {runs_dir.relative_to(ROOT)}")
    df = pd.DataFrame(rows)

    # Runs recorded before the schema migration carry a `verdict` label from the
    # model and none of the typed answer fields. There is no way to derive `value`
    # from `explicitly_stated`: the old label mixed the finding with the strength
    # of its evidence, and the two cannot be pulled back apart after the fact. So
    # those rows are dropped rather than guessed at, and whatever CSVs they
    # produced are left exactly where they are.
    legacy = df["type"].isna() if "type" in df.columns else pd.Series(True, index=df.index)
    if legacy.any():
        runs = ", ".join(sorted(df.loc[legacy, "run"].unique()))
        print(f"skipping {int(legacy.sum())} row(s) from {legacy.groupby(df['run']).any().sum()} "
              f"pre-migration run(s) — verdict schema, not comparable: {runs}")
        df = df[~legacy].copy()
    if df.empty:
        raise SystemExit(
            "No runs in the current schema. Every run for this country predates the "
            "migration off `verdict`, so no table was written and the existing CSVs "
            "were left untouched. Re-run run_eval.py to produce comparable results."
        )

    for col, default in (("merged", False), ("rep_merged", False), ("shard", 0),
                         ("n_shards", 1), ("rep", 0), ("n_reps", 1),
                         ("stability", pd.NA), ("rep_values", ""), ("tie", False),
                         ("source_missing", False),
                         # Runs on a free-tier key carry a cost figure that is not
                         # money. Rows written before this column existed are from
                         # paid Anthropic runs, so False is the right default.
                         ("cost_notional", False), ("billing", "paid")):
        if col not in df.columns:
            df[col] = default
    for col in ("merged", "rep_merged", "tie", "source_missing", "cost_notional"):
        df[col] = df[col].fillna(False).astype(bool)
    for col in ("n_shards", "n_reps"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(1).astype(int)
    for col in ("n_elements", "n_elements_true", "n_quotes"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    return df


def assessments(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (country, model, mode, indicator).

    The log holds up to three generations of the same assessment: the per-shard
    and per-rep rows are the billing record, the shard-merged row is the
    conclusion for one rep, and the rep-voted row is the conclusion overall. They
    have to be ranked, not just deduplicated, because each generation supersedes
    the one below it. Ranking explicitly beats relying on the order the rows
    happen to sit in the log.
    """
    df = df[(df["call"] == True) | (df["merged"]) | (df["n_shards"] <= 1)].copy()  # noqa: E712
    df = df[~((df["n_shards"] > 1) & (~df["merged"]))]
    # A repeated indicator is only settled by its vote, so drop the individual
    # reps once one exists; without this the last rep would masquerade as the
    # verdict and the whole reliability run would be silently discarded.
    df = df[~((df["n_reps"] > 1) & (~df["rep_merged"]))]
    df["generation"] = df["merged"].astype(int) + df["rep_merged"].astype(int)
    return df.sort_values(["run_timestamp", "generation"]).drop_duplicates(
        subset=["country", "model", "mode", "indicator_id"], keep="last"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="argentina")
    ap.add_argument("--run", nargs="+", metavar="RUN",
                    help="report these run folders only; default pools all runs")
    ap.add_argument("--name", help="required with several --run folders: the report is "
                                   "written to outputs/<country>/reports/<name>/")
    args = ap.parse_args()
    if args.run and len(args.run) > 1 and not args.name:
        ap.error("several --run folders need --name for the combined report")

    # A single-run report belongs beside that run; a pooled report sits at the
    # country level, above the runs it pools. The single-run tables go one level
    # down, in `report/`, because they carry the same five filenames as the pooled
    # ones and the two answer different questions: `report/results_indicators.csv`
    # is this run, `outputs/<country>/results_indicators.csv` is every run at once.
    # Nested, they cannot be confused — and load_runs() globs `runs/*/raw.jsonl`,
    # one level deep, so a report/ directory is never mistaken for a run.
    #
    # Several runs chosen by hand (e.g. one per subdimension, so a failed batch is
    # re-run alone) are neither: they get a named folder of their own under
    # `reports/`, which load_runs() never globs either.
    if args.run and len(args.run) > 1:
        out = ROOT / "outputs" / args.country / "reports" / args.name
    elif args.run:
        out = ROOT / "outputs" / args.country / "runs" / args.run[0] / "report"
    else:
        out = ROOT / "outputs" / args.country / "report"
    out.mkdir(parents=True, exist_ok=True)
    fw = framework_mod.load()
    meta = framework_mod.subdimensions(fw)
    ind_text = {
        i["indicator_id"]: i["text"]
        for s in fw["subdimensions"]
        for i in s["indicators"]
    }

    raw = load_runs(args.country, args.run)
    # Coerce on `raw`, before the split: the per-call usage table is built from it
    # too, and the shard rows are the only record of what was actually billed.
    for col in ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                "output_tokens", "cost_usd", "latency_s", "n_indicators_in_call"]:
        raw[col] = pd.to_numeric(raw.get(col), errors="coerce").fillna(0)
    df = assessments(raw)
    df["dimension"] = fw["dimension"]
    df["subdimension_title"] = df["subdimension_id"].map(lambda k: meta[k]["title"])
    df["indicator_text"] = df["indicator_id"].map(ind_text)

    # An indicator is insufficient_evidence when the document type it is routed to
    # is not in this country's registry. Asking the registry rather than trusting
    # a flag on the row means the label is right even for a row written before a
    # document was added, or after one was withdrawn. A multi-source indicator
    # (`C+M`) is answerable when any of its sources is held, as the runners ask it.
    docs = corpus_mod.load_docs(args.country)
    df["insufficient_evidence"] = df["source_code"].map(
        lambda code: not framework_mod.held_codes({"source_code": code}, docs))

    # Replace the logged element count with the declared one before anything reads
    # it: label_of() and answer_str() both take the denominator from this column.
    # The logged value is kept as `n_elements_returned`, because the gap between
    # the two is what decides not_labelled — and because a reader of the CSV needs
    # to see that the answer was short, not just that it carried no label.
    declared = declared_element_counts(fw)
    df["n_elements_returned"] = df["n_elements"]
    is_list = df["type"] == "criterion_list"
    if is_list.any():
        df.loc[is_list, "n_elements"] = df.loc[is_list, "indicator_id"].map(declared)
        short = df[is_list & df["n_elements_returned"].notna()
                   & (df["n_elements_returned"] < df["n_elements"])]
        for _, r in short.iterrows():
            print(f"{r['indicator_id']}: {int(r['n_elements_returned'])} of "
                  f"{int(r['n_elements'])} declared elements answered "
                  f"-> not_labelled")

    df["label"] = df.apply(label_of, axis=1)

    # Recomputed here rather than read from the log, so runs written before the
    # check existed are covered by the same rule.
    def uncited(r):
        return " | ".join(P.uncited_refs(r.get("reasoning"), r.get("n_quotes"),
                                         r.get("field_order")))
    df["uncited_refs"] = df.apply(uncited, axis=1)
    unexpected = df[(df["label"] == "not_labelled") & df["type"].isin(LABELLED_TYPES)]
    if len(unexpected):
        print(f"\n{len(unexpected)} labelled-type indicator(s) carry no label — "
              f"no answer, or an incomplete one (see the `error` column): "
              f"{', '.join(sorted(unexpected['indicator_id'].unique()))}")

    # --- 1. indicator-level results -------------------------------------
    ind_cols = ["country", "dimension", "subdimension_id", "subdimension_title",
                "indicator_id", "source_code", "indicator_text", "type",
                "model", "mode",
                # exclusion_type replaced excluded_by_text on 2026-10-07; runs
                # from before carry only the old boolean, so both are kept and the
                # column filter below drops whichever no loaded run has.
                "label", "value", "exclusion_type", "excluded_by_text",
                "elements", "n_elements_true", "n_elements", "n_elements_returned",
                "selected", "extracted_text", "fields",
                "stability", "rep_values", "tie",
                "exclusion_stability", "exclusion_values", "exclusion_tie",
                "text_similarity", "rep_similarity", "rep_texts",
                "n_quotes", "quotes", "reasoning", "uncited_refs", "field_order", "error",
                "input_tokens", "cache_read_input_tokens", "output_tokens",
                "cost_usd", "latency_s", "run_timestamp"]
    # A column only exists once a run has covered an indicator type that produces
    # it: a run restricted to d1 has no `selected` at all.
    ind_cols = [c for c in ind_cols if c in df.columns]
    ind = df[ind_cols].sort_values(["model", "mode", "indicator_id"])
    ind.to_csv(out / "results_indicators.csv", index=False)

    # --- 1b. every repetition, not just the one that won the vote --------
    # results_indicators.csv keeps a single quote per indicator -- the witness rep
    # that voted with the majority. For a reliability run that is not enough: the
    # question the run exists to answer is *why* a dissenting rep disagreed, and
    # that reasoning lives only in the individual calls.
    reps = raw[(raw["call"] == True) & (pd.to_numeric(raw.get("rep"), errors="coerce") >= 1)]  # noqa: E712
    if len(reps):
        reps = reps.copy()
        reps["subdimension_title"] = reps["subdimension_id"].map(lambda k: meta[k]["title"])
        reps["indicator_text"] = reps["indicator_id"].map(ind_text)
        # Each rep is compared against the answer that won its vote, in the field
        # its own type answers in: `value` for a criterion, the element booleans
        # for a criterion_list. categorical and record are not voted, so they have
        # nothing to agree or disagree with and the column is left null.
        won = df.set_index(["model", "mode", "indicator_id"])
        key = list(zip(reps["model"], reps["mode"], reps["indicator_id"]))
        reps["voted_value"] = [won["value"].get(k) for k in key]
        reps["voted_elements"] = [won["elements"].get(k) if "elements" in won else None
                                  for k in key]

        def agrees(r):
            if r["type"] == "criterion":
                return r.get("value") == r.get("voted_value")
            if r["type"] == "criterion_list":
                return r.get("elements") == r.get("voted_elements")
            return None

        reps["agrees_with_vote"] = reps.apply(agrees, axis=1)
        reps["uncited_refs"] = reps.apply(uncited, axis=1)
        rep_cols = ["country", "subdimension_id", "subdimension_title", "indicator_id",
                    "source_code", "indicator_text", "type", "model", "mode", "rep",
                    "value", "voted_value", "exclusion_type", "excluded_by_text",
                    "elements", "voted_elements",
                    "n_elements_true", "agrees_with_vote",
                    "selected", "extracted_text", "fields",
                    "n_quotes", "quotes", "reasoning", "uncited_refs", "field_order", "error",
                    "shard", "cost_usd", "latency_s", "run", "run_timestamp"]
        rep_cols = [c for c in rep_cols if c in reps.columns]
        reps[rep_cols].sort_values(["model", "mode", "indicator_id", "rep"]).to_csv(
            out / "results_repetitions.csv", index=False)

    # --- 2. subdimension-level composition ------------------------------
    sub = (
        df.groupby(["country", "model", "mode", "subdimension_id", "subdimension_title"])["label"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=LABEL_ORDER, fill_value=0)
        .reset_index()
    )
    sub["n_indicators"] = sub[LABEL_ORDER].sum(axis=1)
    # The denominator for every share below: only the indicators that produced a
    # finding about the instrument. Both non-findings are excluded, and for the
    # same reason — neither says anything about the survey, so neither may dilute
    # its score. insufficient_evidence is a document we do not hold;
    # not_labelled is an answer we did not get, or a type that carries no
    # ranking. An excluded row contributes nothing at all: not 0, not 0.5.
    labelled = sub[FINDING_LABELS].sum(axis=1)
    sub["n_labelled"] = labelled
    sub["pct_met"] = (sub["met"] / labelled.where(labelled > 0)).round(3)
    # partially_met counted as half: a criterion_list with two of three elements
    # is a real, partial capability, and scoring it 0 would erase the difference
    # between a survey that measures some of unpaid work and one that measures
    # none. The halving is a convention of this table, not a finding.
    sub["score"] = (
        (sub["met"] + 0.5 * sub["partially_met"]) / labelled.where(labelled > 0)
    ).round(3)
    # Mean test-retest stability of the indicators in this subdimension, when the
    # run was repeated. NaN for single-shot runs, which is the honest value: an
    # unrepeated answer has no measured stability, it is not perfectly stable.
    # Only criterion and criterion_list contribute — the others are not voted.
    stab = pd.to_numeric(df["stability"], errors="coerce")
    if stab.notna().any():
        means = (
            df.assign(stability=stab)
            .groupby(["country", "model", "mode", "subdimension_id"])["stability"]
            .mean().round(3).rename("mean_stability").reset_index()
        )
        sub = sub.merge(means, on=["country", "model", "mode", "subdimension_id"], how="left")
    sub.to_csv(out / "results_subdimensions.csv", index=False)

    # --- 3. per-call token usage ----------------------------------------
    calls = raw[raw["call"] == True].copy()  # noqa: E712
    call_cols = ["country", "model", "mode", "subdimension_id", "cache_key", "cached_codes",
                 "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                 "output_tokens", "answer_tokens", "thoughts_tokens",
                 "cost_usd", "cost_notional", "billing",
                 "latency_s", "stop_reason", "effort", "response_file",
                 "n_indicators_in_call", "run_timestamp"]
    # answer/thoughts and response_file only exist on runs recorded after they were
    # added; an older paid run is still readable without them.
    call_cols = [c for c in call_cols if c in calls.columns]
    usage = (
        calls[call_cols + ["indicator_id"]]
        .drop_duplicates(subset=["model", "mode", "subdimension_id", "run_timestamp",
                                 "cache_key", "input_tokens", "output_tokens"])
        .drop(columns=["indicator_id"])
        .sort_values(["model", "mode", "run_timestamp"])
    )
    usage.to_csv(out / "token_usage.csv", index=False)

    # --- 4. cost summary -------------------------------------------------
    g = usage.groupby(["model", "mode"])
    summary = g.agg(
        api_calls=("cost_usd", "size"),
        fresh_input_tokens=("input_tokens", "sum"),
        cache_write_tokens=("cache_creation_input_tokens", "sum"),
        cache_read_tokens=("cache_read_input_tokens", "sum"),
        output_tokens=("output_tokens", "sum"),
        cost_usd=("cost_usd", "sum"),
        wallclock_s=("latency_s", "sum"),
    ).reset_index()

    summary["total_input_tokens"] = (
        summary["fresh_input_tokens"] + summary["cache_write_tokens"] + summary["cache_read_tokens"]
    )
    summary["pct_input_from_cache"] = (
        summary["cache_read_tokens"] / summary["total_input_tokens"]
    ).round(3)
    # What the same tokens would have cost with no caching at all.
    summary["cost_usd_no_cache"] = [
        cost_usd(r.model, input_tokens=int(r.total_input_tokens), output_tokens=int(r.output_tokens))
        for r in summary.itertuples()
    ]
    summary["cache_saving_usd"] = (summary["cost_usd_no_cache"] - summary["cost_usd"]).round(4)
    summary["cache_saving_pct"] = (
        summary["cache_saving_usd"] / summary["cost_usd_no_cache"]
    ).round(3)
    # Whether this configuration's cost is money or a counterfactual. A model×mode
    # is one provider on one key, so the flag is uniform within the group; `max`
    # would flag a group only if some row in it was notional, which is what we want
    # to surface rather than average away.
    notional = (calls.groupby(["model", "mode"])["cost_notional"]
                .max().rename("cost_notional").reset_index())
    summary = summary.merge(notional, on=["model", "mode"], how="left")
    summary["cost_notional"] = summary["cost_notional"].fillna(False).astype(bool)
    summary["projected_13_countries_usd"] = (summary["cost_usd"] * N_COUNTRIES_TOTAL).round(2)
    summary["cost_usd"] = summary["cost_usd"].round(4)
    summary["cost_usd_no_cache"] = summary["cost_usd_no_cache"].round(4)
    summary.insert(0, "country", args.country)
    summary.to_csv(out / "cost_summary.csv", index=False)

    # --- console ---------------------------------------------------------
    pd.set_option("display.width", 200)
    print(f"\n{fw['dimension']} — {args.country}\n")
    print("LABELS (derived here, not returned by the model)")
    print(
        df.pivot_table(index="indicator_id", columns=["model", "mode"], values="label",
                       aggfunc="first").fillna("-").to_string()
    )
    # The label is a summary; what the model actually reported is the answer, and
    # for the unlabelled types it is the only thing there is to show.
    print("\nANSWERS")
    print(
        df.assign(answer=df.apply(answer_str, axis=1))
        .pivot_table(index="indicator_id", columns=["model", "mode"], values="answer",
                     aggfunc="first").fillna("-").to_string()
    )
    print("\nCOST")
    print(summary[["model", "mode", "api_calls", "total_input_tokens", "output_tokens",
                   "pct_input_from_cache", "cost_usd", "cost_usd_no_cache",
                   "cache_saving_pct", "projected_13_countries_usd"]].to_string(index=False))

    both = df.pivot_table(index=["subdimension_id", "indicator_id"], columns="model",
                          values="label", aggfunc=lambda s: s.mode().iat[0])
    if {"claude-opus-5", "claude-sonnet-5"} <= set(both.columns):
        disagree = both[both["claude-opus-5"] != both["claude-sonnet-5"]]
        print(f"\nMODEL DISAGREEMENT: {len(disagree)}/{len(both)} indicators")
        if len(disagree):
            print(disagree.to_string())

    # Every call, not only the rep that won the vote: an uncited answer that lost
    # the vote is still an answer that broke the evidence constraint.
    calls = raw[raw["call"] == True].copy()  # noqa: E712
    calls["uncited_refs"] = calls.apply(uncited, axis=1)
    answered = calls[calls["field_order"].fillna("").astype(str) != ""]
    flagged = answered[answered["uncited_refs"] != ""]
    print(f"\nUNCITED REASONING: {len(flagged)} of {len(answered)} answers name document "
          f"passages with an empty `quotes` field (column `uncited_refs`)")
    for _, r in flagged.iterrows():
        print(f"    {r['indicator_id']:<8} rep {r.get('rep', 1)}  {r['uncited_refs'][:110]}")

    real = usage.loc[~usage["cost_notional"].astype(bool), "cost_usd"].sum()
    fake = usage.loc[usage["cost_notional"].astype(bool), "cost_usd"].sum()
    print(f"\nTOTAL SPENT: ${real:.4f}")
    if fake:
        print(f"  (plus ${fake:.4f} notional — free-tier calls that cost quota, "
              f"not money; see the cost_notional column)")
    for f in ["results_indicators.csv", "results_subdimensions.csv", "token_usage.csv", "cost_summary.csv"]:
        print(f"  -> {(out / f).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
