"""Extract survey documentation to text and route it by source code (C/M/G).

Each framework indicator declares which document family answers it, so the
evidence corpus is assembled per call rather than once for the whole run.
Extraction is cached under data/processed/text/<country>/ and is idempotent.

    python scripts/llm/corpus.py --country argentina --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Doc:
    """One extracted source document."""

    source_code: str
    doc: str
    text_path: Path
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def manifest(self) -> dict:
        return {
            "source_code": self.source_code,
            "doc": self.doc,
            "text_file": str(self.text_path.relative_to(ROOT)),
            "chars": len(self.text),
            "sha256": self.sha256,
        }


class MissingSource(Exception):
    """Raised when a source code has no documents for this country."""


def load_map(country: str) -> dict:
    path = ROOT / "config" / f"corpus_map.{country}.json"
    if not path.exists():
        sys.exit(f"No corpus map for {country!r}: expected {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def cache_path(text_dir: Path, rel: Path) -> Path:
    """Where a document's extracted text is cached, keyed on its path relative
    to doc_dir rather than on its filename.

    Keying on the stem alone collides: INEI ships FichaTecnica.pdf under four
    different year folders, and the second one mapped would silently read the
    first one's cached text — wrong evidence, no error. Flat corpora keep their
    existing cache files, because there the relative path *is* the filename.
    """
    return text_dir / ("__".join(rel.with_suffix("").parts) + ".txt")


def pdf_to_text(path: Path) -> str:
    """-layout preserves the column structure that questionnaire PDFs rely on;
    a reflowed extraction scrambles question codes."""
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"pdftotext failed on {path.name}: {proc.stderr.strip()}")
    return proc.stdout


def docx_to_text(path: Path) -> str:
    """Interviewer manuals are the scarcest source family (G) and Paraguay's is
    only published as .docx, so it gets a reader rather than an exclusion."""
    try:
        import docx  # python-docx
    except ImportError:
        sys.exit(f"{path.name} is .docx and python-docx is not installed: pip install python-docx")
    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:  # manuals put response categories in tables
        for row in table.rows:
            parts.append("\t".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


READERS = {".pdf": pdf_to_text, ".docx": docx_to_text}


def extract(src_path: Path, out_path: Path) -> str:
    """Extract one document to text, cached and idempotent."""
    if out_path.exists():
        return out_path.read_text(encoding="utf-8")
    reader = READERS.get(src_path.suffix.lower())
    if reader is None:
        sys.exit(
            f"No reader for {src_path.suffix!r} ({src_path.name}). "
            f"Readable formats: {', '.join(sorted(READERS))}. "
            "Spreadsheets and result tabulations do not belong in the corpus — "
            "record them under 'excluded' in the corpus map instead."
        )
    text = reader(src_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text


def load_docs(country: str) -> dict[str, list[Doc]]:
    """Extract every mapped document, grouped by source code."""
    cmap = load_map(country)
    doc_dir = ROOT / cmap["doc_dir"]
    text_dir = ROOT / "data" / "processed" / "text" / country
    docs: dict[str, list[Doc]] = {}
    for code, spec in cmap["sources"].items():
        docs[code] = []
        for fname in spec["files"]:
            src = doc_dir / fname
            if not src.exists():
                sys.exit(f"Missing file listed in corpus map: {src.relative_to(ROOT)}")
            out = cache_path(text_dir, Path(fname))
            docs[code].append(Doc(code, fname, out, extract(src, out)))
    return docs


def build(country: str, codes: tuple[str, ...], docs: dict[str, list[Doc]] | None = None):
    """Assemble the evidence corpus for a set of source codes.

    Returns (blocks, manifest). `blocks` is one text block per document, ready to
    be placed at the head of the user turn. Raises MissingSource if any requested
    code has no documents for this country — the caller reports that indicator as
    source_missing instead of spending a call on it.
    """
    docs = docs if docs is not None else load_docs(country)
    selected: list[Doc] = []
    group_end: dict[str, int] = {}
    for code in sorted(set(codes)):  # sorted => deterministic prefix => cache hits
        if not docs.get(code):
            raise MissingSource(code)
        selected.extend(docs[code])
        group_end[code] = len(selected) - 1  # index of this group's last block

    blocks = [
        f"=== SOURCE DOCUMENT [{d.source_code}] {d.doc} ===\n\n{d.text}" for d in selected
    ]
    return blocks, [d.manifest for d in selected], group_end


# The evidence blocks of one call must leave room for the system prompt, the task
# block and the model's own output. Measured tails run 3-6k tokens, so this is the
# budget for documents alone, not the whole context window.
SHARD_BUDGET_TOKENS = 170_000

# Token density varies far more than expected between documents -- 4.3 chars per
# token for prose methodology, 5.9 for a whitespace-heavy questionnaire that
# pdftotext -layout pads into columns. So a shared chars-per-token constant would
# either overshoot the window or waste a third of it. Each document's own ratio is
# measured once, then applied with this margin to absorb drift within the document.
SHARD_SAFETY = 0.90


def paginate(text: str) -> list[str]:
    """Cut extracted text into the largest natural units available.

    pdftotext emits a form feed per page, which is the cleanest cut there is: a
    page boundary never lands in the middle of a question, so a shard never shows
    the model half a grid. .docx carries no pages, so interviewer manuals in that
    format fall back to blank-line paragraph breaks.
    """
    parts = text.split("\f") if "\f" in text else re.split(r"\n\s*\n", text)
    return [p for p in parts if p.strip()]


def split_doc(doc: Doc, budget_tokens: int, count_tokens) -> list[tuple[str, int, int]]:
    """Split one document into consecutive parts, each inside `budget_tokens`.

    Returns [(text, part_number, n_parts)]. A document that already fits comes
    back as a single part, which is the common case and costs one free
    count_tokens call.

    Splitting is a last resort and only ever applies to a document that cannot fit
    a call on its own -- Mexico's 452k-token Manual del entrevistador, the UK's
    ONS volumes. The alternative was to cut such a document down to size, but a
    corpus pruned to fit makes every `not_evidenced` verdict rest on documents
    that were never searched, which is exactly the inference the study must not
    make. Sharding pays in calls instead of in validity.
    """
    total = count_tokens(doc.text)
    if total <= budget_tokens:
        return [(doc.text, 1, 1)]

    per_char = total / max(len(doc.text), 1)
    char_budget = int(budget_tokens * SHARD_SAFETY / per_char)

    parts, cur, cur_len = [], [], 0
    for page in paginate(doc.text):
        if cur and cur_len + len(page) > char_budget:
            parts.append("\f".join(cur))
            cur, cur_len = [], 0
        cur.append(page)
        cur_len += len(page)
    if cur:
        parts.append("\f".join(cur))

    # A single page larger than the budget cannot be cut on a page boundary. It is
    # rare enough to be worth failing loudly on rather than silently truncating.
    for part in parts:
        if count_tokens(part) > budget_tokens:
            sys.exit(
                f"{doc.doc}: a single page exceeds the {budget_tokens:,}-token shard "
                "budget and cannot be split on a page boundary."
            )
    return [(text, i, len(parts)) for i, text in enumerate(parts, 1)]


def build_shards(country, codes, docs, count_tokens, budget_tokens=SHARD_BUDGET_TOKENS):
    """Assemble the evidence corpus as one or more shards that each fit a call.

    Returns a list of (blocks, manifest, group_end) triples with the same shape
    `build` returns, so a caller that ignores sharding sees no change: a corpus
    that fits yields exactly one shard, identical to `build`'s output.

    Sharding is per *document*, not per source group. Documents are packed in
    sorted-code order and a new shard opens when the next document would not fit;
    an oversized document is split across shards of its own. Verdicts from the
    shards of one indicator are merged by the caller.
    """
    docs = docs if docs is not None else load_docs(country)
    selected: list[Doc] = []
    for code in sorted(set(codes)):
        if not docs.get(code):
            raise MissingSource(code)
        selected.extend(docs[code])

    # (block, manifest, source_code) in the order they must be presented.
    units: list[tuple[str, dict, str]] = []
    for d in selected:
        for text, part, n_parts in split_doc(d, budget_tokens, count_tokens):
            tag = f" (part {part} of {n_parts})" if n_parts > 1 else ""
            units.append((
                f"=== SOURCE DOCUMENT [{d.source_code}] {d.doc}{tag} ===\n\n{text}",
                {**d.manifest, "part": part, "n_parts": n_parts},
                d.source_code,
            ))

    shards, cur, cur_tokens = [], [], 0
    for block, man, code in units:
        n = count_tokens(block)
        if cur and cur_tokens + n > budget_tokens:
            shards.append(cur)
            cur, cur_tokens = [], 0
        cur.append((block, man, code))
        cur_tokens += n
    if cur:
        shards.append(cur)

    out = []
    for shard in shards:
        blocks = [b for b, _, _ in shard]
        manifest = [m for _, m, _ in shard]
        group_end = {}
        for i, (_, _, code) in enumerate(shard):
            group_end[code] = i  # index of this group's last block within the shard
        out.append((blocks, manifest, group_end))
    return out


def cache_key(codes: tuple[str, ...]) -> str:
    """Calls sharing a cache key share a byte-identical document prefix."""
    return "+".join(sorted(set(codes)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="argentina")
    ap.add_argument("--check", action="store_true", help="count tokens per corpus (free API call)")
    args = ap.parse_args()

    cmap = load_map(args.country)
    docs = load_docs(args.country)

    print(f"{cmap['survey']} — {cmap['agency']}\n")
    for code, spec in cmap["sources"].items():
        got = docs[code]
        if not got:
            print(f"  [{code}] {spec['label']}: NO DOCUMENTS -> indicators become source_missing")
            continue
        print(f"  [{code}] {spec['label']}")
        for d in got:
            print(f"        {d.doc:<64} {len(d.text):>9,} chars")

    if args.check:
        import anthropic

        client = anthropic.Anthropic()
        print("\n  token counts (count_tokens is free, no credits consumed):")
        for codes in [("C",), ("M",), ("C", "M")]:
            try:
                blocks, _, _ = build(args.country, codes, docs)
            except MissingSource as e:
                print(f"    {cache_key(codes):<6} unavailable (missing source {e})")
                continue
            n = client.messages.count_tokens(
                model="claude-sonnet-5",
                messages=[{"role": "user", "content": "\n\n".join(blocks)}],
            ).input_tokens
            print(f"    {cache_key(codes):<6} {n:>9,} tokens")


if __name__ == "__main__":
    main()
