"""Regenerate the colleague-facing survey inventory from the pipeline's own state.

The inventory used to be maintained by hand, so it drifted: file counts predated
both the 43 newly scraped documents and the debris move, `docs_status` said
`completo` for countries whose corpus map has no questionnaire at all, and the
`scraper` column still named the 25 per-country scripts that `scrape_docs.py`
replaced. One row (portugal) had an unquoted comma in `notes`, so the file did
not parse: pandas saw 13 fields against a 12-column header and raised.

Everything here is derived, so it cannot drift again:

    scope, exclusion reason   scripts/study_scope.py
    survey, agency, C/M/G     config/corpus_map.<country>.json, else config/draft/
    document counts           data/raw/<country>/documentacion/ on disk
    debris moved              data/raw/<country>/descartes/_moved.csv
    microdata waves           config/microdata_years.json

Only `region`, `url` and the free-text `notes` are carried over from the old
hand-written file, because nothing in the pipeline knows them. The old file is
read tolerantly: fields past the last column are rejoined into `notes`, which
recovers the portugal row instead of dropping it.

    python scripts/inventory.py            # dry run, prints the table
    python scripts/inventory.py --go       # rewrite the CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from study_scope import EXCLUDED, ISO3, LABEL  # noqa: E402

OUT = ROOT / "data" / "inventory" / "surveys_inventory.csv"
OLD_COLS = 12  # the hand-written file's header width

# Formats corpus.py can actually read; see corpus.READERS.
READABLE = {".pdf", ".docx"}

COLUMNS = [
    "country", "iso3", "region", "survey_name", "acronym", "stats_office", "url",
    "in_scope", "excluded_reason", "anchor_case",
    "docs_readable", "docs_other", "debris_moved",
    "corpus_map", "n_C", "n_M", "n_G", "corpus_tokens", "sources_missing",
    "microdata_years", "microdata_waves", "notes",
]


def carried_over() -> dict[str, dict]:
    """Region, url and notes from the old hand-written CSV.

    Tolerant on purpose: the portugal row has an unquoted comma in `notes` and
    so carries 13 fields. Rejoining the overflow recovers it; strict parsing
    drops it, which is how it went unnoticed.
    """
    if not OUT.exists():
        return {}
    out = {}
    with OUT.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows or len(rows[0]) != OLD_COLS:
        return {}  # already regenerated; nothing to carry
    for r in rows[1:]:
        if len(r) > OLD_COLS:
            r = r[: OLD_COLS - 1] + [",".join(r[OLD_COLS - 1 :])]
        if len(r) < OLD_COLS:
            continue
        out[r[0].strip().lower().replace(" ", "_")] = {
            "region": r[1], "survey_name": r[2], "acronym": r[3],
            "stats_office": r[4], "url": r[5], "anchor_case": r[6], "notes": r[11],
        }
    return out


def corpus_map(country: str) -> tuple[str, dict | None]:
    live = ROOT / "config" / f"corpus_map.{country}.json"
    if live.exists():
        return "live", json.loads(live.read_text(encoding="utf-8"))
    draft = ROOT / "config" / "draft" / f"corpus_map.{country}.json"
    if draft.exists():
        return "draft", json.loads(draft.read_text(encoding="utf-8"))
    return "none", None


def doc_counts(country: str) -> tuple[int, int]:
    d = ROOT / "data" / "raw" / country / "documentacion"
    if not d.exists():
        return 0, 0
    files = [p for p in d.rglob("*") if p.is_file() and not p.name.startswith(".")]
    readable = sum(1 for p in files if p.suffix.lower() in READABLE)
    return readable, len(files) - readable


def debris_moved(country: str) -> int:
    log = ROOT / "data" / "raw" / country / "descartes" / "_moved.csv"
    if not log.exists():
        return 0
    with log.open(encoding="utf-8") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def microdata(country: str, blob: dict) -> tuple[str, int]:
    nat = blob.get("countries", {}).get(country, {}).get("national", {}) or {}
    if not nat:
        return "", 0
    years = sorted(nat)
    waves = sum(len(v) for v in nat.values())
    span = years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}"
    return span, waves


def build() -> list[dict]:
    old = carried_over()
    years_blob = json.loads((ROOT / "config" / "microdata_years.json").read_text())
    rows = []
    for country in sorted(ISO3):
        prev = old.get(country, {})
        kind, cmap = corpus_map(country)
        readable, other = doc_counts(country)
        span, waves = microdata(country, years_blob)

        n = {c: 0 for c in "CMG"}
        tokens = 0
        missing = []
        survey = prev.get("survey_name", "")
        agency = prev.get("stats_office", "")
        if cmap:
            survey = cmap.get("survey", survey)
            agency = cmap.get("agency", agency)
            for c in "CMG":
                n[c] = len(cmap["sources"][c]["files"])
                if n[c] == 0:
                    missing.append(c)
            tok = cmap.get("estimated_tokens", {})
            tokens = sum(tok.get(c, 0) for c in "CMG")

        rows.append({
            "country": LABEL.get(country, country.replace("_", " ").title()),
            "iso3": ISO3[country],
            "region": prev.get("region", ""),
            "survey_name": survey,
            "acronym": prev.get("acronym", ""),
            "stats_office": agency,
            "url": prev.get("url", ""),
            "in_scope": "FALSE" if country in EXCLUDED else "TRUE",
            "excluded_reason": EXCLUDED.get(country, ""),
            "anchor_case": prev.get("anchor_case", "FALSE"),
            "docs_readable": readable,
            "docs_other": other,
            "debris_moved": debris_moved(country),
            "corpus_map": kind,
            "n_C": n["C"], "n_M": n["M"], "n_G": n["G"],
            "corpus_tokens": tokens,
            "sources_missing": "+".join(missing),
            "microdata_years": span,
            "microdata_waves": waves,
            "notes": prev.get("notes", ""),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="rewrite the CSV (default is a dry run)")
    args = ap.parse_args()

    rows = build()
    head = ["country", "in_scope", "corpus_map", "docs_readable", "n_C", "n_M", "n_G",
            "corpus_tokens", "sources_missing", "microdata_waves"]
    print("  ".join(f"{c:>14}" if c != "country" else f"{c:16}" for c in head))
    for r in rows:
        print("  ".join(f"{str(r[c]):>14}" if c != "country" else f"{str(r[c]):16}" for c in head))

    if not args.go:
        print(f"\nDry run — {OUT.relative_to(ROOT)} not written. Re-run with --go.")
        return

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)} — {len(rows)} rows, {len(COLUMNS)} columns")


if __name__ == "__main__":
    main()
