"""Which years of microdata the study actually holds, per country.

    python scripts/microdata_years.py            # scan and write the cache
    python scripts/microdata_years.py --print    # show the table only

Writes `config/microdata_years.json`, which `scripts/inventory.py` reads. The scan
is cached because two sources cannot be read from the path alone:

  * UK microdata are UKDA study-number archives (`8813tab_<sha>_V1.zip`) whose
    filenames carry no year at all. The year lives inside, in the tab-file stem
    `lfsp_<period><yy>_eul` — `aj16` is Apr-Jun 2016, `fa21` Feb-Apr 2021. ONS
    uses rolling quarters, so the period code is two month initials, not q1-q4.
  * Eurostat public-use files are one zip per country holding every wave.

Both are read through `zipfile`, which parses only the central directory — but
see the dataless guard below, which is the reason this is a cache and not a
function call at plot time.

Everything else is recovered from the path, and deliberately so: most of the
microdata may be held as placeholders whose contents are not stored locally, and a
path-based scan reads names only, so it still reports the truth about a holding
that is not materialised locally.

Two counting traps, both live here:

  * A trailing download stamp is not a data year. Brazil ships
    `PNADC_2016_visita1_20250822.zip` — the 2025 is the day IBGE regenerated the
    file. YEAR_RE requires a delimiter after the four digits, so `20250822`
    cannot match while `_2016_` can.
  * Eurostat PUFs are the harmonised EU LFS, not the national instrument, so
    they are recorded under a separate key. Germany holds no national microdata
    (the Mikrozensus SUF goes only to EU-based institutions) and would otherwise
    look covered for 2013 on the strength of a different survey.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "config" / "microdata_years.json"

# A year must be delimited on both sides, which is what keeps Brazil's
# `_20250822` download stamp from registering as a 2025 wave.
YEAR_RE = re.compile(r"(?:^|[/_-])((?:19|20)\d{2})(?=[/_.-]|$)")

# Within-year period, tried in order. The bare two-digit month is last and
# anchored on both sides, or it would fire on any number in a filename.
# `\b` cannot be used to close these: `_` is a word character, so `q3_hogar`
# has no boundary after the digit and every quarterly country collapsed to one
# wave per year. A negative lookahead for a further digit is what is meant.
PERIOD_RES = (
    ("q", re.compile(r"[_/]q([1-4])(?![0-9])", re.I)),
    ("t", re.compile(r"trimestre([1-4])", re.I)),
    ("v", re.compile(r"visita([1-5])", re.I)),
    ("m", re.compile(r"_(0[1-9]|1[0-2])(?=[._])")),
)

# Lookup/classification tables shipped beside the waves. Peru's
# `tablas/ENAHO-TABLA-CNO-2015.sav` is an occupation coding frame, not a 2015 wave.
LOOKUP_DIRS = {"tablas", "descartes", "diccionarios"}

# ONS rolling-quarter codes: two month initials, e.g. aj16 = Apr-Jun 2016.
UK_WAVE_RE = re.compile(r"lfsp_([a-z]{2})(\d{2})_", re.I)

BOOKKEEPING = ("manifest", "_moved")
MICRODATA_SUFFIXES = {".zip", ".csv", ".sav", ".dta", ".rar", ".7z", ".txt", ".parquet"}

EUROSTAT_DIR = RAW / "eurostat_lfs"
EUROSTAT_COUNTRY = {
    "DE": "germany", "ES": "spain", "FR": "france",
    "IT": "italy", "NL": "netherlands",
}


def _is_microdata(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in MICRODATA_SUFFIXES
        and not path.name.lower().startswith(BOOKKEEPING)
        and not path.name.startswith(".")
    )


def _period(tail: str) -> str | None:
    for tag, rx in PERIOD_RES:
        m = rx.search(tail)
        if m:
            return f"{tag}{m.group(1)}"
    return None


def scan_paths(country: str) -> dict[str, set[str]]:
    """year -> set of within-year periods, from filenames only.

    A year with no recoverable period gets one pseudo-period, so an annual
    survey reads as complete rather than as an empty year."""
    out: dict[str, set[str]] = {}
    micro = RAW / country / "microdatos"
    for path in sorted(micro.rglob("*")) if micro.exists() else []:
        if not _is_microdata(path):
            continue
        rel_path = path.relative_to(micro)
        if set(part.lower() for part in rel_path.parts[:-1]) & LOOKUP_DIRS:
            continue
        rel = str(rel_path)
        period = _period(rel) or "y"
        # Every year in the path counts, not just the last: Ecuador ships
        # `2018_2019/ENEMDU_2018_2019_panel.sav`, a panel spanning both.
        for year in set(YEAR_RE.findall(rel)):
            out.setdefault(year, set()).add(period)
    return out


def scan_uk() -> dict[str, set[str]]:
    """UK years live inside the archive, in the tab-file stem."""
    out: dict[str, set[str]] = {}
    micro = RAW / "united_kingdom" / "microdatos"
    for path in sorted(micro.glob("*.zip")) if micro.exists() else []:
        if path.stat().st_blocks == 0:
            continue  # not on disk; opening it would download gigabytes
        for name in zipfile.ZipFile(path).namelist():
            m = UK_WAVE_RE.search(Path(name).name)
            if m:
                wave, yy = m.group(1).lower(), int(m.group(2))
                out.setdefault(str(2000 + yy), set()).add(wave)
    return out


def scan_eurostat() -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """Harmonised EU LFS public-use files, one zip per country, kept separate
    from national holdings. Returns (per-country years, offloaded zips)."""
    out: dict[str, dict[str, list[str]]] = {}
    offloaded: list[str] = []
    for path in sorted(EUROSTAT_DIR.glob("*_PUF_LFS.zip")) if EUROSTAT_DIR.exists() else []:
        country = EUROSTAT_COUNTRY.get(path.name[:2])
        if country is None:
            continue
        if path.stat().st_blocks == 0:
            offloaded.append(path.name)
            continue
        years: dict[str, set[str]] = {}
        for name in zipfile.ZipFile(path).namelist():
            for y in YEAR_RE.findall(Path(name).stem):
                years.setdefault(y, set()).add("y")
        out[country] = {y: sorted(p) for y, p in years.items()}
    return out, offloaded


def local_bytes(country: str) -> tuple[int, int]:
    """(logical bytes, bytes actually materialised on this machine).

    st_blocks is 0 for a placeholder whose contents are not on disk, so the gap between the two is
    how much of the holding is not really here."""
    logical = materialised = 0
    root = RAW / country
    for path in root.rglob("*") if root.exists() else []:
        if not _is_microdata(path):
            continue
        st = path.stat()
        logical += st.st_size
        if st.st_blocks:
            materialised += st.st_size
    return logical, materialised


def build() -> dict:
    import sys
    sys.path.insert(0, str(ROOT / "scripts" / "scraping"))
    from scrape_docs import COUNTRIES

    eurostat, offloaded = scan_eurostat()
    data: dict[str, dict] = {}
    for country in sorted(COUNTRIES):
        years = scan_uk() if country == "united_kingdom" else scan_paths(country)
        logical, materialised = local_bytes(country)
        data[country] = {
            "national": {y: sorted(p) for y, p in sorted(years.items())},
            "eurostat": eurostat.get(country, {}),
            "logical_bytes": logical,
            "materialised_bytes": materialised,
        }
    return {"countries": data, "eurostat_offloaded": offloaded}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args()

    if args.show and CACHE.exists():
        payload = json.loads(CACHE.read_text())
    else:
        payload = build()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"{'country':<17}{'years held':<9} {'span':<12}{'local':>7}  waves")
    for country, rec in payload["countries"].items():
        nat = rec["national"]
        span = f"{min(nat)}-{max(nat)}" if nat else "-"
        pct = (100 * rec["materialised_bytes"] / rec["logical_bytes"]) if rec["logical_bytes"] else 0
        euro = f'  +eurostat {min(rec["eurostat"])}-{max(rec["eurostat"])}' if rec["eurostat"] else ""
        print(f"{country:<17}{len(nat):<9} {span:<12}{pct:>6.0f}%  "
              f"{sum(len(v) for v in nat.values())}{euro}")
    if payload["eurostat_offloaded"]:
        print("\noffloaded eurostat zips, not scanned:", ", ".join(payload["eurostat_offloaded"]))
    if not args.show:
        print(f"\nWrote {CACHE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
