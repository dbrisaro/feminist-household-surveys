"""Draft a corpus map for a country from what is actually in its documentation folder.

Filename rules resolve most documents into C (questionnaire), M (methodology) or
G (interviewer guide); the residue is resolved by reading each title page. Where a
document repeats per wave, the most recent one wins and the rest are recorded as
superseded, never dropped silently.

Nothing is moved or renamed. Output is a draft config/draft/corpus_map.<country>.json
plus config/draft/review.<country>.md listing every decision for review.

    python scripts/llm/triage_corpus.py --country bolivia          # free, rules only
    python scripts/llm/triage_corpus.py --country united_kingdom   # dry run, shows token cost
    python scripts/llm/triage_corpus.py --country united_kingdom --go
    python scripts/llm/triage_corpus.py --all --go
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import framework as framework_mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "data" / "inventory" / "surveys_inventory.csv"
DRAFT_DIR = ROOT / "config" / "draft"

READABLE = {".pdf", ".docx"}  # must match corpus.READERS

# Documents whose filename names the paper's own object of study are never
# auto-excluded. Chile publishes its sex/gender/orientation measurement reviews
# as "informe de resultados ...", which the exclusion rules would otherwise drop
# — and those are direct evidence for the gender-disaggregation indicators.
SALIENT = re.compile(
    r"g[eé]nero|sexo|orientaci[oó]n|gender|\bsex\b|women|mujeres|k[oö]n|geschlecht|diversidad",
    re.I,
)

# Checked in order. Exclusions come first so that "boletín metodológico" is read
# as a bulletin, not as methodology — but SALIENT overrides them.
RULES: list[tuple[str, str, re.Pattern]] = [
    ("X", "bulletin, tabulation or press material", re.compile(
        r"bolet[ií]n|bulletin|comunicado|\bcp[_-]|nota.?de.?prensa|press.?release|tabulado|"
        r"cuadro|presentaci[oó]n|pres[-_]|resultado|result|empalme|proyecci[oó]n|"
        r"\bseries\b|s[eé]ries?.?(hist|empalm|est|nal)|"
        r"tr[ií]ptico|folheto|brochure|faq|leggimi|readme|descrizionefile|indicador|"
        r"principales|informe.?sobre.?cifras|estratificaci[oó]n.?del.?marco|anexo|annex|allegato",
        re.I)),
    ("G", "names an interviewer or field manual", re.compile(
        r"manual.?(del?.?)?(encuestador|entrevistador|campo|recolecci[oó]n)|"
        r"instructivo|interviewer|field.?manual|intervieweranweisung",
        re.I)),
    # (?<!en) keeps "Encuesta" out of C: it contains the substring "cuest", so a
    # bare /cuest/ made every Spanish filename with the word for "survey" a
    # questionnaire — including ENEMDU_Metodologia_Encuesta_Nacional...pdf.
    ("C", "names a questionnaire or form", re.compile(
        r"(?<!en)cuest|formulario|question[aá]rio|questionario|questionnaire|"
        r"vragenlijst|fragebogen|frageb|enk[aä]t|ced-\d|modello.?di.?rilevazione",
        re.I)),
    ("M", "names methodology, technical notes or sample design", re.compile(
        r"metodolog|methodolog|m[eé]thodolog|metodolog[ií]a|nota.?(t[eé]cnica|metodol)|"
        r"notametodologica|ficha.?t[eé]cnica|consideraciones|dise[nñ]?i?o.?(de.?)?muestra|"
        r"dise[nñ]o.?muestral|marco.?(maestro.?de.?)?muestreo|sampling|sample.?design|"
        r"quality.?report|qualit|methoden|definities|definici|background.?and.?methodology|"
        r"documentatie|documento.?metodol|especificaci|nt[_-]|conceptos|muestras",
        re.I)),
]

CODE_LABELS = framework_mod.source_codes()

# Tokens that carry wave identity rather than document identity: removing them
# lets four years of FichaTecnica.pdf collapse into one group.
WAVE_WORDS = re.compile(
    r"\b(trim(estre)?|trimester|quarter|primo|secondo|terzo|quarto|primer|segundo|tercer|"
    r"cuarto|1er|2do|3er|3ro|4to|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|"
    r"diciembre|anual|annual|partir|hasta|desde|gesti[oó]n|durante|def|final|act|v)\b",
    re.I,
)
HASH_PREFIX = re.compile(r"^[0-9a-f]{5}-")  # INE Paraguay prefixes every download
QUARTER_WORDS = {"primo": 1, "primer": 1, "1er": 1, "secondo": 2, "segundo": 2, "2do": 2,
                 "terzo": 3, "tercer": 3, "3er": 3, "3ro": 3, "quarto": 4, "cuarto": 4, "4to": 4}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def clean_name(rel: Path) -> str:
    """Readable form of a filename: URL-decoded enough to match rules, hash prefix gone."""
    name = HASH_PREFIX.sub("", rel.name)
    return re.sub(r"%[0-9a-fA-F]{2}", " ", name)


@dataclass
class Candidate:
    rel: Path                       # path relative to doc_dir
    code: str = ""                  # C / M / G / X (excluded) / "" (unresolved)
    reason: str = ""
    year: int = 0
    quarter: int = 0
    version: int = 0
    tokens: frozenset = field(default_factory=frozenset)
    words: frozenset = field(default_factory=frozenset)  # from the extracted TEXT
    superseded: list[str] = field(default_factory=list)
    size: int = 0  # estimated tokens, filled in only for documents that survive
    pinned: bool = False  # named in manual_overrides; never dropped by wave or cap

    @property
    def vintage(self) -> tuple[int, int, int]:
        return (self.year, self.quarter, self.version)

    @property
    def label(self) -> str:
        return str(self.rel)


def read_vintage(cand: Candidate) -> None:
    """Date a document from its filename and the folders above it.

    Separators are flattened to spaces first: `_` is a word character, so a naive
    \\b2003\\b never matches metodologia_eph_continua_2003.pdf.
    """
    raw = strip_accents(f"{cand.rel.parent}/{clean_name(cand.rel)}").lower()
    hay = re.sub(r"[^a-z0-9]+", " ", raw)

    # YYYYMM (Ecuador: 202603_Metodologia_ENEMDU.pdf) before plain years, so the
    # month is not mistaken for a separate figure.
    years = []
    ym = re.search(r"\b(20[0-3]\d)(0[1-9]|1[0-2])\b", hay)
    if ym:
        years.append(int(ym.group(1)))
        cand.quarter = (int(ym.group(2)) - 1) // 3 + 1
    # Lookarounds rather than \b: ONS glues the wave to the name, as in
    # volume2octtodec2025.pdf, where \b2025\b never matches.
    years += [int(y) for y in re.findall(r"(?<!\d)(19[7-9]\d|20[0-3]\d)(?!\d)", hay)]
    cand.year = max(years, default=0)

    if not cand.quarter:
        # 2t20 and 1_trim_2019 are both common in Latin American naming
        m = re.search(r"\b([1-4])t(\d{2})\b", hay)
        if m:
            cand.quarter = int(m.group(1))
            cand.year = cand.year or 2000 + int(m.group(2))
    if not cand.year:
        # A two-digit year glued to the end of the name: INE Spain ships
        # epacues21.pdf and epacues05.pdf. Undated, both read as the same vintage
        # and the lineage test never compared them. Three letters before the
        # digits, so a version like _v21 is not taken for a year; same 1970-2039
        # span as the four-digit pattern.
        stem = strip_accents(clean_name(cand.rel.with_suffix(""))).lower()
        m = re.search(r"[a-z]{3}(\d{2})$", stem)
        if m:
            yy = int(m.group(1))
            if yy <= 39:
                cand.year = 2000 + yy
            elif yy >= 70:
                cand.year = 1900 + yy
    if not cand.quarter:
        # "2º Trim" normalises to "2o trim" — NFKD turns the ordinal sign into an o
        for pat in (r"\bt([1-4])\b", r"\bq([1-4])\b", r"\b([1-4])\s*o?\s*(?:trim|t)\b"):
            m = re.search(pat, hay)
            if m:
                cand.quarter = int(m.group(1))
                break
    if not cand.quarter:
        for word, q in QUARTER_WORDS.items():
            if re.search(rf"\b{word}\b", hay):
                cand.quarter = q
                break
    if not cand.quarter:
        m = re.search(r"\b(i{1,3}|iv)[_ ]?(?:trim|_)", hay)
        if m:
            cand.quarter = ROMAN[m.group(1)]

    m = re.search(r"\bv(?:ersi[oó]n)?[_ ]?(\d{1,2})\b", hay)
    if m:
        cand.version = int(m.group(1))


def group_tokens(cand: Candidate) -> None:
    """Identity of the document with its wave stripped out, as a token set."""
    base = strip_accents(clean_name(cand.rel.with_suffix(""))).lower()
    base = re.sub(r"\d+", " ", base)
    base = re.sub(r"[^a-z]+", " ", base)
    base = WAVE_WORDS.sub(" ", base)
    cand.tokens = frozenset(t for t in base.split() if len(t) > 2)


OVERRIDES = ROOT / "config" / "manual_overrides.json"


def load_overrides(country: str) -> dict:
    if not OVERRIDES.exists():
        return {}
    return json.loads(OVERRIDES.read_text(encoding="utf-8")).get(country, {})


def apply_overrides(cands: list[Candidate], over: dict) -> int:
    """Re-apply the human decisions this run must not overwrite.

    A regenerated map used to lose them: paraguay's wrong-survey exclusions and
    argentina's hand-split PDF both came back on the first re-run after the
    content-dedup change. Rules cannot reach either — one needs to know that EUT
    and MICS are different surveys, the other that a file was cut down by hand —
    so they are declared in config/manual_overrides.json and replayed here.
    """
    excl = over.get("exclude", {})
    pin = over.get("pin", {})  # filename -> code; survives wave selection and the cap
    hit = 0
    for cand in cands:
        why = excl.get(cand.label)
        if why:
            cand.code = "X"
            cand.reason = f"[manual] {why}"
            hit += 1
        elif cand.label in pin:
            cand.code = pin[cand.label]
            cand.pinned = True
            cand.reason = f"[manual] pinned to {cand.code}"
            hit += 1
    for name in list(excl) + list(pin):
        if not any(c.label == name for c in cands):
            print(f"  !! override names a file that is not in doc_dir: {name}")
    return hit


def words_of(text: str) -> frozenset:
    """A text's identity as a set of words: accents stripped, lower case, letters
    only, words of three letters or more. Shared with run_eval, which compares the
    repeats of a record indicator with the same measure the triage uses."""
    base = re.sub(r"[^a-z]+", " ", strip_accents(text or "").lower())
    return frozenset(w for w in base.split() if len(w) > 2)


def content_words(doc_dir: Path, text_dir: Path, cands: list[Candidate]) -> None:
    """Identity of the document from its extracted TEXT, as a word set.

    Filenames are not documents. Agencies name files however they like, so
    word-overlap between two names says nothing reliable about whether the two
    contents are the same — and `group_tokens` above got it wrong in both
    directions. It over-merged Mexico's `Cuestionario_de_Ocupación` and
    `Cuestionario_sociodemográfico`, which share nearly every name token but are
    the two halves of one instrument, and deleted half the questionnaire. It
    under-merged the ONS `volume2*` files, four vintages of one questionnaire
    published under names that share almost nothing, and kept 550k tokens of
    near-duplicate.

    Extraction is local `pdftotext` and already cached under data/processed/text,
    so this costs nothing and hits no API.
    """
    from corpus import cache_path, extract

    for cand in cands:
        try:
            text = extract(doc_dir / cand.rel, cache_path(text_dir, cand.rel))
        except SystemExit:  # unreadable file; fall back to the filename
            text = ""
        cand.words = words_of(text)


def classify(cand: Candidate) -> None:
    hay = strip_accents(clean_name(cand.rel)) + " " + strip_accents(str(cand.rel.parent))
    salient = bool(SALIENT.search(hay))
    for code, why, pattern in RULES:
        if not pattern.search(hay):
            continue
        if code == "X" and salient:
            cand.reason = "filename mentions gender/sex — never auto-excluded, needs a look"
            return  # leave unresolved
        cand.code = code
        cand.reason = why
        return
    if salient:
        cand.reason = "filename mentions gender/sex but no rule matched"


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


# Content overlap that makes two DIFFERENT-vintage documents the same lineage —
# waves of one questionnaire that drifted apart, not two documents. Set from a
# measured gap that is unusually clean, so the exact value hardly matters:
#
#   0.143  argentina Vivienda vs Individual   two parts of one instrument
#   0.178  argentina Hogar vs Individual      two parts of one instrument
#   0.184  mexico Ocupación vs sociodemográ   two halves of one instrument
#   ------------------------------------------ nothing lands in between
#   0.699  bolivia questionnaire v4 vs v9     waves
#   0.785  paraguay EPHC 2023 T4 vs 2026 T1   waves
#
# The vintage guard carries most of the weight: same vintage means not waves of
# each other, whatever the overlap. Only different-vintage pairs reach this test.
LINEAGE_CONTENT = 0.50


def pick_waves(cands: list[Candidate], threshold: float, cap: int,
               name_threshold: float = 0.55) -> tuple[list[Candidate], list[Candidate]]:
    """Keep the newest document of each group; return (kept, superseded).

    Two documents are the same document if EITHER holds:

      content  their extracted text overlaps >= `threshold`. Catches the ONS
               volume2 files, four vintages of one questionnaire published under
               names that share almost nothing.
      lineage  their filenames overlap >= `name_threshold` AND their vintages
               differ. Catches waves that drifted apart in content — Paraguay's
               EPHC questionnaire scores 0.72 across 2020..2026 — which the
               content test alone would keep as four separate documents,
               contradicting the wave policy.

    The vintage guard is what makes the lineage test safe. Without it, filename
    similarity merged Mexico's `Cuestionario_de_Ocupación` and
    `Cuestionario_sociodemográfico` — two halves of ONE instrument, same vintage,
    nearly identical names — and deleted half the questionnaire. Same vintage
    means not waves of each other, whatever the names suggest.

    Grouping is still a heuristic, so every displaced document is named in the
    winner's `superseded` list and written to the review sheet. Trimming a wrong
    choice is then a one-line edit, not a re-run.
    """
    pinned = [c for c in cands if c.pinned]
    cands = [c for c in cands if not c.pinned]
    order = sorted(cands, key=lambda c: (c.vintage, c.label), reverse=True)
    kept: list[Candidate] = []
    dropped: list[Candidate] = []
    for cand in order:
        home = score = None
        for k in kept:
            # Content when both sides have text; filenames only as a fallback, so
            # a scanned PDF that extracts to nothing does not Jaccard to 0 or 1
            # against everything.
            if k.words and cand.words:
                s, how = jaccard(k.words, cand.words), "content"
            else:
                s, how = jaccard(k.tokens, cand.tokens), "filename"
            if s < threshold:
                name = jaccard(k.tokens, cand.tokens)
                content = jaccard(k.words, cand.words) if (k.words and cand.words) else 0.0
                if k.vintage != cand.vintage and (name >= name_threshold
                                                  or content >= LINEAGE_CONTENT):
                    s, how = max(name, content), "same lineage, later wave"
                else:
                    continue
            home, score, basis = k, s, how
            break
        if home is None:
            kept.append(cand)
        else:
            home.superseded.append(cand.label)
            cand.reason = (f"earlier wave, superseded by {home.label} "
                           f"({basis} similarity {score:.3f})")
            dropped.append(cand)
    # Pinned documents are a human decision, so neither wave selection nor the
    # cap may displace them; they occupy slots ahead of everything else. The
    # slots they take are counted here, or the documents they push out are
    # neither kept nor recorded and vanish from the map.
    slots = max(cap - len(pinned), 0)
    for cand in kept[slots:]:
        cand.reason = (f"beyond --max-per-source {cap}; newest {cap} kept for this source"
                       if not pinned else
                       f"beyond --max-per-source {cap}; {len(pinned)} pinned and the newest "
                       f"{slots} kept for this source")
        dropped.append(cand)
    return pinned + kept[:slots], dropped


def measure(doc_dir: Path, text_dir: Path, kept: list[Candidate]) -> int:
    """Fill in each document's real token count and return the group total.

    Sizing matters because a file count is not a cost: one ONS volume 2 is ~119k
    tokens while three Argentine forms together are 38k. Nothing is dropped here —
    which document to cut when a corpus will not fit is a research decision, not
    something to settle by sort order, so the caller only warns.

    count_tokens is a free endpoint, so this is exact rather than a chars/4 guess.
    Whitespace-heavy questionnaires make that guess overshoot by about a third,
    since the tokenizer compresses the runs of spaces that pdftotext -layout emits.
    """
    from corpus import cache_path, extract

    for cand in kept:
        text = extract(doc_dir / cand.rel, cache_path(text_dir, cand.rel))
        cand.size = count_tokens(text)
    return sum(c.size for c in kept)


_CLIENT = None


def count_tokens(text: str) -> int:
    global _CLIENT
    if not text.strip():
        return 0
    try:
        if _CLIENT is None:
            import anthropic
            _CLIENT = anthropic.Anthropic()
        return _CLIENT.messages.count_tokens(
            model="claude-sonnet-5", messages=[{"role": "user", "content": text}]
        ).input_tokens
    except Exception:
        return len(text) // 4  # offline fallback, overshoots on questionnaires


def title_page(path: Path, chars: int = 1500) -> str:
    """First page only — enough to see a title, cheap enough to send for every file."""
    if path.suffix.lower() == ".docx":
        from corpus import docx_to_text
        return docx_to_text(path)[:chars]
    proc = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", "1", str(path), "-"],
        capture_output=True, text=True,
    )
    return " ".join(proc.stdout.split())[:chars]


ASK = """You are triaging the documentation of a national household survey for a study of
whether survey instruments are designed with feminist intent. Assign each document
exactly one code from its title page:

C = the data collection instrument itself (questionnaire, form, showcard)
M = methodological notes, technical reports, sampling or sample design, concept definitions
G = interviewer or field manuals — instructions to the person asking the questions
X = none of the above (results, bulletins, press releases, tabulations, codebooks of
    an already-collected dataset, file descriptions, spliced series)

A document that reports measurement of sex, gender or sexual orientation *as a
methodological question* is M, not X, even if it is titled "results" or "report".

Answer with one JSON array, one object per document, no prose:
[{"i": 0, "code": "M", "why": "six words"}]

Documents:
"""


CACHE = DRAFT_DIR / "titlepage_verdicts.json"


def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def save_cache(cache: dict) -> None:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                     encoding="utf-8")


def resolve_by_title_page(country: str, doc_dir: Path, unresolved: list[Candidate],
                          model: str, go: bool) -> None:
    """One call per country over the title pages of everything the rules missed.

    Verdicts are cached so that re-running after a rule change costs nothing.
    """
    import anthropic

    cache = load_cache()
    hits = [c for c in unresolved if f"{country}/{c.label}" in cache]
    for cand in hits:
        entry = cache[f"{country}/{cand.label}"]
        cand.code, cand.reason = entry["code"], entry["why"]
    todo = [c for c in unresolved if c not in hits]
    if hits:
        print(f"  title-page pass: {len(hits)} cached", end="")
        print(f", {len(todo)} to read" if todo else "")
    if not todo:
        return

    pages = []
    for i, cand in enumerate(todo):
        text = title_page(doc_dir / cand.rel)
        pages.append(f"[{i}] filename: {cand.label}\n    first page: {text or '(no extractable text)'}")
    prompt = ASK + "\n\n".join(pages)
    unresolved = todo

    client = anthropic.Anthropic()
    n = client.messages.count_tokens(
        model=model, messages=[{"role": "user", "content": prompt}]
    ).input_tokens
    print(f"  title-page pass: {len(unresolved)} documents, {n:,} input tokens", end="")
    if not go:
        print(" — dry run, add --go to classify them")
        return
    print(" — calling")

    reply = client.messages.create(
        model=model,
        max_tokens=64 * len(unresolved) + 256,
        messages=[{"role": "user", "content": prompt}],
    )
    # content may open with a thinking block, so take the text blocks specifically
    body = "".join(b.text for b in reply.content if b.type == "text")
    match = re.search(r"\[.*\]", body, re.S)
    if not match:
        print(f"  could not parse reply, leaving unresolved: {body[:200]}")
        return
    for item in json.loads(match.group(0)):
        i = item.get("i")
        if not isinstance(i, int) or not 0 <= i < len(unresolved):
            continue
        code = item.get("code", "")
        if code in {"C", "M", "G", "X"}:
            why = f"title page: {item.get('why', '').strip()}"
            unresolved[i].code = code
            unresolved[i].reason = why
            cache[f"{country}/{unresolved[i].label}"] = {"code": code, "why": why}
    save_cache(cache)


def survey_meta(country: str) -> dict:
    want = country.replace("_", " ").lower()
    for row in csv.DictReader(INVENTORY.open(encoding="utf-8")):
        if row["country"].lower() == want:
            return {"survey": f"{row['survey_name']} ({row['acronym']})",
                    "agency": row["stats_office"]}
    return {"survey": country, "agency": ""}


# Documents plus framework, instructions and room to answer have to fit one call.
SUBDIM_LIMIT = 170_000


def triage(country: str, threshold: float, cap: int, model: str, go: bool) -> dict:
    doc_dir = ROOT / "data" / "raw" / country / "documentacion"
    if not doc_dir.is_dir():
        sys.exit(f"No documentation folder: {doc_dir.relative_to(ROOT)}")

    cands: list[Candidate] = []
    non_textual: dict[str, int] = {}
    for path in sorted(doc_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(doc_dir)
        if path.suffix.lower() not in READABLE:
            ext = path.suffix.lower() or "(no extension)"
            non_textual[ext] = non_textual.get(ext, 0) + 1
            continue
        cand = Candidate(rel)
        classify(cand)
        read_vintage(cand)
        group_tokens(cand)
        cands.append(cand)

    over = load_overrides(country)
    n_over = apply_overrides(cands, over)  # before the title-page pass, so an
    # overridden file is never sent for classification

    content_words(doc_dir, ROOT / "data" / "processed" / "text" / country, cands)

    print(f"\n{country}: {len(cands)} readable documents, "
          f"{sum(non_textual.values())} non-textual files")

    unresolved = [c for c in cands if not c.code]
    if unresolved:
        resolve_by_title_page(country, doc_dir, unresolved, model, go)

    sources: dict[str, dict] = {}
    excluded: dict[str, str] = {}
    review: dict[str, list[Candidate]] = {}
    text_dir = ROOT / "data" / "processed" / "text" / country
    sizes: dict[str, int] = {}
    for code in ("C", "M", "G"):
        pool = [c for c in cands if c.code == code]
        kept, dropped = pick_waves(pool, threshold, cap)
        sizes[code] = measure(doc_dir, text_dir, kept)
        review[code] = sorted(pool, key=lambda c: (c.vintage, c.label), reverse=True)
        spec: dict = {"label": CODE_LABELS[code], "files": [c.label for c in kept]}
        if not kept:
            spec["missing_note"] = (
                f"No document of type {code} ({CODE_LABELS[code]}) was found in the "
                f"collected corpus for {country}. Indicators routed to {code} are "
                "reported as source_missing, not as not_evidenced."
            )
        sources[code] = spec
        for cand in dropped:
            excluded[cand.label] = cand.reason

    for cand in cands:
        if cand.code == "X":
            excluded[cand.label] = cand.reason or "not instrument documentation"

    still_open = {c.label: c.reason or "no rule matched, title page not read"
                  for c in cands if not c.code}

    cmap = {
        "country": country,
        **survey_meta(country),
        "doc_dir": str((doc_dir).relative_to(ROOT)),
        "wave_policy": "most recent available wave only, consistent with the Argentina anchor",
        "sources": sources,
        "estimated_tokens": {**sizes, "C+M": sizes["C"] + sizes["M"]},
        "excluded": excluded,
        "unclassified": still_open,
        **({"manual_review": {"source": "config/manual_overrides.json",
                              "applied": n_over,
                              "note": over.get("note", "")}} if over else {}),
        "non_textual": dict(sorted(non_textual.items(), key=lambda kv: -kv[1])),
    }

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFT_DIR / f"corpus_map.{country}.json"
    out.write_text(json.dumps(cmap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DRAFT_DIR / f"review.{country}.md").write_text(
        render_review(country, cmap, review, still_open), encoding="utf-8")

    for code in ("C", "M", "G"):
        files = sources[code]["files"]
        state = ", ".join(files) if files else "NONE -> source_missing"
        print(f"  [{code}] ~{sizes[code]:>7,} tok  {state}")
    if still_open:
        print(f"  {len(still_open)} unclassified — see review.{country}.md")
    for code in ("C", "M", "G"):
        if sizes[code] > SUBDIM_LIMIT:
            print(f"  !! [{code}] alone is ~{sizes[code]:,} tokens — over the window. Not "
                  "fixable by call granularity; a document has to be cut or split.")
    if sizes["C"] + sizes["M"] > SUBDIM_LIMIT >= max(sizes["C"], sizes["M"]):
        print(f"  ! C+M is ~{sizes['C'] + sizes['M']:,} tokens — over the ~{SUBDIM_LIMIT:,} "
              "that fit one subdimension call, but each source fits alone: run this "
              "country with --mode indicator.")
    print(f"  -> {out.relative_to(ROOT)}")
    return cmap


def render_review(country: str, cmap: dict, review: dict, still_open: dict) -> str:
    L = [f"# Corpus triage — {country}", "",
         f"**{cmap['survey']}** — {cmap['agency']}  ",
         f"Wave policy: {cmap['wave_policy']}", "",
         "To change a choice, edit `corpus_map." + country + ".json`: move a filename between "
         "`sources.<code>.files` and `excluded`. Every displaced document is listed below, "
         "so nothing has to be re-derived.", ""]
    for code in ("C", "M", "G"):
        chosen = set(cmap["sources"][code]["files"])
        L += [f"## [{code}] {cmap['sources'][code]['label']}", ""]
        if not review[code]:
            L += ["_No candidate found. Indicators routed here become `source_missing`._", ""]
            continue
        L += [f"Selected: **~{cmap['estimated_tokens'][code]:,} tokens**", "",
              "| | document | tokens | year | Q | v | why |", "|---|---|---|---|---|---|---|"]
        for c in review[code]:
            mark = "**IN**" if c.label in chosen else "out"
            L.append(f"| {mark} | `{c.label}` | {f'{c.size:,}' if c.size else ''} | "
                     f"{c.year or ''} | {c.quarter or ''} | {c.version or ''} | {c.reason} |")
        L.append("")
    sizes = cmap["estimated_tokens"]
    total = sizes["C+M"]
    L += ["## Corpus size", "", f"C+M is **~{total:,} tokens** against a ~{SUBDIM_LIMIT:,} "
          "usable window.", ""]
    oversized = [c for c in ("C", "M", "G") if sizes[c] > SUBDIM_LIMIT]
    if oversized:
        L.append("Source " + " and ".join(f"**{c}** (~{sizes[c]:,})" for c in oversized) +
                 " exceeds the window on its own. Call granularity cannot fix that — a "
                 "document has to be cut or split. The tables above show what each costs.")
    elif total > SUBDIM_LIMIT:
        L.append("Each source fits alone but not together, so this country runs with "
                 "`--mode indicator` rather than `--mode subdimension`.")
    else:
        L.append("Fits a single subdimension call, so both granularities are available.")
    L.append("")
    if still_open:
        L += ["## Unclassified — need your call", "",
              "| document | note |", "|---|---|"]
        L += [f"| `{k}` | {v} |" for k, v in sorted(still_open.items())]
        L.append("")
    if cmap["non_textual"]:
        counts = ", ".join(f"{n}× {ext}" for ext, n in cmap["non_textual"].items())
        L += ["## Not readable as text", "", counts,
              "", "_Left in place; the corpus map ignores them._", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country")
    ap.add_argument("--all", action="store_true", help="every country with a documentation folder")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--threshold", type=float, default=0.80,
                    help="content similarity above which two files are the same document. "
                         "0.80 because there is a clean empirical gap: every true duplicate "
                         "scores >=0.83, while bolivia's genuinely different CUESTIONARIO V9 "
                         "vs v4 pair scores 0.692 and must survive. The old 0.55 was tuned "
                         "for filename tokens and does not transfer to text.")
    ap.add_argument("--max-per-source", type=int, default=4)
    ap.add_argument("--go", action="store_true",
                    help="make the title-page calls (default is a free dry run)")
    args = ap.parse_args()

    if args.all:
        countries = sorted(p.name for p in (ROOT / "data" / "raw").iterdir()
                           if (p / "documentacion").is_dir()
                           and any((p / "documentacion").rglob("*.pdf")))
    elif args.country:
        countries = [args.country]
    else:
        sys.exit("Pass --country <name> or --all")

    for country in countries:
        triage(country, args.threshold, args.max_per_source, args.model, args.go)


if __name__ == "__main__":
    main()
