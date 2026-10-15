"""Evaluate survey instruments using Google Gemini models.

Two axes:
  --mode subdimension   one call per subdimension (the whole indicator group at once)
  --mode indicator      one call per indicator (each call loads only its own source)

Dry run is the default and costs nothing: count_tokens is a free endpoint, so the
exact input cost is known before any billable call is made. Add --go to spend.

    python scripts/llm/run_eval_gemini.py --country argentina --mode subdimension indicator \
        --model gemini-3.6-flash gemini-3.1-pro-preview
    python scripts/llm/run_eval_gemini.py --country argentina --mode subdimension \
        --model gemini-3.6-flash --go --budget-usd 3.00
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.error

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus as corpus_mod
from cost import cost_from_usage, cost_usd, price_of
import framework as framework_mod
import prompts as P
import run_eval

ROOT = Path(__file__).resolve().parents[2]

MAX_TOKENS = {"subdimension": 8000, "indicator": 4000}


def max_out(mode: str, override: int | None = None) -> int:
    """The output ceiling for one call: the mode default unless --max-output-tokens
    overrides it. Thinking tokens are billed out of this same allowance, so the
    figure is not the length of the expected answer."""
    return override or MAX_TOKENS[mode]

# What goes in the `effort` column of every row this runner writes. The Anthropic
# runner sends an effort level and records it; this one has nothing to send, and a
# row claiming `effort: medium` would describe a setting that never reached the
# API. None is the honest value, and it reads as an empty cell in the CSV.
EFFORT_NOT_SENT = None


# Every retry is a real request against the free-tier daily ceiling, so a
# generous cap turns one slow call into five spent requests. On 2026-09-02 that
# cascade emptied three keys in a morning: a read timeout on a large shard was
# retried until the day's quota was gone, and Mexico and Spain came back with
# zero usable rows. Two attempts is enough to ride out a transient 503 without
# letting a persistently slow call consume the day.
MAX_RETRIES = 2

# Free-tier input-token ceiling per minute, per model. Exceeding it costs nothing
# but wastes wall-clock on rejected requests, so the runner paces itself to stay
# under it. Raise with --tokens-per-minute on a paid key (paid tiers are far
# higher); the ceiling only ever delays calls, it never drops them.
FREE_TIER_INPUT_TPM = 250_000

# The rest of the free-tier allowance for gemini-3.6-flash, verified in the
# console. On the free tier these, not a dollar figure, are what a run can run
# out of: requests are the scarce resource and they refill on a clock. RPD is a
# hard stop for the day -- there is no way to buy past it without moving the key
# to a paid project.
FREE_TIER_RPM = 5
FREE_TIER_RPD = 20


def retry_delay_seconds(err_body: str, default: float = 30.0) -> float:
    """Seconds to wait after a 429, as stated by the API itself.

    Google returns a RetryInfo block ("retryDelay": "19s") and repeats the figure
    in the message. Obeying it beats guessing: too short and the retry is rejected
    again, too long and the run crawls.
    """
    try:
        err = json.loads(err_body).get("error", {})
        for d in err.get("details", []):
            delay = d.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                return float(delay[:-1]) + 1.0  # +1s of slack against clock skew
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    m = re.search(r"retry in ([\d.]+)s", err_body)
    return float(m.group(1)) + 1.0 if m else default


# Google meters at request admission, and its clock is not ours. Leaving headroom
# is much cheaper than a rejected 100k-token request, which costs a full minute.
PACER_SAFETY = 0.85


class RatePacer:
    """Keep input tokens under a per-minute ceiling by waiting before the call.

    A sliding window of the last 60 seconds of input tokens. When the next call
    would push the window over the limit, sleep until enough of it has aged out.

    Two things this has to get right, both learned the hard way:

    - **Record at request time, not on response.** Google meters when it admits
      the request; a call that takes 25s would otherwise be logged 25s late, and
      the window would think it had aged out while Google still counted it.
    - **Record rejected attempts too.** A 429'd request appears to count against
      the meter. Not recording retries lets the pacer believe there is room while
      the bucket is still full, so it retries into a wall until it runs out of
      attempts -- which is exactly how three retries became five failures.

    A single call larger than the ceiling can never be admitted; the caller is
    told rather than left to spin.
    """

    def __init__(self, tokens_per_minute: int):
        self.limit = int(tokens_per_minute * PACER_SAFETY) if tokens_per_minute else 0
        self.hard_limit = tokens_per_minute
        self.window: list[tuple[float, int]] = []

    def _used(self, now: float) -> int:
        self.window = [(t, n) for t, n in self.window if now - t < 60.0]
        return sum(n for _, n in self.window)

    def wait_for(self, tokens: int) -> None:
        """Block until `tokens` can be sent, then charge them to the window."""
        if not self.limit:
            return
        if tokens > self.hard_limit:
            print(f"      WARNING: this call is {tokens:,} tokens, above the "
                  f"{self.hard_limit:,}/min ceiling — it cannot succeed on this tier")
            self.record(tokens)
            return
        while True:
            now = time.time()
            used = self._used(now)
            if used + tokens <= self.limit:
                self.record(tokens)  # charge on admission, as Google does
                return
            # Wait for the oldest entry to leave the window, then re-check.
            sleep = 60.0 - (now - self.window[0][0]) + 1.0
            print(f"      pacing: {used:,} + {tokens:,} over {self.limit:,} tok/min "
                  f"— waiting {sleep:.0f}s")
            time.sleep(sleep)

    def record(self, tokens: int) -> None:
        """Charge tokens to the window — for admitted *and* rejected requests."""
        self.window.append((time.time(), tokens))


class RequestPacer:
    """Keep requests under the free tier's per-minute and per-day ceilings.

    Separate from RatePacer, which meters tokens: a run can be well inside the
    token ceiling and still be rejected for making a sixth request in a minute.
    Both apply at once on the free tier.

    The per-day count is the one that ends a run rather than delaying it. It is
    counted within this process only, so a second run on the same key the same day
    starts from zero as far as this counter knows -- the API is the authority, and
    a 429 that survives the retries is what it looks like when the real count
    disagrees. Stated plainly rather than hidden: this is a guard, not a ledger.
    """

    def __init__(self, rpm: int, rpd: int):
        self.rpm = rpm
        self.rpd = rpd
        self.times: list[float] = []
        self.total = 0

    @property
    def remaining_today(self) -> int:
        return max(0, self.rpd - self.total) if self.rpd else 10**9

    def wait_for_slot(self) -> None:
        """Block until a request may be made. Caller must check remaining_today first."""
        if not self.rpm:
            return
        while True:
            now = time.time()
            self.times = [x for x in self.times if now - x < 60.0]
            if len(self.times) < self.rpm:
                self.times.append(now)
                self.total += 1
                return
            sleep = 60.0 - (now - self.times[0]) + 1.0
            print(f"      pacing: {len(self.times)}/{self.rpm} requests in the last "
                  f"minute — waiting {sleep:.0f}s")
            time.sleep(sleep)


# Gemini's response_schema is an OpenAPI 3.0 subset, not full JSON Schema: it
# rejects any key it does not know, `additionalProperties` among them. The schema
# in prompts.py is written for Anthropic, which requires that key, so it has to be
# translated rather than shared verbatim. Only these keys survive the trip.
GEMINI_SCHEMA_KEYS = {
    "type", "format", "description", "nullable", "enum",
    "items", "properties", "required", "propertyOrdering",
    "minItems", "maxItems", "anyOf",
}


def gemini_schema(node):
    """Strip the JSON Schema keys Gemini rejects, recursively.

    Only the *shape* is translated -- field names, types, enums and required
    lists are untouched, so both providers are asked for exactly the same object.
    """
    if isinstance(node, list):
        return [gemini_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k not in GEMINI_SCHEMA_KEYS:
            continue
        if k == "properties":
            # The keys here are the caller's field names, not schema keywords --
            # filter their values, never the names themselves.
            out[k] = {name: gemini_schema(sub) for name, sub in v.items()}
            # Gemini does not honour the order properties are declared in unless
            # it is stated. The order matters here: quotes and reasoning are
            # written before the answer field, never after it.
            out["propertyOrdering"] = list(v.keys())
        elif k in ("required", "enum", "propertyOrdering"):
            out[k] = v  # plain lists of strings; nothing to recurse into
        else:
            out[k] = gemini_schema(v)
    return out


class GeminiClient:
    """Client wrapper supporting google-genai SDK, google.generativeai, or direct REST API."""

    def __init__(self, api_key: str | None = None, key_var: str = "GEMINI_API_KEY"):
        """`key_var` names which variable to read, so a second account's key can
        live in .env alongside the first and be selected with one flag. Values are
        unquoted here -- doing it in the shell is what produced a run of 400s.
        """
        env = dotenv_values(ROOT / ".env")

        self.key_var = key_var
        self.api_key = (
            api_key
            or os.getenv(key_var)
            or env.get(key_var)
            or os.getenv("GOOGLE_API_KEY")
            or env.get("GOOGLE_API_KEY")
            or ""
        )
        self._genai_sdk = None
        self._mode = "rest"

        try:
            from google import genai
            self._genai_sdk = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
            self._mode = "genai_sdk"
        except Exception:
            try:
                import google.generativeai as genai_legacy
                if self.api_key:
                    genai_legacy.configure(api_key=self.api_key)
                self._genai_sdk = genai_legacy
                self._mode = "genai_legacy"
            except Exception:
                self._mode = "rest"

    def count_tokens(self, model: str, text: str) -> int:
        if self._mode == "genai_sdk":
            try:
                res = self._genai_sdk.models.count_tokens(model=model, contents=text)
                return getattr(res, "total_tokens", getattr(res, "totalTokens", len(text) // 4))
            except Exception:
                pass

        if self._mode == "genai_legacy":
            try:
                m = self._genai_sdk.GenerativeModel(model)
                res = m.count_tokens(text)
                return getattr(res, "total_tokens", len(text) // 4)
            except Exception:
                pass

        if not self.api_key:
            return len(text) // 4

        model_clean = model.strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:countTokens?key={self.api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": text}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("totalTokens", len(text) // 4)
        except Exception:
            return len(text) // 4

    def generate_content(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        schema: dict,
        pacer=None,
        est_input_tokens: int = 0,
    ) -> dict:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please run `export GEMINI_API_KEY='your_key'` before running with --go."
            )

        if self._mode == "genai_sdk":
            try:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=schema,
                )
                res = self._genai_sdk.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                text = res.text or ""
                meta = getattr(res, "usage_metadata", None)
                prompt_tok = getattr(meta, "prompt_token_count", 0) if meta else 0
                out_tok = getattr(meta, "candidates_token_count", 0) if meta else 0
                cached_tok = getattr(meta, "cached_content_token_count", 0) if meta else 0
                thoughts_tok = getattr(meta, "thoughts_token_count", 0) if meta else 0
                return {
                    "text": text,
                    "prompt_tokens": prompt_tok,
                    "output_tokens": out_tok + (thoughts_tok or 0),
                    "answer_tokens": out_tok,
                    "thoughts_tokens": thoughts_tok or 0,
                    "cached_tokens": cached_tok,
                    "stop_reason": "end_turn",
                }
            except Exception as e:
                pass

        # REST API implementation
        model_clean = model.strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={self.api_key}"
        payload_dict = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        payload = json.dumps(payload_dict).encode("utf-8")

        for attempt in range(MAX_RETRIES + 1):
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"})
            try:
                # 120s was too short for the largest shards: a 165k-token input
                # with heavy thinking spends over two minutes before the first
                # byte comes back, and abandoning it mid-write both loses the
                # answer and spends a retry. Successful calls on 2026-09-02 ran
                # 20-62s, so 300 leaves real headroom without hanging forever.
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    text = ""
                    stop_reason = "end_turn"
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                        finish = candidates[0].get("finishReason", "STOP")
                        if finish != "STOP":
                            stop_reason = finish.lower()

                    meta = data.get("usageMetadata", {})
                    # Gemini 3.x reasoning tokens are billed as output but reported
                    # separately from candidatesTokenCount, and they count against
                    # maxOutputTokens. Reading only the candidates count made the
                    # recorded spend a floor rather than the spend, and made a
                    # finishReason of MAX_TOKENS look impossible: 1,059 candidate
                    # tokens against an 8,000 cap, with ~7,000 spent thinking.
                    answer_tok = meta.get("candidatesTokenCount", 0)
                    thoughts_tok = meta.get("thoughtsTokenCount", 0) or 0
                    return {
                        "text": text,
                        "prompt_tokens": meta.get("promptTokenCount", 0),
                        # What is billed, which is what the cost must be based on.
                        "output_tokens": answer_tok + thoughts_tok,
                        # Kept apart so the split stays visible in the log: it is
                        # what explains a truncated answer under a generous cap.
                        "answer_tokens": answer_tok,
                        "thoughts_tokens": thoughts_tok,
                        "cached_tokens": meta.get("cachedContentTokenCount", 0),
                        "stop_reason": stop_reason,
                    }
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                # 429 is a pacing problem, not a failure: the request was never
                # served, so nothing was spent and retrying costs nothing extra.
                # Google states how long to wait -- obey it rather than guessing.
                if e.code == 429 and attempt < MAX_RETRIES:
                    # The rejected request still counted against the meter, so
                    # charge it -- otherwise the pacer keeps believing there is
                    # room and every retry walks into the same wall.
                    if pacer is not None and est_input_tokens:
                        pacer.record(est_input_tokens)
                    stated = retry_delay_seconds(err_body, default=30.0)
                    # Back off on top of what Google states: repeated 429s mean
                    # the window is more congested than one retryDelay accounts for.
                    wait = stated * (attempt + 1)
                    print(f"      rate limited, waiting {wait:.0f}s "
                          f"(attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                if e.code >= 500 and attempt < MAX_RETRIES:
                    wait = 2.0 ** attempt
                    print(f"      server error {e.code}, retrying in {wait:.0f}s")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Gemini API HTTP Error {e.code}: {err_body}") from e
            except urllib.error.URLError as e:
                if attempt < MAX_RETRIES:
                    wait = 2.0 ** attempt
                    print(f"      network error ({e.reason}), retrying in {wait:.0f}s")
                    time.sleep(wait)
                    continue
                raise


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
        self.shard = shard
        self.n_shards = n_shards
        # Repeats are byte-identical requests sharing a cache key on purpose --
        # see run_eval.Call for why. Gemini caches implicitly rather than via
        # explicit breakpoints, so the saving is smaller here, but the ordering
        # requirement is the same.
        self.rep = rep
        self.n_reps = n_reps
        self.cache_key = (corpus_mod.cache_key(codes) if codes else "")
        if n_shards > 1:
            self.cache_key += f"#{shard}/{n_shards}"
        self.input_tokens = 0
        self.breakpoints: set[int] = set()
        self.cached_codes: tuple[str, ...] = ()

    @property
    def label(self):
        base = (self.indicators[0]["indicator_id"] if self.mode == "indicator"
                else self.subdim["subdimension_id"])
        return f"{base}~{self.shard}/{self.n_shards}" if self.n_shards > 1 else base


def split_only(only):
    """`--only` values, separated into subdimension ids and indicator ids.

    An indicator id contains '_i' ("d2_i3") and a subdimension id does not ("d2"),
    so one flag can carry both and the caller need not learn a second one.
    Returns (subdimension_ids, indicator_ids), each None when nothing was asked
    for — None meaning "no restriction", which is not the same as an empty set.
    """
    if not only:
        return None, None
    inds = {x for x in only if "_i" in x}
    subs = {x for x in only if "_i" not in x}
    # An indicator id implies its own subdimension, so naming d2_i3 alone does not
    # have to mean naming d2 as well.
    subs |= {x.split("_i")[0] for x in inds}
    return subs or None, inds or None


def plan(framework, country, models, modes, docs, only=None, shard_counts=None, repeats=1):
    shard_counts = shard_counts or {}
    only_subs, only_inds = split_only(only)
    calls, missing = [], []
    for model in models:
        for mode in modes:
            for sub in framework["subdimensions"]:
                if only_subs and sub["subdimension_id"] not in only_subs:
                    continue
                indicators = [i for i in sub["indicators"]
                              if not only_inds or i["indicator_id"] in only_inds]
                # An indicator filter that matches nothing in this subdimension is
                # not an empty call, it is no call: skip before the missing-source
                # bookkeeping, which would otherwise report indicators nobody asked
                # about as gaps in the corpus.
                if not indicators:
                    continue
                available, unavailable = [], []
                for ind in indicators:
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

    # Sorted by cache_key so calls over the same corpus stay contiguous; `rep`
    # sorts last only to make the order stable. See run_eval.plan.
    calls.sort(key=lambda c: (c.model, c.mode, c.cache_key, c.shard, c.rep))
    return calls, missing


def measure(client: GeminiClient, framework, country, calls, docs, shards=None):
    shards = shards or {}
    for c in calls:
        if c.codes in shards:
            doc_blocks, manifest, group_end = shards[c.codes][c.shard - 1]
        else:
            doc_blocks, manifest, group_end = corpus_mod.build(country, c.codes, docs)
        c.doc_blocks, c.manifest, c.group_end = doc_blocks, manifest, group_end

        task_block = P.dimension_block(framework["dimension"], c.subdim, c.indicators)
        user_prompt = "\n\n".join(doc_blocks + [task_block])
        full_text = P.system_prompt(manifest) + "\n\n" + user_prompt
        c.input_tokens = client.count_tokens(c.model, full_text)
    return calls


def project(calls):
    rows = {}
    for c in calls:
        r = rows.setdefault((c.model, c.mode), {"calls": 0, "fresh": 0, "write": 0, "read": 0})
        r["calls"] += 1
        r["fresh"] += c.input_tokens
    return rows


def parse_response(text: str):
    try:
        data = json.loads(text)
        return data.get("assessments", []), None
    except json.JSONDecodeError as e:
        return [], f"unparseable JSON: {e}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Run survey evaluation with Google Gemini models")
    ap.add_argument("--country", default="argentina")
    ap.add_argument("--model", nargs="+", default=["gemini-3.6-flash"])
    ap.add_argument("--mode", nargs="+", default=["subdimension"], choices=["subdimension", "indicator"])
    ap.add_argument("--only", nargs="+", metavar="ID",
                    help="restrict the run to these subdimension ids (e.g. d3) or "
                         "individual indicator ids (e.g. d2_i3); the two can be mixed, "
                         "and an indicator id is told apart by containing '_i'")
    # Gemini 3.x spends reasoning tokens out of this same ceiling and reports them
    # separately, so a cap sized for the answer alone truncates the JSON mid-object
    # -- which is exactly what happened on 2026-08-27: ~7,000 tokens of thinking,
    # 1,059 of answer, against a cap of 8,000. There is no way to turn thinking off
    # from here (the API takes no such parameter on this path), so the only lever is
    # a ceiling with room for both.
    ap.add_argument("--max-output-tokens", type=int, metavar="N",
                    help=f"output ceiling per call, thinking tokens included "
                         f"(default per mode: "
                         f"{', '.join(f'{m}={n}' for m, n in MAX_TOKENS.items())})")
    # Accepted so the two runners take the same command line, but the Gemini API
    # exposes no equivalent knob here, so it is never sent. It is therefore not a
    # parameter of the run and must not be recorded as one: the log and the
    # appendix both say "not applicable" rather than echoing a value that had no
    # effect on the call. If a thinking-budget parameter is wired up later, this
    # is the flag to route into it -- and EFFORT_NOT_SENT is what to delete.
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                    help="accepted for symmetry with run_eval.py but NOT sent to the "
                         "Gemini API, which has no equivalent parameter")
    ap.add_argument("--note", metavar="TEXT",
                    help="one line on what this run is for, kept in manifest.json and "
                         "listed in the country README. Optional, so a quick probe still "
                         "runs — but a run without one shows up in the index as unexplained")
    ap.add_argument("--go", action="store_true", help="make billable API calls (default is dry run)")
    ap.add_argument("--api-key-var", default="GEMINI_API_KEY", metavar="NAME",
                    help="which variable in .env (or the environment) holds the key — "
                         "use this to run on a second account's key (default GEMINI_API_KEY)")
    ap.add_argument("--tokens-per-minute", type=int, default=FREE_TIER_INPUT_TPM,
                    metavar="N",
                    help=f"pace calls to stay under N input tokens per minute "
                         f"(default {FREE_TIER_INPUT_TPM:,}, Google's free-tier ceiling; "
                         f"raise it on a paid key, 0 disables pacing)")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="ask each unit of work N times and majority-vote the answers, "
                         "reporting a per-indicator stability score (default 1)")
    # On the free tier a USD ceiling guards nothing: the run cannot spend money,
    # so a dollar budget would only ever stop a call that was free. What it can run
    # out of is requests, so that is what is enforced. --budget-usd is kept for a
    # key on a paid project, where it means what it says.
    ap.add_argument("--billing", default="free", choices=["free", "paid"],
                    help="whether this key's project is billed. On `free` (default) "
                         "no dollar budget is enforced, the request quota is, and "
                         "every cost figure is marked notional")
    ap.add_argument("--budget-usd", type=float, default=3.00,
                    help="hard cost ceiling in USD — enforced only with --billing paid")
    ap.add_argument("--requests-per-minute", type=int, default=FREE_TIER_RPM, metavar="N",
                    help=f"free-tier request ceiling per minute (default {FREE_TIER_RPM})")
    ap.add_argument("--requests-per-day", type=int, default=FREE_TIER_RPD, metavar="N",
                    help=f"free-tier request ceiling per day (default {FREE_TIER_RPD}); "
                         "the run stops when it is reached")
    args = ap.parse_args()

    framework = framework_mod.load()
    docs = corpus_mod.load_docs(args.country)
    client = GeminiClient(key_var=args.api_key_var)

    def count_fn(text):
        return client.count_tokens(args.model[0], text)

    # The same filter plan() applies, so the shards built here are the shards the
    # planned calls ask for — and no corpus is measured for a call nobody makes.
    only_subs, only_inds = split_only(args.only)
    code_sets = set()
    for sub in framework["subdimensions"]:
        if only_subs and sub["subdimension_id"] not in only_subs:
            continue
        avail = [i for i in sub["indicators"]
                 if (not only_inds or i["indicator_id"] in only_inds)
                 and framework_mod.held_codes(i, docs)]
        if not avail:
            continue
        code_sets.add(tuple(sorted({c for i in avail
                                    for c in framework_mod.held_codes(i, docs)})))
        code_sets.update(framework_mod.held_codes(i, docs) for i in avail)

    shards, shard_counts = {}, {}
    for codes in sorted(code_sets):
        try:
            shards[codes] = corpus_mod.build_shards(args.country, codes, docs, count_fn)
        except corpus_mod.MissingSource:
            continue
        shard_counts[codes] = len(shards[codes])

    calls, missing = plan(framework, args.country, args.model, args.mode, docs,
                          args.only, shard_counts, args.repeat)
    if not calls:
        sys.exit("Nothing to run.")

    measure(client, framework, args.country, calls, docs, shards)

    # Same run-folder layout as the Anthropic runner, so a Gemini run and a
    # Claude run of the same country sit side by side and report.py reads both.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (ROOT / "outputs" / args.country / "runs"
               / run_eval.run_name(args, stamp, provider="google"))
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir

    print(f"\n{'PLAN (Gemini)':<30}{'calls':>7}{'fresh':>12}{'cache wr':>12}{'cache rd':>12}{'input $':>10}{'max out $':>11}")
    print("-" * 94)
    total_lo = total_hi = 0.0
    for (model, mode), r in sorted(project(calls).items()):
        cin = cost_usd(model, input_tokens=r["fresh"], cache_creation_input_tokens=r["write"],
                       cache_read_input_tokens=r["read"])
        cout = r["calls"] * max_out(mode, args.max_output_tokens) * price_of(model).output_per_mtok / 1e6
        total_lo += cin
        total_hi += cin + cout
        print(f"{model + ' / ' + mode:<30}{r['calls']:>7}{r['fresh']:>12,}{r['write']:>12,}"
              f"{r['read']:>12,}{cin:>10.3f}{cout:>11.3f}")
    print("-" * 94)
    print(f"{'input (measured)':<30}{'':>7}{'':>12}{'':>12}{'':>12}{total_lo:>10.3f}")
    print(f"{'worst case incl. max output':<30}{'':>7}{'':>12}{'':>12}{'':>12}{total_hi:>10.3f}")
    if args.billing == "free":
        print("\nNOTIONAL: this key is on the free tier, so no dollar figure above is "
              "money.\nThey are what the same calls would cost on a paid key. What this "
              f"run can\nactually run out of is requests: {args.requests_per_minute}/min, "
              f"{args.requests_per_day}/day.")

    if missing:
        by_code = {}
        for m in missing:
            by_code[m["source_code"]] = by_code.get(m["source_code"], 0) + 1
        note = ", ".join(f"{n} routed to [{c}]" for c, n in sorted(by_code.items()))
        print(f"\nsource_missing (no call made): {note}")

    write_appendix(out_dir, framework, args, calls, missing)
    print(f"prompts appendix -> {(out_dir / 'prompts_appendix.md').relative_to(ROOT)}")

    projected = {"input": total_lo, "worst": total_hi}
    run_eval.write_manifest(run_dir, args, calls, missing, projected, provider="google",
                            planned_utc=stamp)

    if not args.go:
        print("\nDry run complete — no API calls were billed. Re-run with --go to execute.\n")
        return

    # Execution phase
    log = out_dir / "raw.jsonl"
    spent = 0.0
    n_failed = 0
    pacer = RatePacer(args.tokens_per_minute)
    free = args.billing == "free"
    reqs = RequestPacer(args.requests_per_minute if free else 0,
                        args.requests_per_day if free else 0)

    with log.open("w", encoding="utf-8") as fh:
        for rec in missing:
            fh.write(json.dumps({**rec, "run_timestamp": stamp, "call": False}, ensure_ascii=False) + "\n")

        shard_records = []
        if free:
            print(f"\nrunning {len(calls)} Gemini calls on the FREE TIER — no money is "
                  f"spent. Limits: {args.requests_per_minute} req/min, "
                  f"{args.requests_per_day} req/day, "
                  f"{args.tokens_per_minute:,} input tok/min. Every $ below is "
                  f"notional: what the same call would cost on a paid key.\n")
        else:
            print(f"\nrunning {len(calls)} Gemini calls, budget ${args.budget_usd:.2f}\n")
        for i, c in enumerate(calls, 1):
            p = price_of(c.model)
            worst = (c.input_tokens * p.input_per_mtok
                     + max_out(c.mode, args.max_output_tokens) * p.output_per_mtok) / 1e6
            if free:
                # Requests, not dollars, are what runs out here.
                if not reqs.remaining_today:
                    print(f"  STOP at call {i}/{len(calls)}: the free-tier ceiling of "
                          f"{args.requests_per_day} requests/day is used up. The rest of "
                          f"the run needs a new day or a paid key.")
                    break
                reqs.wait_for_slot()
            elif spent + worst > args.budget_usd:
                print(f"  STOP at call {i}/{len(calls)}: ${spent:.3f} spent, next call could "
                      f"reach ${spent + worst:.3f} > budget ${args.budget_usd:.2f}")
                break

            task_block = P.dimension_block(framework["dimension"], c.subdim, c.indicators)
            user_prompt = "\n\n".join(c.doc_blocks + [task_block])

            # Wait if this call would breach the per-minute ceiling. c.input_tokens
            # is the measured count from the planning phase, so the estimate is
            # exact rather than a guess.
            pacer.wait_for(c.input_tokens)

            t0 = time.time()
            try:
                res = client.generate_content(
                    model=c.model,
                    system_prompt=P.system_prompt(c.manifest),
                    user_prompt=user_prompt,
                    max_tokens=max_out(c.mode, args.max_output_tokens),
                    schema=gemini_schema(P.output_schema(
                        c.indicators, complete=run_eval.call_is_complete(c))),
                    pacer=pacer,
                    est_input_tokens=c.input_tokens,
                )
            except Exception as exc:
                # A rejected key (or any 400) fails identically for every remaining
                # call, so grinding through them wastes minutes to learn nothing.
                if "API key not valid" in str(exc) or "HTTP Error 400" in str(exc):
                    print(f"\n  ABORTING: {str(exc)[:200]}")
                    print(f"  The key in {args.api_key_var} was rejected. Nothing was billed.")
                    raise SystemExit(1)
                # One dead call must not discard the calls already paid for. Record
                # it as an unanswered row and carry on; merge_reps will report the
                # affected indicator as less stable rather than silently confident.
                n_failed += 1
                dt = time.time() - t0
                print(f"  [{i:>2}/{len(calls)}] {c.model:<18} {c.mode[:4]} {c.label:<7} "
                      f"FAILED after {dt:.0f}s: {str(exc)[:120]}")
                for ind in c.indicators:
                    rec = {
                        "country": args.country, "model": c.model, "mode": c.mode,
                        "subdimension_id": c.subdim["subdimension_id"],
                        "indicator_id": ind["indicator_id"],
                        "source_code": ind["source_code"],
                        **P.assessment_columns(P.empty_assessment(ind)),
                        "reasoning": f"call failed: {str(exc)[:400]}",
                        "call": True, "cache_key": c.cache_key,
                        "cached_codes": "+".join(c.cached_codes),
                        "input_tokens": 0, "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0, "output_tokens": 0,
                        "n_indicators_in_call": len(c.indicators),
                        "cost_usd": 0.0, "cost_notional": free,
                        "billing": args.billing,
                        "requests_used_today": reqs.total if free else None,
                        "latency_s": round(dt, 2),
                        "stop_reason": "error", "effort": EFFORT_NOT_SENT,
                        "run_timestamp": stamp, "error": str(exc)[:400],
                        "shard": c.shard, "n_shards": c.n_shards,
                        "rep": c.rep, "n_reps": c.n_reps,
                    }
                    shard_records.append(rec)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                continue
            dt = time.time() - t0

            # promptTokenCount includes the implicitly cached tokens, which Google
            # bills at the cached rate. Recorded apart, as fresh vs cache-read, so
            # the cost and the --budget-usd check are in real dollars and report.py
            # does not count the cached tokens twice.
            cached_tok = res.get("cached_tokens", 0)
            in_tok = res["prompt_tokens"] - cached_tok
            out_tok = res["output_tokens"]
            call_cost = cost_usd(c.model, input_tokens=in_tok,
                                 cache_read_input_tokens=cached_tok, output_tokens=out_tok)
            spent += call_cost

            assessments, err = parse_response(res["text"])
            # Written before the rows, so a crash while building them still leaves
            # the response on disk. An unparseable response is exactly the one
            # worth keeping.
            response_file = run_eval.save_response(out_dir, c, res["text"], err is None)
            by_id = {a["indicator_id"]: a for a in assessments}

            for ind in c.indicators:
                a = by_id.get(ind["indicator_id"], {})
                # criterion_list carries its answer in `elements`, one boolean per
                # element; a malformed one is an error on the row, not a silent {}.
                answer, a_err = (P.read_assessment(
                                     ind, a, require_quotes=run_eval.has_all_sources(c, ind))
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
                    "input_tokens": in_tok,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": cached_tok,
                    "output_tokens": out_tok,
                    "answer_tokens": res.get("answer_tokens", out_tok),
                    "thoughts_tokens": res.get("thoughts_tokens", 0),
                    "n_indicators_in_call": len(c.indicators),
                    # Kept because it is the only comparable cost figure across
                    # providers, but on the free tier it is what the call *would*
                    # have cost, not what anything was charged. Anything that sums
                    # this column must read cost_notional first.
                    "cost_usd": call_cost,
                    "cost_notional": free,
                    "billing": args.billing,
                    "requests_used_today": reqs.total if free else None,
                    "latency_s": round(dt, 2),
                    "response_file": response_file,
                    "stop_reason": res["stop_reason"], "effort": EFFORT_NOT_SENT,
                    "run_timestamp": stamp,
                    "error": "; ".join(x for x in (err, a_err) if x),
                    "shard": c.shard, "n_shards": c.n_shards,
                    "rep": c.rep, "n_reps": c.n_reps,
                }
                shard_records.append(rec)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

            # out= is what is billed; the split says how much of it was thinking,
            # which is what explains a truncated answer under a generous cap.
            print(f"  [{i:>2}/{len(calls)}] {c.model:<18} {c.mode[:4]} {c.label:<7} "
                  f"in={in_tok:<6,} out={out_tok:<5,} "
                  f"(answer {res.get('answer_tokens', out_tok):,} + thinking "
                  f"{res.get('thoughts_tokens', 0):,}) "
                  f"${call_cost:.4f}  cum ${spent:.3f}  {dt:>5.1f}s{'  ' + err if err else ''}")

        by_shard = run_eval.merge_shards(shard_records)
        merged = [r for r in by_shard if r.get("n_shards", 1) > 1]
        for r in merged:
            fh.write(json.dumps({**r, "call": False, "merged": True}, ensure_ascii=False) + "\n")

        voted = [r for r in run_eval.merge_reps(by_shard) if r.get("n_reps", 1) > 1]
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
                print(f"    {r['indicator_id']:<8} {r['model']:<18} {r['mode'][:4]}  "
                      f"{r['rep_values']} -> {run_eval.answer_str(r)} "
                      f"({r['stability']:.2f}){tie}")
            run_eval.print_text_similarity(voted)

    run_eval.write_manifest(
        run_dir, args, calls, missing, projected,
        {"spent_usd": 0.0 if free else round(spent, 4),
         "notional_usd_on_paid_key": round(spent, 4) if free else None,
         "billing": args.billing,
         "requests_used": reqs.total if free else None,
         "requests_per_day_limit": args.requests_per_day if free else None,
         "budget_usd": None if free else args.budget_usd,
         "n_calls_planned": len(calls), "started_utc": stamp,
         "finished_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")},
        provider="google", planned_utc=stamp)

    print()
    run_eval.print_uncited(shard_records)
    if free:
        print(f"\nNo money spent: free tier. Used {reqs.total} of "
              f"{args.requests_per_day} requests/day "
              f"({reqs.remaining_today} left today). "
              f"Notional cost had this been a paid key: ${spent:.4f}")
    else:
        print(f"\nSpent ${spent:.4f} of ${args.budget_usd:.2f} budget")
    if n_failed:
        print(f"  {n_failed} of {len(calls)} calls FAILED and were recorded as 'error'")
    print(f"raw log  -> {log.relative_to(ROOT)}")
    print(f"manifest -> {(run_dir / 'manifest.json').relative_to(ROOT)}")
    print(f"run folder -> {run_dir.relative_to(ROOT)}\n")


def write_appendix(out_dir, framework, args, calls, missing) -> None:
    """Methodological appendix: the verbatim prompt behind every indicator."""
    by_indicator = {}
    for c in calls:
        for ind in c.indicators:
            by_indicator.setdefault((c.mode, ind["indicator_id"]), c)

    scaffold = framework.get("scaffold", {})
    role = scaffold.get("role", P.ROLE)
    inputs_tpl = scaffold.get("inputs", P.INPUTS)
    constraints = scaffold.get("constraints", P.CONSTRAINTS)
    method = scaffold.get("method", P.METHOD)

    L = [
        f"# Prompt appendix — {args.country.title()}",
        "",
        f"Framework: **{framework['dimension']}**, parsed from "
        f"`{framework['source_file']}` (the analytical framework is the single source of truth; "
        "this file is generated from it, never hand-edited).",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"models: {', '.join(args.model)} · modes: {', '.join(args.mode)} · "
        f"effort: not applicable (the Gemini API takes no effort parameter; "
        f"`--effort {args.effort}` was accepted but not sent) · "
        f"max_output_tokens: "
        f"{', '.join(f'{m}={max_out(m, args.max_output_tokens)}' for m in args.mode)}"
        f"{' (default)' if not args.max_output_tokens else ' (--max-output-tokens)'}"
        f" · thinking tokens are billed out of this ceiling",
        "",
        "Every call is a single user turn against the Gemini API with a structured-output "
        "schema (below). No conversation state carries between indicators: each assessment is "
        "independent, and the only evidence available to the model is the source documents "
        "listed in each entry.",
        "",
        "## 1. Shared scaffold (system prompt)",
        "",
        "Lifted verbatim from the `scaffold` object in "
        f"`{framework['source_file']}`. Role and Constraints are identical, byte for byte, in "
        "every call.",
        "",
        "### Role", "", "```text", role, "```", "",
        "### Inputs (template)", "", "```text", inputs_tpl, "```", "",
        "### Constraints", "", "```text", constraints, "```", "",
        "## 2. Method block", "",
        "Appended to every task block, after the indicator list.", "",
        "```text", method, "```", "",
        "## 3. Required output schema", "",
        *run_eval.schema_appendix_lines(framework),
        "## 4. Per-indicator task blocks", "",
        "The user turn is the source documents (verbatim extracted text) followed by the task block.", "",
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
