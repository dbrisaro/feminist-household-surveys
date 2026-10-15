"""Build RESULTS_SUMMARY.md for a multi-country run from each country's report.

The countries and their run folders are listed in <dir>/runs.json, as
{"<country>": "<run folder name>"}. Each run must already have been reported
(`report.py --country <c> --run <folder>`), since the labels are read from
<run>/report/results_indicators.csv rather than derived here.

    python scripts/llm/final_run_results.py --dir outputs/final_run_2026-10-08
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "llm"))
import framework as F  # noqa: E402

# English names, for RESULTS_SUMMARY.md; the same names the English figures use.
COUNTRY_EN = {"argentina": "Argentina", "bolivia": "Bolivia", "chile": "Chile", "colombia": "Colombia",
              "ecuador": "Ecuador", "italy": "Italy", "mexico": "Mexico", "paraguay": "Paraguay",
              "peru": "Peru", "spain": "Spain", "united_kingdom": "United Kingdom", "uruguay": "Uruguay"}
NAMES_EN = {
    "d1_i1": "Sex variable", "d1_i2": "Gender identity variable",
    "d1_i3": "Instructions for recording sex or gender", "d1_i4": "Terms for persons and kinship",
    "d2_i1": "Domestic or care work module", "d2_i2": "Responsibility, performance and magnitude",
    "d2_i3": "Unpaid work in the activity category", "d2_i4": "Domestic work recorded per person",
    "d2_i5": "Supervision or availability to care", "d3_i1": "Time allocation across activities",
    "d3_i2": "Time in paid work, unpaid work, leisure and self-care", "d4_i1": "Definition of headship",
    "d4_i2": "Method for identifying the head", "d4_i3": "Reference person and respondent",
    "d4_i4": "Dimensions of headship by member", "d4_i5": "Relationships and household delimitation",
    "d4_i6": "Types of female-headed households",
}
LABEL = {"met": "✔ met", "partially_met": "◐ partially", "unmet": "✗ unmet",
         "insufficient_evidence": "no source"}


def cell(r) -> str:
    """One country's result for one indicator, as it appears in the matrix."""
    if r is None:
        return "—"
    if r["label"] == "insufficient_evidence":
        return LABEL["insufficient_evidence"]
    if r["type"] == "record":
        return "record"
    if r["type"] == "categorical":
        return r["selected"] if isinstance(r["selected"], str) and r["selected"] else "(empty)"
    s = LABEL.get(r["label"], r["label"])
    if r["type"] == "criterion_list" and pd.notna(r.get("n_elements_true")):
        s += f" {int(r['n_elements_true'])}/{int(r['n_elements'])}"
    if pd.notna(r.get("stability")) and r["stability"] < 1:
        s += f" ⚠{r['stability']:.2f}"
    return s


def answer(r) -> str:
    """The voted answer, spelled out for the per-country table."""
    t = r["type"]
    if t == "criterion":
        if pd.isna(r["value"]):
            return "no answer"
        return "true" if bool(r["value"]) else f"false · {r['exclusion_type']}"
    if t == "criterion_list" and isinstance(r["elements"], str):
        return " ".join(("✓" if v else "✗") + k for k, v in json.loads(r["elements"]).items())
    if t == "categorical":
        return r["selected"] if isinstance(r["selected"], str) and r["selected"] else "(empty)"
    if t == "record":
        text = r["extracted_text"] if isinstance(r["extracted_text"], str) else ""
        return text[:160].replace("\n", " ").replace("|", "/") or "(empty)"
    return ""


def _json(x):
    try:
        return json.loads(x) if isinstance(x, str) else None
    except json.JSONDecodeError:
        return None


def _bool(x):
    if isinstance(x, str):
        return {"True": True, "False": False}.get(x)
    return None if pd.isna(x) else bool(x)


def _str(x) -> str:
    return x if isinstance(x, str) else ""


def agrees(row, r) -> bool:
    """Whether one repetition (one part, in a split call) gave the voted answer.

    A split call is merged per repetition before the vote, so a repetition that
    agrees with the vote can still hold a part that answered differently. Only a
    part whose own answer is the voted one can supply the quote that shows it.
    """
    if r["type"] == "criterion":
        return _bool(row["value"]) == _bool(r["value"])
    if r["type"] == "criterion_list":
        return _json(row["elements"]) == _json(r["elements"])
    if r["type"] == "categorical":
        return _str(row["selected"]) == _str(r["selected"])
    return False


def fmt_quote(q) -> str:
    text = " ".join(str(q.get("text", "")).split())[:110].replace("|", "/")
    return f"“{text}” ({str(q.get('location', ''))[:40].replace('|', '/')})"


def first_quote(r, reps) -> str:
    """The voted answer's first quote, taken from a repetition that gave that answer.

    report.py already takes the quotes from a repetition that voted with the
    majority, but in a split call those quotes are every part's, in part order,
    so the first one can come from a part that answered otherwise. That quote is
    kept when its part agrees with the vote; otherwise the first quote of the
    first agreeing repetition and part replaces it. Record indicators are not
    voted, so they keep the quote of the repetition closest to the others.
    """
    quotes = _json(r["quotes"]) or []
    if r["type"] == "record" or not quotes or reps.empty:
        return fmt_quote(quotes[0]) if quotes else "(no quote)"
    split = reps["shard"].nunique() > 1
    rows = [row for _, row in reps.sort_values(["rep", "shard"]).iterrows()
            if agrees(row, r) and _json(row["quotes"])]

    def tag(row) -> str:
        return f"rep {int(row['rep'])}, part {int(row['shard'])}" if split else f"rep {int(row['rep'])}"

    for row in rows:
        if any(q.get("text") == quotes[0].get("text") for q in _json(row["quotes"])):
            return f"{fmt_quote(quotes[0])} [{tag(row)}]"
    if rows:
        return f"{fmt_quote(_json(rows[0]['quotes'])[0])} [{tag(rows[0])}]"
    return "(no quote from a repetition that agrees with the vote)"


def element_shares(fw, rows) -> dict:
    """Subdimension -> (true elements, elements) for one country, as final_run_figures.py counts them.

    Only criteria and criterion lists with a met, partially_met or unmet label count; a criterion
    is one element, and a criterion list adds its true elements out of all its elements.
    """
    share = {}
    for s in fw["subdimensions"]:
        t = n = 0
        for i in s["indicators"]:
            r = rows[i["indicator_id"]]
            if r["type"] not in ("criterion", "criterion_list") or r["label"] not in ("met", "partially_met", "unmet"):
                continue
            if r["type"] == "criterion":
                t, n = t + int(r["label"] == "met"), n + 1
            else:
                t, n = t + int(r["n_elements_true"]), n + int(r["n_elements"])
        share[s["subdimension_id"]] = (t, n)
    return share


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "outputs" / "final_run_2026-10-08",
                    help="folder holding runs.json; RESULTS_SUMMARY.md is written there")
    args = ap.parse_args()
    out = args.dir if args.dir.is_absolute() else ROOT / args.dir
    runs = json.loads((out / "runs.json").read_text(encoding="utf-8"))

    fw = F.load()
    order = [i["indicator_id"] for s in fw["subdimensions"] for i in s["indicators"]]
    data, reps = {}, {}
    for country, run in runs.items():
        report = ROOT / "outputs" / country / "runs" / run / "report"
        df = pd.read_csv(report / "results_indicators.csv")
        data[country] = {r["indicator_id"]: r for _, r in df.iterrows()}
        reps[country] = pd.read_csv(report / "results_repetitions.csv")
    cs = list(runs)

    L = ["# Final run: results", "",
         "Gemini 3.6 Flash, indicator mode, 3 repetitions, majority vote (per element in criterion "
         "lists). Generated by `scripts/llm/final_run_results.py` from each run's "
         "`report/results_indicators.csv` and `report/results_repetitions.csv`.", "",
         f"Countries: {', '.join(COUNTRY_EN[c] for c in cs)}.", "",
         "## Results matrix", "",
         "✔ met · ◐ partially_met (true elements / all elements) · ✗ unmet · ⚠ stability < 1 · "
         "record = record indicator (neither labelled nor voted) · categorical = option selected.", "",
         "In the country tables, the first quote of a voted indicator comes from a repetition (and, in "
         "split calls, from a part) whose answer agrees with the vote; which one is given in brackets. "
         "The quote of a record indicator comes from the repetition closest to the others.", "",
         "| ID | Indicator | " + " | ".join(COUNTRY_EN[c] for c in cs) + " |",
         "|---|---|" + "---|" * len(cs)]
    for i in order:
        L.append(f"| {i} | {NAMES_EN[i]} | " + " | ".join(cell(data[c].get(i)) for c in cs) + " |")
    subs = [s["subdimension_id"] for s in fw["subdimensions"]]
    shares = {c: element_shares(fw, data[c]) for c in cs}
    total = {c: tuple(sum(shares[c][s][k] for s in subs) for k in (0, 1)) for c in cs}
    L += ["", "## Elements met by country and subdimension", "",
          "True elements out of elements counted, as in Figure 2: a criterion is one element and a criterion "
          "list counts its true elements; only indicators labelled met, partially_met or unmet count. "
          "Countries from the most elements met to the fewest, equal counts in alphabetical order.", "",
          "| Country | " + " | ".join(f"Sub. {s[1:]}" for s in subs) + " | Total |",
          "|---|" + "---|" * (len(subs) + 1)]
    for c in sorted(cs, key=lambda c: (-total[c][0], COUNTRY_EN[c])):
        L.append(f"| {COUNTRY_EN[c]} | " + " | ".join(f"{shares[c][s][0]}/{shares[c][s][1]}" for s in subs)
                 + f" | {total[c][0]}/{total[c][1]} |")
    for c in cs:
        L += ["", f"## {COUNTRY_EN[c]}", "", f"Run: `outputs/{c}/runs/{runs[c]}`", "",
              "| ID | Indicator | Label | Answer | Stability | First quote |",
              "|---|---|---|---|---|---|"]
        for i in order:
            r = data[c].get(i)
            if r is None:
                L.append(f"| {i} | {NAMES_EN[i]} | — | not asked | | |")
                continue
            st = f"{r['stability']:.2f}" if pd.notna(r.get("stability")) else "n/a"
            q = first_quote(r, reps[c][reps[c]["indicator_id"] == i])
            L.append(f"| {i} | {NAMES_EN[i]} | {r['label']} | {answer(r)} | {st} | {q} |")
    (out / "RESULTS_SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {(out / 'RESULTS_SUMMARY.md').relative_to(ROOT)}  ({', '.join(cs)})")


if __name__ == "__main__":
    main()
