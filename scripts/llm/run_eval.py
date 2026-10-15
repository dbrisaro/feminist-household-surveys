"""Run the framework against a country's survey documentation and meter the spend.

Two axes:
  --mode subdimension   one call per subdimension (the whole indicator group at once)
  --mode indicator      one call per indicator (each call loads only its own source)

Dry run is the default and costs nothing: count_tokens is a free endpoint, so the
exact input cost is known before any billable call is made. Add --go to spend.

    python scripts/llm/run_eval.py --country argentina --mode subdimension indicator \
        --model claude-sonnet-5 claude-opus-5
    python scripts/llm/run_eval.py --country argentina --mode subdimension \
        --model claude-sonnet-5 --go --budget-usd 3.00
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anthropic  # noqa: E402

import corpus as corpus_mod  # noqa: E402
import framework as framework_mod  # noqa: E402
import prompts as P  # noqa: E402
from triage_corpus import jaccard, words_of  # noqa: E402
from cost import cost_from_usage, cost_usd, price_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

MAX_TOKENS = {"subdimension": 8000, "indicator": 4000}


class Call:
    """One planned unit of work."""

    def __init__(self, model, mode, subdim, indicators, codes, missing_codes,
                 shard=1, n_shards=1, rep=1, n_reps=1):
        self.model = model
        self.mode = mode
        self.subdim = subdim
        self.indicators = indicators
        self.codes = tuple(sorted(set(codes)))
        self.missing_codes = missing_codes
        # Repeats of one call are byte-identical requests. They share a cache key
        # on purpose: rep 1 writes the prefix, reps 2..n read it, which is why
        # repeating is sublinear in cost. Nothing else about them differs -- the
        # variation being measured is the sampler's, not the prompt's.
        self.rep = rep
        self.n_reps = n_reps
        # Shards of one corpus share no bytes, so they must not share a cache key:
        # a shard-2 call reading a shard-1 prefix would be a cache miss charged as
        # a hit in the projection.
        self.shard = shard
        self.n_shards = n_shards
        self.cache_key = (corpus_mod.cache_key(codes) if codes else "")
        if n_shards > 1:
            self.cache_key += f"#{shard}/{n_shards}"
        self.input_tokens = 0  # filled in during planning, via count_tokens
        self.breakpoints: set[int] = set()
        self.cached_codes: tuple[str, ...] = ()  # groups behind a cache breakpoint

    @property
    def label(self):
        base = (self.indicators[0]["indicator_id"] if self.mode == "indicator"
                else self.subdim["subdimension_id"])
        return f"{base}~{self.shard}/{self.n_shards}" if self.n_shards > 1 else base


def has_all_sources(call, indicator) -> bool:
    """Whether this call supplied everything the indicator could draw on: a single
    shard, and every source code the indicator declares. Only then is it held to
    at least one quote -- a shard without the relevant chapter, or a C+M indicator
    sent with C alone, may have nothing to quote."""
    return (call.n_shards == 1
            and set(framework_mod.codes_of(indicator["source_code"])) <= set(call.codes))


def call_is_complete(call) -> bool:
    return all(has_all_sources(call, i) for i in call.indicators)


def plan(framework, country, models, modes, docs, only=None, shard_counts=None, repeats=1):
    """Build the call list plus the source_missing records that need no API call.

    `shard_counts` maps a tuple of source codes to how many shards that corpus was
    split into. A corpus that fits a single call has one shard, so the default of
    an empty mapping reproduces the unsharded behaviour exactly.

    `repeats` asks each unit of work `n` times so the instrument's own test-retest
    variation can be measured. repeats=1 reproduces the single-shot behaviour
    exactly, down to the absence of the extra rows in the log.
    """
    shard_counts = shard_counts or {}
    calls, missing = [], []
    for model in models:
        for mode in modes:
            for sub in framework["subdimensions"]:
                if only and sub["subdimension_id"] not in only:
                    continue
                available, unavailable = [], []
                for ind in sub["indicators"]:
                    (available if framework_mod.held_codes(ind, docs) else unavailable).append(ind)

                for ind in unavailable:
                    missing.append(
                        {
                            "country": country,
                            "model": model,
                            "mode": mode,
                            "subdimension_id": sub["subdimension_id"],
                            "indicator_id": ind["indicator_id"],
                            "source_code": ind["source_code"],
                            # No answer fields at all: the indicator was never
                            # asked. report.py labels these insufficient_evidence
                            # from the country's document registry, so nothing
                            # here should look like a finding.
                            **P.assessment_columns(P.empty_assessment(ind)),
                            "source_missing": True,
                            "reasoning": (
                                f"No document of type {ind['source_code']} is available for "
                                f"{country}; the indicator was not sent to the model. This is a "
                                "gap in the source collection, not a property of the survey."
                            ),
                        }
                    )
                if not available:
                    continue

                # One call per (unit of work x shard). Every shard sees the same
                # question and a different slice of the corpus; merge_shards folds
                # them back into one answer per indicator.
                if mode == "subdimension":
                    codes = tuple(sorted({c for i in available
                                         for c in framework_mod.held_codes(i, docs)}))
                    n = shard_counts.get(codes, 1)
                    for s in range(1, n + 1):
                        for rep in range(1, repeats + 1):
                            calls.append(Call(model, mode, sub, available, codes,
                                              [i["source_code"] for i in unavailable],
                                              s, n, rep, repeats))
                else:
                    for ind in available:
                        codes = framework_mod.held_codes(ind, docs)
                        n = shard_counts.get(codes, 1)
                        for s in range(1, n + 1):
                            for rep in range(1, repeats + 1):
                                calls.append(Call(model, mode, sub, [ind], codes, [],
                                                  s, n, rep, repeats))

    # Group by (model, cache_key): the cache is model-scoped with a 5 minute TTL,
    # so interleaving models or corpora makes every call pay a cold prefix.
    # Sorting by cache_key also puts "C" before "C+M", so the narrower call writes
    # the C prefix that the wider one then reads.
    # `cache_key` sorting is what keeps repeats cheap: every call over the same
    # corpus is contiguous, so the document prefix stays inside the 5 minute TTL
    # for all of them. Repeats of one indicator need not be adjacent to each other
    # -- they share the prefix with every other call on the same corpus, not just
    # with their own siblings. `rep` sorts last only to make the order stable.
    calls.sort(key=lambda c: (c.model, c.mode, c.cache_key, c.shard, c.rep))

    # How many calls share each *prefix* of source codes? Documents are emitted in
    # sorted code order, so a call over ("C","M") shares its opening bytes with
    # every call over ("C",).
    prefix_uses: dict = {}
    for c in calls:
        for i in range(1, len(c.codes) + 1):
            k = (c.model, c.mode, c.shard, c.codes[:i])
            prefix_uses[k] = prefix_uses.get(k, 0) + 1

    for c in calls:
        cached = []
        for i in range(1, len(c.codes) + 1):
            # A cache write costs 1.25x: only mark a boundary whose prefix is reused.
            # Max 4 breakpoints per request.
            if prefix_uses[(c.model, c.mode, c.shard, c.codes[:i])] >= 2 and len(cached) < 4:
                cached.append(c.codes[i - 1])
        c.cached_codes = tuple(cached)
    return calls, missing


def measure(client, framework, country, calls, docs, shards=None):
    """Fill in exact token counts. count_tokens is free, so the input side of the
    bill is known before a single billable call is made.

    `shards` maps a codes tuple to the list build_shards returned for it, so a
    sharded call takes its blocks from its own slice rather than rebuilding the
    whole corpus.
    """
    shards = shards or {}
    group_tokens: dict = {}   # (model, code, shard) -> tokens of that source group
    tail_tokens: dict = {}    # (model, label, mode) -> system + task block

    for c in calls:
        if c.codes in shards:
            doc_blocks, manifest, group_end = shards[c.codes][c.shard - 1]
        else:
            doc_blocks, manifest, group_end = corpus_mod.build(country, c.codes, docs)
        c.doc_blocks, c.manifest, c.group_end = doc_blocks, manifest, group_end
        # A shard need not contain every code: only mark boundaries it actually has.
        c.breakpoints = {group_end[code] for code in c.cached_codes if code in group_end}

        for code in c.codes:
            key = (c.model, code, c.shard)
            if key not in group_tokens:
                blocks = [b for b, m in zip(doc_blocks, manifest)
                          if m["source_code"] == code]
                group_tokens[key] = client.messages.count_tokens(
                    model=c.model,
                    messages=[{"role": "user", "content": "\n\n".join(blocks)}],
                ).input_tokens if blocks else 0

        tail_key = (c.model, c.label, c.mode)
        if tail_key not in tail_tokens:
            system, messages = P.build_request(
                dimension=framework["dimension"], subdimension=c.subdim,
                indicators=c.indicators, doc_blocks=[], manifest=c.manifest,
            )
            tail_tokens[tail_key] = client.messages.count_tokens(
                model=c.model, system=system, messages=messages
            ).input_tokens

        c.group_tokens = {code: group_tokens[(c.model, code, c.shard)] for code in c.codes}
        c.tail_tokens = tail_tokens[tail_key]
        c.input_tokens = sum(c.group_tokens.values()) + c.tail_tokens
    return calls


def project(calls):
    """Projected input split per (model, mode), simulating the cache group by group
    in execution order."""
    rows = {}
    written = set()
    for c in calls:
        r = rows.setdefault((c.model, c.mode), {"calls": 0, "fresh": 0, "write": 0, "read": 0})
        r["calls"] += 1
        for i, code in enumerate(c.codes, start=1):
            n = c.group_tokens[code]
            if code not in c.cached_codes:
                r["fresh"] += n
                continue
            prefix_id = (c.model, c.mode, c.shard, c.codes[:i])
            if prefix_id in written:
                r["read"] += n
            else:
                written.add(prefix_id)
                r["write"] += n
        r["fresh"] += c.tail_tokens  # the task block sits after the last breakpoint
    return rows


PROVIDER = "anthropic"


class Tee:
    """Echo everything printed to a file as well as the terminal.

    The console output is the only place some things are said -- which calls were
    skipped, which indicators disagreed across repeats, where the budget stopped.
    Keeping a copy inside the run folder means a run can be read back months later
    without re-deriving it from the JSONL.
    """

    def __init__(self, path):
        self.file = path.open("w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, s):
        self.stdout.write(s)
        self.file.write(s)
        return len(s)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def run_name(args, stamp: str, provider: str = PROVIDER) -> str:
    """A folder name that says what the run was without opening anything.

    e.g. d2_i3__gemini-3.6-flash__subdimension__x3__2026-08-28_02

    Scope leads, because that is what you go looking for: every run of the same
    indicator group sorts together. The date and a per-day sequence close it, and
    are only there to disambiguate — the exact start time lives in the manifest.
    Why the run happened is not encoded here at all; that is `--note`.
    """
    scope = "-".join(args.only) if args.only else "all"
    models = "+".join(m.replace("claude-", "") for m in args.model)
    parts = [scope, models, "+".join(args.mode)]
    # Only Anthropic is sent an effort level, so only an Anthropic run may name
    # one. Putting `medium` on a Gemini folder would advertise a setting that
    # call never had — the same reason the manifest records it as None there.
    if provider == PROVIDER:
        parts.append(args.effort)
    parts.append(f"x{getattr(args, 'repeat', 1)}")
    parts.append(run_seq(args.country, stamp))
    # A dry run holds a cost projection and no answers. Saying so in the name
    # keeps it from being read as a result.
    if not args.go:
        parts.append("dry")
    return "__".join(parts)


def run_seq(country: str, stamp: str) -> str:
    """`YYYY-MM-DD_NN` — the date, and which run of that day this is.

    The count is over every run of the country that day, whatever its scope, so
    the pair is unique and reads in the order the work happened. Bumped until the
    path is free rather than derived from a count, so two runs finishing at once
    cannot land on the same folder.
    """
    date = f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"
    runs_dir = ROOT / "outputs" / country / "runs"
    n = 1
    while any(runs_dir.glob(f"*__{date}_{n:02d}")) or any(runs_dir.glob(f"*__{date}_{n:02d}__*")):
        n += 1
    return f"{date}_{n:02d}"


def write_manifest(run_dir, args, calls, missing, projected, actual=None,
                   provider: str = PROVIDER, planned_utc: str | None = None) -> None:
    """Everything needed to say what this run was and what it cost, in one file.

    Written twice: once at plan time (so a dry run leaves a record too) and again
    after execution with the real spend. `projected` is what the free token count
    predicted; `actual` is what was billed. Keeping both is what makes it possible
    to check whether the projection can be trusted for the other countries.
    """
    docs = []
    seen = set()
    for c in calls:
        for m in c.manifest:
            if m["sha256"] not in seen:
                seen.add(m["sha256"])
                docs.append(m)

    manifest = {
        "run": run_dir.name,
        # Why this run happened, in the words of whoever launched it. Nothing
        # derives it and nothing validates it: the settings below say what the
        # run did, and no combination of them says what it was for. Top level
        # rather than under `settings` because it is not one.
        "note": getattr(args, "note", None),
        # When it was planned. `cost.started_utc` covers a run that executed, but
        # a dry run has no cost block at all — without this its only timestamp
        # would be the one in its folder name, and a name is a label.
        "planned_utc": planned_utc,
        "provider": provider,
        "country": args.country,
        # Every knob, written out in full — including the ones that came from
        # defaults, so the run is reproducible from this file alone.
        "settings": {
            "model": args.model,
            "mode": args.mode,
            # Only Anthropic is sent an effort level. Recording the flag's value
            # for a provider that never received it would make the manifest claim
            # a setting the run did not have, and the manifest is what the paper
            # cites as the run's configuration.
            "effort": args.effort if provider == PROVIDER else None,
            "effort_note": (None if provider == PROVIDER else
                            f"--effort {args.effort} accepted but not sent: the "
                            f"{provider} API takes no equivalent parameter"),
            "repeat": getattr(args, "repeat", 1),
            "only": args.only,
            "budget_usd": args.budget_usd,
            # Which credential the run billed against. Without it a run cannot be
            # reconciled against an invoice, and on a provider with a free tier it
            # cannot even be said whether the recorded spend was real money.
            # The name only — never the key itself, which must not reach a file
            # that gets committed.
            "api_key_var": getattr(args, "api_key_var", "ANTHROPIC_API_KEY"),
            "executed": bool(args.go),
            "max_tokens": {m: MAX_TOKENS[m] for m in args.mode},
            # Same reason as `effort`: only the Anthropic call sets this.
            "thinking": (getattr(args, "thinking", "adaptive")
                         if provider == PROVIDER else None),
        },
        "framework": {
            "source_file": framework_mod.load()["source_file"],
            # Distinct indicators assessed -- not the number of assessments, which
            # is this multiplied by shards and repeats.
            "n_indicators": len({i["indicator_id"] for c in calls for i in c.indicators}),
        },
        "corpus": {
            "n_documents": len(docs),
            "documents": docs,
        },
        "plan": {
            "n_calls": len(calls),
            "n_source_missing": len(missing),
            "projected_input_usd": round(projected["input"], 4),
            "projected_worst_case_usd": round(projected["worst"], 4),
        },
        "cost": actual,
        "command": " ".join(sys.argv),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def parse_response(msg):
    """(assessments, error, raw_text). The raw text is returned so the caller can
    persist it whether or not it parsed — see save_response()."""
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return json.loads(text).get("assessments", []), None, text
    except json.JSONDecodeError as e:
        return [], f"unparseable JSON: {e}", text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="argentina")
    ap.add_argument("--model", nargs="+", default=["claude-sonnet-5"])
    ap.add_argument("--mode", nargs="+", default=["subdimension"], choices=["subdimension", "indicator"])
    ap.add_argument("--only", nargs="+", help="restrict to these subdimension ids (e.g. d3)")
    ap.add_argument("--note", metavar="TEXT",
                    help="one line on what this run is for, kept in manifest.json and "
                         "listed in the country README. Optional, so a quick probe still "
                         "runs — but a run without one shows up in the index as unexplained")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="ask each unit of work N times and majority-vote the answers, "
                         "reporting a per-indicator stability score (default 1)")
    # Thinking is worth its tokens for a real assessment and worth nothing for a
    # schema check: the schema is validated when the request is admitted, before a
    # single token is generated. Turning it off makes the output cost predictable,
    # which is what a validation run needs.
    ap.add_argument("--thinking", default="adaptive", choices=["adaptive", "off"],
                    help="extended thinking: adaptive (default) or off. Off is for "
                         "runs whose purpose is not the quality of the answer")
    ap.add_argument("--max-output-tokens", type=int, default=None, metavar="N",
                    help=f"override the per-mode output cap (defaults: "
                         f"{', '.join(f'{k}={v}' for k, v in MAX_TOKENS.items())}). "
                         "The cap is what the budget guard prices as the worst case, "
                         "so lowering it is how a cheap run is made to fit.")
    ap.add_argument("--go", action="store_true", help="make billable calls (default is a free dry run)")
    ap.add_argument("--budget-usd", type=float, default=3.00, help="hard ceiling; aborts before exceeding")
    args = ap.parse_args()

    # A single override applies to every mode: the flag exists for one-off runs,
    # and per-mode caps would be a config file, not a flag.
    if args.max_output_tokens:
        for mode in MAX_TOKENS:
            MAX_TOKENS[mode] = args.max_output_tokens

    framework = framework_mod.load()
    docs = corpus_mod.load_docs(args.country)
    client = anthropic.Anthropic()

    # Shard first: a corpus whose single document exceeds the window cannot be
    # made to fit by call granularity, so the corpus is split and each indicator
    # asked once per shard. count_tokens is free, so this costs nothing.
    def count(text):
        return client.messages.count_tokens(
            model=args.model[0], messages=[{"role": "user", "content": text}]
        ).input_tokens

    code_sets = set()
    for sub in framework["subdimensions"]:
        if args.only and sub["subdimension_id"] not in args.only:
            continue
        avail = [i for i in sub["indicators"] if framework_mod.held_codes(i, docs)]
        if not avail:
            continue
        code_sets.add(tuple(sorted({c for i in avail
                                    for c in framework_mod.held_codes(i, docs)})))
        code_sets.update(framework_mod.held_codes(i, docs) for i in avail)

    shards, shard_counts = {}, {}
    for codes in sorted(code_sets):
        try:
            shards[codes] = corpus_mod.build_shards(args.country, codes, docs, count)
        except corpus_mod.MissingSource:
            continue
        shard_counts[codes] = len(shards[codes])

    over = {c: n for c, n in shard_counts.items() if n > 1}
    if over:
        print("\nsharded corpora (a single source exceeds the context window):")
        for codes, n in sorted(over.items()):
            print(f"  {'+'.join(codes):<6} -> {n} shards; "
                  f"each indicator is asked {n} times and the answers merged")

    if args.repeat > 1:
        print(f"\nreliability run: every unit of work is asked {args.repeat} times and "
              f"the answers majority-voted (repeats share the document cache)")

    calls, missing = plan(framework, args.country, args.model, args.mode, docs,
                          args.only, shard_counts, args.repeat)
    if not calls:
        sys.exit("Nothing to run.")
    measure(client, framework, args.country, calls, docs, shards)

    # One folder per run, named for what the run was. Nothing is ever overwritten:
    # a second run of the same settings gets its own timestamped folder, so the
    # repeat-run history stays on disk instead of being clobbered.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "outputs" / args.country / "runs" / run_name(args, stamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    tee = Tee(run_dir / "console.log")
    sys.stdout = tee
    try:
        _run(args, framework, client, calls, missing, run_dir, stamp)
    finally:
        sys.stdout = tee.stdout
        tee.close()
    print(f"run folder -> {run_dir.relative_to(ROOT)}\n")


def _run(args, framework, client, calls, missing, run_dir, stamp) -> None:
    out_dir = run_dir

    # --- projection -------------------------------------------------------
    print(f"\n{'PLAN':<30}{'calls':>7}{'fresh':>12}{'cache wr':>12}{'cache rd':>12}{'input $':>10}{'max out $':>11}")
    print("-" * 94)
    total_lo = total_hi = 0.0
    for (model, mode), r in sorted(project(calls).items()):
        cin = cost_usd(model, input_tokens=r["fresh"], cache_creation_input_tokens=r["write"],
                       cache_read_input_tokens=r["read"])
        cout = r["calls"] * MAX_TOKENS[mode] * price_of(model).output_per_mtok / 1e6
        total_lo += cin
        total_hi += cin + cout
        print(f"{model + ' / ' + mode:<30}{r['calls']:>7}{r['fresh']:>12,}{r['write']:>12,}"
              f"{r['read']:>12,}{cin:>10.3f}{cout:>11.3f}")
    print("-" * 94)
    print(f"{'input (exact, measured)':<30}{'':>7}{'':>12}{'':>12}{'':>12}{total_lo:>10.3f}")
    print(f"{'worst case incl. max output':<30}{'':>7}{'':>12}{'':>12}{'':>12}{total_hi:>10.3f}")
    if missing:
        by_code = {}
        for m in missing:
            by_code[m["source_code"]] = by_code.get(m["source_code"], 0) + 1
        note = ", ".join(f"{n} routed to [{c}]" for c, n in sorted(by_code.items()))
        print(f"\nsource_missing (no call made): {note}")

    write_appendix(out_dir, framework, args, calls, missing)
    print(f"prompts appendix -> {(out_dir / 'prompts_appendix.md').relative_to(ROOT)}")

    projected = {"input": total_lo, "worst": total_hi}
    # Write the manifest before spending anything, so a run that dies mid-flight
    # still leaves a record of what it was trying to do.
    write_manifest(run_dir, args, calls, missing, projected, planned_utc=stamp)

    if not args.go:
        print("\nDry run — nothing was billed. Re-run with --go to execute.\n")
        return

    # --- execution --------------------------------------------------------
    log = out_dir / "raw.jsonl"
    spent = 0.0
    stopped_early = False
    n_calls_made = 0

    with log.open("w", encoding="utf-8") as fh:
        for rec in missing:
            fh.write(json.dumps({**rec, "run_timestamp": stamp, "call": False}, ensure_ascii=False) + "\n")

        shard_records = []
        print(f"\nrunning {len(calls)} calls, budget ${args.budget_usd:.2f}\n")
        for i, c in enumerate(calls, 1):
            worst = cost_usd(c.model, input_tokens=c.input_tokens) + (
                MAX_TOKENS[c.mode] * price_of(c.model).output_per_mtok / 1e6
            )
            if spent + worst > args.budget_usd:
                print(f"  STOP at call {i}/{len(calls)}: ${spent:.3f} spent, next call could "
                      f"reach ${spent + worst:.3f} > budget ${args.budget_usd:.2f}")
                stopped_early = True
                break

            system, messages = P.build_request(
                dimension=framework["dimension"], subdimension=c.subdim,
                indicators=c.indicators, doc_blocks=c.doc_blocks,
                manifest=c.manifest, breakpoints=c.breakpoints,
            )
            t0 = time.time()
            msg = client.messages.create(
                model=c.model,
                max_tokens=MAX_TOKENS[c.mode],
                system=system,
                messages=messages,
                thinking={"type": "adaptive"} if args.thinking == "adaptive"
                         else {"type": "disabled"},
                output_config={
                    "effort": args.effort,
                    "format": {"type": "json_schema",
                               "schema": P.output_schema(c.indicators,
                                                         complete=call_is_complete(c))},
                },
            )
            dt = time.time() - t0
            u = msg.usage
            call_cost = cost_from_usage(c.model, u)
            spent += call_cost
            n_calls_made += 1
            assessments, err, raw_text = parse_response(msg)
            if msg.stop_reason == "refusal":
                err = f"refusal: {getattr(msg.stop_details, 'category', None)}"
            # Written before the rows, so a crash while building them still leaves
            # the response on disk.
            response_file = save_response(out_dir, c, raw_text, err is None)

            by_id = {a["indicator_id"]: a for a in assessments}
            for ind in c.indicators:
                a = by_id.get(ind["indicator_id"], {})
                answer, a_err = (P.read_assessment(ind, a, require_quotes=has_all_sources(c, ind))
                                 if a
                                 else (P.empty_assessment(ind), "no assessment returned"))
                rec = {
                    "country": args.country, "model": c.model, "mode": c.mode,
                    "subdimension_id": c.subdim["subdimension_id"],
                    "indicator_id": ind["indicator_id"], "source_code": ind["source_code"],
                    **P.assessment_columns(answer),
                    "reasoning": answer["reasoning"] or err or "no assessment returned",
                    "call": True, "cache_key": c.cache_key,
                    "cached_codes": "+".join(c.cached_codes),
                    "input_tokens": u.input_tokens,
                    "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                    "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                    "output_tokens": u.output_tokens,
                    "n_indicators_in_call": len(c.indicators),
                    "cost_usd": call_cost, "latency_s": round(dt, 2),
                    "response_file": response_file,
                    "stop_reason": msg.stop_reason, "effort": args.effort,
                    "run_timestamp": stamp,
                    "error": "; ".join(x for x in (err, a_err) if x),
                    "shard": c.shard, "n_shards": c.n_shards,
                    "rep": c.rep, "n_reps": c.n_reps,
                }
                shard_records.append(rec)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

            cr = getattr(u, "cache_read_input_tokens", 0) or 0
            cw = getattr(u, "cache_creation_input_tokens", 0) or 0
            print(f"  [{i:>2}/{len(calls)}] {c.model.split('-')[1]:<7} {c.mode[:4]} {c.label:<7} "
                  f"in={u.input_tokens:<6,} wr={cw:<7,} rd={cr:<7,} out={u.output_tokens:<5,} "
                  f"${call_cost:.4f}  cum ${spent:.3f}  {dt:>5.1f}s{'  ' + err if err else ''}")

        # The shard rows above are the record of what was actually billed; the
        # merged rows are the record of what was concluded. Both stay in the log so
        # an answer can always be traced back to the shard that produced its quote.
        # Shards fold first (many documents -> one answer per rep), then reps
        # (many samples -> one answer). Doing it the other way round would vote
        # across slices of the corpus, which is not what either fold means.
        by_shard = merge_shards(shard_records)
        merged = [r for r in by_shard if r.get("n_shards", 1) > 1]
        for r in merged:
            fh.write(json.dumps({**r, "call": False, "merged": True},
                                ensure_ascii=False) + "\n")
        if merged:
            print(f"\nmerged {len(shard_records)} shard assessments into "
                  f"{len(merged)} answers")
            split = [r for r in merged
                     if len({v.split(":", 1)[1] for v in r.get("shard_values", "").split("|")
                             if ":" in v}) > 1]
            for r in split:
                print(f"    {r['indicator_id']:<8} {r['shard_values']} -> "
                      f"{answer_str(r)}")

        voted = [r for r in merge_reps(by_shard) if r.get("n_reps", 1) > 1]
        for r in voted:
            fh.write(json.dumps({**r, "call": False, "merged": True, "rep_merged": True},
                                ensure_ascii=False) + "\n")
        if voted:
            # stability is null for record: free text is not voted, so it is not
            # part of the reliability figure; its text similarity is listed apart.
            measured = [r for r in voted if r.get("stability") is not None]
            unstable = sorted((r for r in measured if r["stability"] < 1.0),
                              key=lambda r: r["stability"])
            if measured:
                mean_stab = sum(r["stability"] for r in measured) / len(measured)
                print(f"\nvoted {len(by_shard)} assessments into {len(voted)} answers over "
                      f"{args.repeat} repeats — mean stability {mean_stab:.3f} over the "
                      f"{len(measured)} voted, {len(measured) - len(unstable)}/{len(measured)} "
                      f"unanimous ({len(voted) - len(measured)} not voted)")
            for r in unstable:
                tie = "  TIE" if r["tie"] else ""
                print(f"    {r['indicator_id']:<8} {r['model'].split('-')[1]:<7} "
                      f"{r['mode'][:4]}  {r['rep_values']} -> {answer_str(r)} "
                      f"({r['stability']:.2f}){tie}")
            print_text_similarity(voted)

    actual = {
        "spent_usd": round(spent, 4),
        "budget_usd": args.budget_usd,
        "stopped_early": stopped_early,
        "n_calls_made": n_calls_made,
        "n_calls_planned": len(calls),
        "input_tokens": sum(r["input_tokens"] for r in shard_records),
        "cache_read_input_tokens": sum(r["cache_read_input_tokens"] for r in shard_records),
        "cache_creation_input_tokens": sum(
            r["cache_creation_input_tokens"] for r in shard_records),
        "output_tokens": sum(r["output_tokens"] for r in shard_records),
        "projection_error_pct": (
            round(100 * (spent - projected["input"]) / projected["input"], 1)
            if projected["input"] else None
        ),
        "started_utc": stamp,
        "finished_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    }
    write_manifest(run_dir, args, calls, missing, projected, actual, planned_utc=stamp)

    print()
    print_uncited(shard_records)
    print(f"\nspent ${spent:.4f} of ${args.budget_usd:.2f} budget")
    if stopped_early:
        print(f"  INCOMPLETE: {n_calls_made} of {len(calls)} calls were made")
    print(f"raw log  -> {log.relative_to(ROOT)}")
    print(f"manifest -> {(run_dir / 'manifest.json').relative_to(ROOT)}")


def schema_appendix_lines(framework) -> list[str]:
    """The response schema section of the prompts appendix.

    There is no single schema any more: a call declares only the answer fields
    the indicator types it covers actually need. So the appendix documents it the
    way it is built — one schema per indicator type, over a real indicator of
    that type, plus the mixed case a subdimension call produces.
    """
    all_inds = [i for s in framework["subdimensions"] for i in s["indicators"]]
    L = [
        "The schema is built per call, from the indicator types that call covers: "
        "`indicator_id`, `quotes` and `reasoning` are always required, and each "
        "type adds its own answer field after them. Field order is part of the "
        "contract — the evidence and the reasoning are written before the answer.",
        "",
    ]
    for kind in ("criterion", "criterion_list", "categorical", "record"):
        one = next((i for i in all_inds if i.get("type") == kind), None)
        if not one:
            continue
        L += [f"**{kind}** (as sent for `{one['indicator_id']}`)", "",
              "```json", json.dumps(P.output_schema([one]), indent=2), "```", ""]

    # A subdimension call covers several types at once, so its item schema is the
    # union of their answer fields; which one an indicator owes is enforced when
    # the response is read, not by the schema.
    mixed = max((s["indicators"] for s in framework["subdimensions"]),
                key=lambda inds: len({i.get("type") for i in inds}), default=[])
    if len({i.get("type") for i in mixed}) > 1:
        L += ["**A mixed subdimension call** covers several types at once, so its "
              "item schema is the union of their answer fields:", "",
              "```json", json.dumps(P.output_schema(mixed), indent=2), "```", ""]
    return L


def save_response(out_dir, call, text: str, parsed_ok: bool) -> str:
    """Write one call's raw response to disk and return its path, relative to the run.

    Kept as a file per call rather than a column on every row: one response covers
    every indicator in the call, so storing it inline would repeat the same
    kilobytes once per indicator.

    Saved whether or not the JSON parsed, and this is the whole point. A response
    that fails to parse is the one worth keeping — it is the only record of what
    the model actually emitted, and without it a truncation or a field-order
    violation can only be inferred from the error message. Unparseable responses
    get a `.txt` extension so nothing downstream tries to json.load them.
    """
    responses = out_dir / "responses"
    responses.mkdir(exist_ok=True)
    stem = f"{call.model}__{call.mode}__{call.label}"
    if call.n_reps > 1:
        stem += f"__rep{call.rep}"
    stem = re.sub(r"[^A-Za-z0-9_.=-]", "-", stem)
    path = responses / f"{stem}.{'json' if parsed_ok else 'txt'}"
    path.write_text(text or "", encoding="utf-8")
    return str(path.relative_to(out_dir))


def print_uncited(records) -> None:
    """Count the answers whose reasoning cites the documents but carries no quotes."""
    flagged = [r for r in records if r.get("uncited_refs")]
    answered = [r for r in records if r.get("field_order")]
    print(f"uncited reasoning: {len(flagged)} of {len(answered)} answers name document "
          f"passages with an empty `quotes` field")
    for r in flagged:
        print(f"    {r['indicator_id']:<8} rep {r.get('rep', 1)}  shard {r.get('shard', 1)}  "
              f"{r['uncited_refs'][:120]}")


def answer_str(rec) -> str:
    """One row's answer, short enough for a console line."""
    kind = rec.get("type", "criterion")
    if kind == "criterion":
        v = rec.get("value")
        return "-" if v is None else ("true" if v else "false")
    if kind == "criterion_list":
        n = rec.get("n_elements_true")
        return "-" if n is None else f"{n}/{rec.get('n_elements')}"
    if kind == "categorical":
        return rec.get("selected") or "(none)"
    return "found" if (rec.get("extracted_text") or rec.get("fields")) else "(none)"


def _json_col(value):
    """A JSON column of the run log, back as an object."""
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def strongest_exclusion(kinds) -> str | None:
    """Fold exclusion_type across shards: explicit, then treated_as_other, then
    not_mentioned. None when no shard reported one."""
    found = {k for k in kinds if k in P.EXCLUSION_TYPES}
    return next((k for k in P.EXCLUSION_TYPES if k in found), None)


def merge_shards(records):
    """Fold the per-shard records of one indicator into one answer.

    Sharding splits the *corpus*, not the indicator list: every shard is asked
    every indicator of the call, over a different slice of the documents. So each
    indicator does come back once per shard, and the shards have to be folded.

    With booleans the fold is a disjunction, not a ranking. A shard that never
    saw the relevant chapter answers false because it found nothing there, which
    is not a claim that the instrument lacks the feature; a shard that did find
    the passage answers true and carries the evidence. So true wins, per
    indicator and, for a criterion_list, per element. `selected` and the record
    text cannot be OR-ed, so the shard that actually found something supplies
    them, and a genuine disagreement between shards is reported rather than
    picked between.
    """
    out, groups = [], {}
    for r in records:
        if r.get("n_shards", 1) <= 1:
            out.append(r)
            continue
        # `rep` is part of the key: shards fold within a rep, never across them.
        # Merging shard 1 of rep 1 with shard 2 of rep 2 would silently turn a
        # reliability run into a single blended answer.
        groups.setdefault(
            (r["country"], r["model"], r["mode"], r["indicator_id"], r.get("rep", 1)), []
        ).append(r)

    for key, shard_recs in groups.items():
        shard_recs.sort(key=lambda r: r["shard"])
        n = shard_recs[0]["n_shards"]
        searched = sorted(r["shard"] for r in shard_recs)
        kind = shard_recs[0].get("type", "criterion")
        problems = []

        # The witness is the shard whose evidence supports the merged answer: the
        # first that found something, so the quotes on file are the quotes the
        # answer rests on.
        positive = [r for r in shard_recs if r.get("value") is True
                    or (r.get("n_elements_true") or 0) > 0
                    or (r.get("selected") or "").strip()
                    or (r.get("extracted_text") or "").strip()
                    or _json_col(r.get("fields"))]
        witness = positive[0] if positive else shard_recs[0]

        merged = {
            **witness,
            "shard": 0,
            "n_shards": n,
            "merged_from_shards": len(shard_recs),
            "cost_usd": sum(r["cost_usd"] for r in shard_recs),
            "input_tokens": sum(r["input_tokens"] for r in shard_recs),
            "output_tokens": sum(r["output_tokens"] for r in shard_recs),
            "latency_s": round(sum(r["latency_s"] for r in shard_recs), 2),
        }

        # All the evidence, from every shard that found any — the merged answer
        # rests on the union, not on one shard's share of it.
        quotes = [q for r in shard_recs for q in (_json_col(r.get("quotes")) or [])]
        merged["quotes"] = json.dumps(quotes, ensure_ascii=False) if quotes else ""
        merged["n_quotes"] = len(quotes)

        if kind == "criterion":
            values = [r.get("value") for r in shard_recs if isinstance(r.get("value"), bool)]
            merged["value"] = any(values) if values else None
            merged["shard_values"] = "|".join(
                f"{r['shard']}:{r.get('value')}" for r in shard_recs)
            # Only a false carries exclusion_type. Across shards the strongest
            # finding wins, for the same reason true does: a shard that never saw
            # the passage reports `not_mentioned` from not having seen it.
            merged["exclusion_type"] = (
                strongest_exclusion(r.get("exclusion_type") for r in shard_recs)
                if merged["value"] is False else None)

        elif kind == "criterion_list":
            per_shard = [_json_col(r.get("elements")) for r in shard_recs]
            names = [k for d in per_shard for k in d]
            elements = {k: any(d.get(k) is True for d in per_shard)
                        for k in dict.fromkeys(names)}
            merged["elements"] = json.dumps(elements, ensure_ascii=False) if elements else ""
            merged["n_elements"] = len(elements)
            merged["n_elements_true"] = sum(elements.values()) if elements else None
            merged["shard_values"] = "|".join(
                f"{r['shard']}:{r.get('n_elements_true')}/{r.get('n_elements')}"
                for r in shard_recs)

        elif kind == "categorical":
            picks = {(r.get("selected") or "").strip()
                     for r in shard_recs if (r.get("selected") or "").strip()}
            # What each shard chose stays in shard_values. Shards that chose
            # different options leave the answer unresolved, as a tied vote does:
            # there is no ground for preferring one, alphabetical order least.
            merged["shard_values"] = "|".join(
                f"{r['shard']}:{r.get('selected')}" for r in shard_recs)
            if len(picks) > 1:
                merged["selected"] = None
                merged["tie"] = True
                problems.append(
                    f"shards disagreed on `selected` ({sorted(picks)}); left unresolved")
            else:
                merged["selected"] = next(iter(picks), "")

        elif kind == "record":
            declared = _json_col(witness.get("fields"))
            if declared:
                # Per field, the first shard that transcribed anything for it.
                fields = {}
                for f in declared:
                    found = next((_json_col(r.get("fields")).get(f) for r in shard_recs
                                  if str(_json_col(r.get("fields")).get(f, "")).strip()), "")
                    fields[f] = found
                merged["fields"] = json.dumps(fields, ensure_ascii=False)
            texts = [t for t in ((r.get("extracted_text") or "").strip()
                                 for r in shard_recs) if t]
            if texts:
                # A record can legitimately be split across shards (a category
                # list running over a page break), so keep every distinct piece.
                merged["extracted_text"] = "\n---\n".join(dict.fromkeys(texts))
            merged["shard_values"] = "|".join(
                f"{r['shard']}:{'found' if (r.get('extracted_text') or _json_col(r.get('fields'))) else 'none'}"
                for r in shard_recs)

        # A shard that never ran (budget stop, refusal) makes a negative unsafe:
        # part of the corpus was never searched, so absence of evidence is not
        # evidence of absence. Say so rather than reporting a clean false.
        answered_negative = (merged.get("value") is False
                             or merged.get("n_elements_true") == 0
                             or (kind == "categorical" and not merged.get("selected"))
                             or (kind == "record" and not merged.get("extracted_text")
                                 and not _json_col(merged.get("fields"))))
        if len(shard_recs) < n and answered_negative:
            problems.append(
                f"only shards {searched} of {n} were assessed, so this negative "
                f"cannot be supported: the rest of the corpus was never searched")
            merged["value"] = None
            merged["exclusion_type"] = None
            merged["n_elements_true"] = None

        if problems:
            merged["error"] = "; ".join(
                x for x in ([merged.get("error", "")] + problems) if x)
        out.append(merged)
    return out


def print_text_similarity(voted) -> None:
    """List each record indicator's mean text similarity across repeats. No
    threshold: the distribution is to be read before one is chosen."""
    texted = [r for r in voted if r.get("text_similarity") is not None]
    if texted:
        print(f"record text similarity (mean pairwise word-set Jaccard, no threshold):")
    for r in sorted(texted, key=lambda r: r["text_similarity"]):
        print(f"    {r['indicator_id']:<8} {r['text_similarity']:.3f}  ({r['rep_similarity']})")


def record_text(rec) -> str | None:
    """A record answer as one string: `extracted_text`, or the declared fields
    joined. None when the rep returned no answer at all (a failed call)."""
    fields = _json_col(rec.get("fields"))
    if fields:
        return "\n".join(str(v) for v in fields.values())
    txt = rec.get("extracted_text")
    return txt if isinstance(txt, str) else None


def text_similarity(a: frozenset, b: frozenset) -> float:
    """Jaccard over word sets, as the triage measures documents. Two empty texts
    are the same answer -- both found nothing -- so they score 1, not 0."""
    if not a and not b:
        return 1.0
    return jaccard(a, b)


def merge_reps(records):
    """Fold the repeats of one indicator into a majority answer plus a stability score.

    Unlike shards, repeats are not different evidence — they are the same question
    asked of the same documents, so disagreement between them is the instrument's
    own noise and must not be resolved by taking whichever answer is more
    favourable. That would bias every indicator upward: one lucky sample out of
    three would be enough to carry it. Majority vote is the honest fold, and
    `stability` is what the reliability run actually exists to report.

    A vote needs a countable answer, so it is defined only where one exists:

    criterion       vote on `value`; stability is the winning share
    criterion_list  vote per element; stability is the mean winning share over
                    the elements, which is the right unit because each element
                    was assessed independently
    categorical     vote on `selected` (an empty selection is an answer and
                    votes); stability is the winning share, a tie unresolved
    record          no vote — free text cannot be counted. Every rep's text is
                    kept, the rep closest to the others by word-set Jaccard is
                    put forward, and the mean pairwise similarity goes to
                    `text_similarity`, not `stability`: it is not a vote share

    For records, and for any indicator whose repeats returned no usable answer,
    `stability` is null. Null is the honest value: not measured, as against
    measured and perfect.

    A tie on a criterion (2-2) leaves `value` null and sets `tie=True`. There is
    no majority, and picking one side would hide exactly the instability the run
    exists to measure.
    """
    out, groups = [], {}
    for r in records:
        if r.get("n_reps", 1) <= 1:
            out.append(r)
            continue
        groups.setdefault(
            (r["country"], r["model"], r["mode"], r["indicator_id"]), []
        ).append(r)

    for key, reps in groups.items():
        reps.sort(key=lambda r: r["rep"])
        kind = reps[0].get("type", "criterion")
        n_expected = reps[0].get("n_reps", len(reps))
        witness, stability, tie = reps[0], None, False
        answer, rep_values = {}, ""
        rep_texts, rep_similarity, text_sim = "", "", None
        exclusion_stability, exclusion_tie, exclusion_values = None, False, ""

        if kind == "criterion":
            votes = [r.get("value") for r in reps if isinstance(r.get("value"), bool)]
            rep_values = "|".join(f"{r['rep']}:{r.get('value')}" for r in reps)
            if votes:
                n_true = sum(votes)
                top = max(n_true, len(votes) - n_true)
                stability = round(top / len(votes), 3)
                tie = n_true * 2 == len(votes)
                winner = None if tie else n_true * 2 > len(votes)
                answer["value"] = winner
                # How the negative is negative gets its own vote, among the reps
                # that answered false -- the only ones that carry it. Plurality
                # with a unique top; a tie is left unresolved, as for `value`.
                if winner is False:
                    kinds = [(r["rep"], r.get("exclusion_type")) for r in reps
                             if r.get("value") is False]
                    ex_votes = [k for _, k in kinds if k in P.EXCLUSION_TYPES]
                    exclusion_values = "|".join(f"{n}:{k}" for n, k in kinds)
                    if ex_votes:
                        counts = {k: ex_votes.count(k) for k in dict.fromkeys(ex_votes)}
                        top_n = max(counts.values())
                        leaders = [k for k, c in counts.items() if c == top_n]
                        exclusion_tie = len(leaders) > 1
                        answer["exclusion_type"] = None if exclusion_tie else leaders[0]
                        exclusion_stability = round(top_n / len(ex_votes), 3)
                    else:
                        answer["exclusion_type"] = None
                else:
                    answer["exclusion_type"] = None
                # The evidence on file must be the evidence for the answer on
                # file, so the witness is a rep that voted with the majority --
                # on exclusion_type too, where there is one.
                witness = (next((r for r in reps if r.get("value") is winner
                                 and r.get("exclusion_type") == answer["exclusion_type"]), None)
                           or next((r for r in reps if r.get("value") is winner), reps[0]))

        elif kind == "criterion_list":
            per_rep = [_json_col(r.get("elements")) for r in reps]
            names = list(dict.fromkeys(k for d in per_rep for k in d))
            elements, shares = {}, []
            for k in names:
                votes = [d[k] for d in per_rep if isinstance(d.get(k), bool)]
                if not votes:
                    continue
                n_true = sum(votes)
                shares.append(max(n_true, len(votes) - n_true) / len(votes))
                # A tied element is left out of the count rather than guessed at;
                # n_elements_true then no longer sums to n_elements, which is the
                # visible sign that one element did not settle.
                if n_true * 2 != len(votes):
                    elements[k] = n_true * 2 > len(votes)
                else:
                    tie = True
            if shares:
                stability = round(sum(shares) / len(shares), 3)
            answer["elements"] = json.dumps(elements, ensure_ascii=False) if elements else ""
            answer["n_elements"] = len(names)
            answer["n_elements_true"] = sum(elements.values()) if elements else None
            rep_values = "|".join(
                f"{r['rep']}:{r.get('n_elements_true')}/{r.get('n_elements')}" for r in reps)
            witness = next((r for r in reps
                            if _json_col(r.get("elements")) == elements), reps[0])

        elif kind == "categorical":
            rep_values = "|".join(f"{r['rep']}:{r.get('selected')}" for r in reps)
            # An empty selection is an answer ("none of the options applies"), so
            # it votes; a missing one (a failed call) does not.
            votes = [r["selected"].strip() for r in reps if isinstance(r.get("selected"), str)]
            if votes:
                counts = {v: votes.count(v) for v in dict.fromkeys(votes)}
                top = max(counts.values())
                leaders = [v for v, c in counts.items() if c == top]
                tie = len(leaders) > 1
                stability = round(top / len(votes), 3)
                answer["selected"] = None if tie else leaders[0]
                if not tie:
                    witness = next(r for r in reps
                                   if isinstance(r.get("selected"), str)
                                   and r["selected"].strip() == leaders[0])

        elif kind == "record":
            rep_values = "|".join(
                f"{r['rep']}:{r.get('n_quotes')}q" for r in reps)
            # Free text cannot be voted. Keep every rep's text, measure how alike
            # they are with the triage's word-set Jaccard, and put forward the rep
            # closest to the others. No threshold is applied here: what counts as
            # an unstable transcription is to be read off a real run first.
            texts = {r["rep"]: record_text(r) for r in reps if record_text(r) is not None}
            rep_texts = json.dumps([{"rep": n, "text": t} for n, t in texts.items()],
                                   ensure_ascii=False)
            if len(texts) >= 2:
                words = {n: words_of(t) for n, t in texts.items()}
                pairs = {(a, b): text_similarity(words[a], words[b])
                         for i, a in enumerate(words) for b in list(words)[i + 1:]}
                rep_similarity = "|".join(f"{a}-{b}:{v:.3f}" for (a, b), v in pairs.items())
                text_sim = round(sum(pairs.values()) / len(pairs), 3)
                closeness = {n: sum(v for (a, b), v in pairs.items() if n in (a, b))
                             for n in words}
                best = max(closeness, key=lambda n: (closeness[n], -n))
                witness = next(r for r in reps if r["rep"] == best)

        merged = {
            **witness,
            **answer,
            "rep": 0,
            "n_reps": n_expected,
            "merged_from_reps": len(reps),
            "rep_values": rep_values,
            "stability": stability,
            "tie": tie,
            # The same three figures for exclusion_type, which is voted separately:
            # a unanimous false can still split on how the text is negative.
            "exclusion_values": exclusion_values,
            "exclusion_stability": exclusion_stability,
            "exclusion_tie": exclusion_tie,
            # record only: every rep's text, the pairwise word-set Jaccard, and its
            # mean -- the record's stability, kept out of `stability` because a
            # text similarity and a vote share are not on the same scale.
            "rep_texts": rep_texts,
            "rep_similarity": rep_similarity,
            "text_similarity": text_sim,
            "cost_usd": sum(r["cost_usd"] for r in reps),
            "input_tokens": sum(r["input_tokens"] for r in reps),
            "output_tokens": sum(r["output_tokens"] for r in reps),
            "latency_s": round(sum(r["latency_s"] for r in reps), 2),
        }
        # A budget stop can leave an indicator with fewer reps than asked for. One
        # sample is not a reliability measurement, so say so rather than reporting
        # a stability of 1.000 that means nothing.
        if len(reps) < n_expected:
            merged["reasoning"] = (
                f"Only {len(reps)} of {n_expected} repeats were run, so the stability "
                f"figure is not comparable with fully repeated indicators. "
                f"{merged['reasoning']}"
            )
        out.append(merged)
    return out


def write_appendix(out_dir, framework, args, calls, missing) -> None:
    """Methodological appendix: the verbatim prompt behind every indicator."""
    from prompts import CONSTRAINTS, INPUTS, METHOD, ROLE

    by_indicator = {}
    for c in calls:
        for ind in c.indicators:
            by_indicator.setdefault((c.mode, ind["indicator_id"]), c)

    L = [
        f"# Prompt appendix — {args.country.title()}",
        "",
        f"Framework: **{framework['dimension']}**, parsed from "
        f"`{framework['source_file']}` (the analytical framework is the single source of truth; "
        "this file is generated from it, never hand-edited).",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"models: {', '.join(args.model)} · modes: {', '.join(args.mode)} · "
        f"effort: `{args.effort}` · thinking: adaptive · "
        f"max_tokens: {', '.join(f'{m}={MAX_TOKENS[m]}' for m in args.mode)}",
        "",
        "Every call is a single user turn against the Messages API with a structured-output "
        "schema (below). No conversation state carries between indicators: each assessment is "
        "independent, and the only evidence available to the model is the source documents "
        "listed in each entry.",
        "",
        "## 1. Shared scaffold (system prompt)",
        "",
        "Lifted verbatim from the `scaffold` object in "
        f"`{framework['source_file']}`. Role and Constraints are identical, byte for byte, in "
        "every call. Inputs is identical except for its `{documents}` slot, which is replaced "
        "with the documents actually supplied to that call — the same list shown per entry in "
        "section 4.",
        "",
        "### Role", "", "```text", ROLE, "```", "",
        "### Inputs (template)", "", "```text", INPUTS, "```", "",
        "### Constraints", "", "```text", CONSTRAINTS, "```", "",
        "## 2. Method block", "",
        "Appended to every task block, after the indicator list.", "",
        "```text", METHOD, "```", "",
        "## 3. Required output schema", "",
        *schema_appendix_lines(framework),
        "## 4. Per-indicator task blocks", "",
        "The user turn is the source documents (verbatim extracted text, listed by file below) "
        "followed by the task block shown for each entry. Document text is not reproduced here "
        "— it runs to tens of thousands of tokens — but each extraction is stored under "
        "`data/processed/text/` and identified by SHA-256 so any assessment can be reproduced "
        "exactly.", "",
    ]

    for sub in framework["subdimensions"]:
        L += [f"### {sub['tag']} — {sub['title']}", "",
              f"*Variable:* {sub['variable']}", ""]
        for ind in sub["indicators"]:
            L += [f"#### `{ind['indicator_id']}` · source `{ind['source_code']}`", "",
                  f"> {ind['text']}", ""]
            miss = next((m for m in missing if m["indicator_id"] == ind["indicator_id"]), None)
            if miss:
                L += [f"**Not sent to the model — `source_missing`.** {miss['reasoning']}", ""]
                continue
            for mode in args.mode:
                c = by_indicator.get((mode, ind["indicator_id"]))
                if not c:
                    continue
                L += [f"**Mode `{mode}`** — assessed "
                      + (f"together with the other indicators of `{sub['subdimension_id']}` in one call"
                         if mode == "subdimension" else "in a call of its own")
                      + f". Evidence corpus `{c.cache_key}` ({c.input_tokens:,} input tokens).", "",
                      "Documents supplied:", ""]
                L += [f"- `{m['doc']}` → `{m['text_file']}` — {m['chars']:,} chars, "
                      f"sha256 `{m['sha256'][:16]}…`" for m in c.manifest]
                L += ["", "`{documents}` resolved to:", "", "```text",
                      P.documents_supplied(c.manifest, framework["source_codes"]),
                      "```", ""]
                L += ["Task block:", "", "```text",
                      P.dimension_block(framework["dimension"], c.subdim, c.indicators),
                      "```", ""]

    (out_dir / "prompts_appendix.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
