"""
Download questionnaires (C), methodology (M) and interviewer guides (G) for
every country in the study.

The first generation of scrapers went after microdata and methodology pages, so
C and G were mostly never requested: of 25 scrapers, 12 searched for a
methodology term, 7 for a questionnaire term and 2 for an interviewer manual.
That is why five countries reached the triage step with no questionnaire at all.
This scraper covers all three families for every country from one registry, and
records — in the registry itself — what an agency does not publish reachably, so
a gap is never mistaken for something nobody tried.

Four kinds of source appear, because the agencies differ:

    direct   an exact URL that is known to serve the document
    page     an HTML page whose PDF links are crawled and classified
    ftp      an Apache/nginx directory listing
    catalog  a NADA/ANDA catalogue's `related-materials` tab (INEGI, DANE,
             INE Uruguay all run this software)

Classification is shared with the triage step via routing.py and always reads
the link *text* as well as the filename, because several agencies publish under
opaque names (INEGI's questionnaire is `c_bas_v7.pdf`).

    python scripts/scraping/scrape_docs.py --list             # classify only
    python scripts/scraping/scrape_docs.py --country mexico
    python scripts/scraping/scrape_docs.py                    # everything
    python scripts/scraping/scrape_docs.py --coverage         # gap report
"""

import argparse
import csv
import html
import re
import subprocess
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, unquote, quote, urlsplit, urlunsplit

from routing import classify
from utils import get_raw_dir, setup_logger

log = setup_logger("scrape_docs")

UA = "Mozilla/5.0 (compatible; feminist-survey-research/1.0; academic)"

# Transport is curl, not requests, for two reasons found the hard way. INEGI and
# DANE publish AAAA records that do not answer, so requests blocks on IPv6 until
# it times out while curl falls back to v4. INE Uruguay serves an incomplete
# certificate chain that curl completes from the system trust store. Neither is
# a reason to weaken verification — curl still verifies.
CURL = ["curl", "-sSL", "--ipv4", "-A", UA]

BLOB = "?__blob=publicationFile"


def _destatis(name: str) -> str:
    return (f"https://www.destatis.de/DE/Methoden/Qualitaet/Qualitaetsberichte/"
            f"Bevoelkerung/{name}.pdf{BLOB}")


# ---------------------------------------------------------------------------
# The registry. `blocked` documents a family that exists but cannot be fetched,
# with the reason; it is printed by --coverage and never silently ignored.
# ---------------------------------------------------------------------------
COUNTRIES: dict[str, dict] = {

    "argentina": {
        "survey": "Encuesta Permanente de Hogares (EPH) — INDEC",
        "sources": [{"kind": "page", "url": "https://www.indec.gob.ar/indec/web/Institucional-Indec-BasesDeDatos"}],
        "blocked": {
            "C": "INDEC serves EPH documentation from a JS-rendered page. The "
                 "/ftp/cuadros/menusuperior/eph/ paths answer 200 with the "
                 "site's HTML shell rather than a PDF, so they cannot be used; "
                 "the 3 questionnaires on disk were downloaded by hand.",
            "M": "same JS-rendered page as C; the 5 methodology PDFs on disk "
                 "were downloaded by hand.",
            "G": "INDEC does not publish the EPH interviewer manual.",
        },
    },

    "bolivia": {
        "survey": "Encuesta Continua de Empleo (ECE) — INE Bolivia",
        "sources": [{"kind": "page", "url": "https://www.ine.gob.bo/index.php/metadatos-y-microdatos/"}],
        "blocked": {
            "C": "ine.gob.bo is JS-rendered with no direct file links; the 13 "
                 "questionnaires on disk (v1–v9 by period) were obtained by hand.",
            "G": "not published.",
        },
    },

    "brazil": {
        "survey": "Pesquisa Nacional por Amostra de Domicílios Contínua (PNAD-C) — IBGE",
        "sources": [
            {"kind": "ftp", "url": "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Notas_metodologicas/"},
            {"kind": "ftp", "url": "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Nota_Tecnica/"},
        ],
        "blocked": {
            "C": "the whole PNAD-C FTP tree holds dictionaries, inputs and "
                 "deflators only; the questionnaire is served from the "
                 "JS-rendered documentation tab on www.ibge.gov.br.",
            "G": "not published.",
        },
    },

    "chile": {
        "survey": "Encuesta Nacional de Empleo (ENE) — INE Chile",
        "sources": [
            {"kind": "page", "url": "https://bancodatosene.ine.cl/"},
            # Chile publishes its sex/gender/orientation measurement work here;
            # it is the strongest positive evidence in the sample.
            {"kind": "page", "url": "https://www.ine.gob.cl/estadisticas-por-tema/sociedad-y-condiciones-de-vida/publicaciones-y-metodologia-con-enfoque-de-genero"},
        ],
        "blocked": {"G": "not published."},
    },

    "colombia": {
        "survey": "Gran Encuesta Integrada de Hogares (GEIH) — DANE",
        "sources": [{"kind": "catalog", "url": "https://microdatos.dane.gov.co/index.php/catalog/853/"}],
        "blocked": {
            "M": "the catalogue's methodology entries redirect to "
                 "dane.isolucion.co, a login portal. DSO-GEIH-MET-001-V11.pdf "
                 "and DSO-GEIH-FME-001-V11.pdf are already on disk and are the "
                 "same documents.",
        },
    },

    "ecuador": {
        "survey": "Encuesta Nacional de Empleo, Desempleo y Subempleo (ENEMDU) — INEC",
        "sources": [
            {"kind": "page", "url": "https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/"},
            {"kind": "page", "url": "https://www.ecuadorencifras.gob.ec/enemdu-trimestral/"},
        ],
    },

    "france": {
        "survey": "Enquête Emploi en continu (EE) — INSEE",
        "sources": [
            {"kind": "page", "url": f"https://www.insee.fr/fr/metadonnees/source/operation/{code}/documentation-methodologique"}
            for code in ("s2227", "s2223", "s2127")
        ],
        "blocked": {
            "C": "INSEE operation pages expose only /documentation-methodologique "
                 "and /documentation-qualite; no questionnaire endpoint exists.",
            "G": "not published.",
        },
    },

    "germany": {
        "survey": "Mikrozensus (MZ) — Destatis",
        "sources": [
            {"kind": "direct", "code": "M", "url": _destatis(f"mikrozensus-{y}")}
            for y in (2024, 2023, 2022)
        ] + [
            {"kind": "direct", "code": "M", "url": f"https://www.destatis.de/DE/Methoden/Demografische-Regionale-Standards/Downloads/demografische-standards-2024.pdf{BLOB}"},
        ],
        "blocked": {
            "C": "the Mikrozensus Fragebogen is served from erhebungsportal."
                 "estatistik.de, which is JS-rendered.",
            "G": "not published.",
            "microdata": "MZ microdata 2016–2024 is released only through the "
                         "FDZ Safe Centre or Remote Execution, which require "
                         "German institutional affiliation. No SUF or Campus "
                         "File exists for these years.",
        },
    },

    "italy": {
        "survey": "Rilevazione sulle Forze di Lavoro (RCFL) — ISTAT",
        "sources": [{"kind": "page", "url": "https://www.istat.it/microdati/rilevazione-sulle-forze-di-lavoro-dati-trasversali-trimestrali/"}],
        "blocked": {
            "G": "not published.",
            "C": "questionnaires ship inside the longitudinal microdata ZIPs "
                 "rather than as standalone PDFs; 83 are already on disk.",
        },
    },

    "mexico": {
        "survey": "Encuesta Nacional de Ocupación y Empleo (ENOE) — INEGI",
        "sources": [{"kind": "catalog", "url": "https://www.inegi.org.mx/rnm/index.php/catalog/1121/"}],
        "blocked": {
            "M": "'Cómo se hace la ENOE' resolves to an inegi.org.mx/app/"
                 "biblioteca ficha whose API is in maintenance.",
        },
    },

    "netherlands": {
        "survey": "Enquête Beroepsbevolking (EBB) — CBS",
        "sources": [{"kind": "page", "url": "https://www.cbs.nl/-/media/cbs/onze-diensten/methoden/"}],
        "blocked": {
            "G": "not published.",
            "C": "cbs.nl serves the vragenlijst PDFs from a JS-rendered media "
                 "listing; the 6 on disk were resolved by hand.",
        },
    },

    "paraguay": {
        "survey": "Encuesta Permanente de Hogares Continua (EPHC) — INE Paraguay",
        "sources": [{"kind": "page", "url": "https://www.ine.gov.py/microdato/encuesta-permanente-de-hogares-continua-ephc-trimestral-2022-2024"}],
        "blocked": {
            "M": "not published separately from the results bulletins.",
            "G": "the only manual published is for the EUT time-use survey, a "
                 "different instrument; it must not be mapped as EPHC's G.",
        },
    },

    "peru": {
        "survey": "Encuesta Nacional de Hogares (ENAHO) — INEI",
        "sources": [{"kind": "page", "url": "https://www.inei.gob.pe/estadisticas/metodologias/"}],
        "blocked": {
            "G": "not reachable: inei.gob.pe listings are JS-rendered and the "
                 "ENAHO manual is not in the microdata packages already held.",
        },
    },

    "portugal": {
        "survey": "Inquérito ao Emprego (IE) — INE Portugal",
        "sources": [{"kind": "direct", "code": "C", "name": "IE_serie2021_questionario",
             "url": "https://webinq.ine.pt/Public/DownloadFiles.aspx?idFile=5391"}],
        "blocked": {
            "M": "INE Portugal publishes IE methodology through the SMI "
                 "metadata system, which requires a session.",
            "G": "not published.",
        },
    },

    "spain": {
        "survey": "Encuesta de Población Activa (EPA) — INE España",
        "sources": [
            {"kind": "direct", "code": "C", "url": "https://www.ine.es/inebaseDYN/epa30308/docs/epacues21.pdf"},
            {"kind": "page", "url": "https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736176918&menu=metodologia&idp=1254735976595"},
        ],
        "blocked": {"G": "not published."},
    },

    "sweden": {
        "survey": "Arbetskraftsundersökningarna (AKU) — SCB",
        "sources": [{"kind": "page", "url": "https://www.scb.se/am0401"}],
        "blocked": {"G": "not published."},
    },

    "united_kingdom": {
        "survey": "Labour Force Survey (LFS) — ONS",
        "sources": [{"kind": "page", "url": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/methodologies/labourforcesurveyuserguidance"}],
        "blocked": {"G": "ONS publishes interviewer instructions only inside the "
                         "user-guide volumes, not as a separate document."},
    },

    "uruguay": {
        "survey": "Encuesta Continua de Hogares (ECH) — INE Uruguay",
        "sources": [
            {"kind": "catalog", "url": "https://www4.ine.gub.uy/Anda5/index.php/catalog/767/"},
            {"kind": "catalog", "url": "https://www4.ine.gub.uy/Anda5/index.php/catalog/730/"},
        ],
        "blocked": {"G": "not published."},
    },
}


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def encode(url: str) -> str:
    """Percent-encode the path. INE Chile links its questionnaire with a literal
    space in the filename, which curl rejects outright."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%")))


def fetch(url: str, dest: Path | None = None, timeout: int = 60,
          attempts: int = 3) -> bytes | None:
    """GET a URL, retrying on failure.

    INDEC and ONS both drop connections when a run requests several files back
    to back — the first pass lost 20 documents that way, all of which fetch
    fine on their own. So failure here means "failed three times, spaced out",
    not "unavailable", and a document that still fails is worth investigating.
    """
    cmd = CURL + ["--max-time", str(timeout), encode(url)]
    if dest is not None:
        cmd += ["-o", str(dest)]
    for attempt in range(1, attempts + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 30)
            if proc.returncode == 0:
                return b"" if dest is not None else proc.stdout
            reason = f"curl {proc.returncode}"
        except subprocess.TimeoutExpired:
            reason = "timed out"
        if attempt < attempts:
            time.sleep(2 * attempt)
    log.warning(f"    {reason} after {attempts} tries: {url[:88]}")
    return None


# ---------------------------------------------------------------------------
# Link discovery, one function per source kind
# ---------------------------------------------------------------------------

LINK = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)

# The ONS user-guidance page still links superseded 2007–2011 volumes through
# the National Archives mirror, and every one of those links is dead. They are
# earlier waves of documents we already hold, so they are dropped rather than
# retried.
DEAD_MIRROR = re.compile(r"webarchive\.nationalarchives\.gov\.uk", re.I)
DOCUMENT = re.compile(r"\.(pdf|docx?)(\?|$)", re.I)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def from_page(url: str) -> list[dict]:
    """Crawl one HTML page and keep the document links that classify."""
    body = fetch(url)
    if not body:
        return []
    found = []
    for m in LINK.finditer(body.decode("utf-8", "replace")):
        href, label = m.group(1), _text(m.group(2))
        if not DOCUMENT.search(href):
            continue
        target = urljoin(url, href)
        if DEAD_MIRROR.search(target):
            continue
        # Filename carries the signal when the anchor text is "Download".
        code = classify(f"{label} {unquote(Path(href.split('?')[0]).name)}")
        if code:
            found.append({"code": code, "title": label or Path(href).name, "url": target})
    return found


def from_ftp(url: str) -> list[dict]:
    """Apache-style directory listing: no link text, so the filename decides."""
    body = fetch(url)
    if not body:
        return []
    found = []
    for m in re.finditer(r'href="([^"?/][^"]*)"', body.decode("utf-8", "replace")):
        href = m.group(1)
        if not DOCUMENT.search(href):
            continue
        code = classify(unquote(href))
        if code:
            found.append({"code": code, "title": unquote(href), "url": urljoin(url, href)})
    return found


def from_catalog(url: str) -> list[dict]:
    """A NADA/ANDA `related-materials` tab.

    The resource title and its download link sit in sibling blocks with no
    shared container, so the pairing is positional: a title claims the first
    document link that appears after it.
    """
    body = fetch(url.rstrip("/") + "/related-materials", timeout=90)
    if not body:
        return []
    page = re.sub(r"<script.*?</script>", "", body.decode("utf-8", "replace"), flags=re.S | re.I)
    token = re.compile(
        r'<span class="resource-info".*?id="(\d{3,})".*?>(.*?)</span>'
        r'|href="([^"]*(?:/download/\d+|\.pdf|\.docx?))"',
        re.S | re.I,
    )
    found, pending = [], None
    for m in token.finditer(page):
        if m.group(1):
            pending = _text(m.group(2)) or None
        elif pending:
            code = classify(pending)
            if code:
                href = m.group(3)
                found.append({
                    "code": code,
                    "title": pending,
                    "url": href if href.startswith("http") else urljoin(url, href),
                })
            pending = None
    return found


def from_direct(spec: dict) -> list[dict]:
    # Some agencies serve documents from a query string (INE Portugal's
    # DownloadFiles.aspx?idFile=), leaving no usable name in the path, so a
    # source may carry an explicit one.
    name = spec.get("name") or unquote(Path(spec["url"].split("?")[0]).name)
    return [{"code": spec["code"], "title": name, "url": spec["url"]}]


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def slugify(title: str, code: str, url: str, prefer_title: bool = False) -> str:
    # Catalogue entries carry a curated title while their filenames are opaque
    # (INEGI's questionnaire is `c_bas_v7.pdf`), so there the title wins. Using
    # different rules for the same document is what produced two copies of every
    # Mexican file when this scraper and its predecessor both ran.
    stem = title if prefer_title else Path(unquote(url.split("?")[0])).stem
    if not re.fullmatch(r"[\w.\- ]{4,}", stem) or stem.isdigit():
        stem = title  # opaque or numeric URL: fall back to the human title
    stem = re.sub(r"[^\w\s-]", "", stem, flags=re.UNICODE).strip()
    stem = re.sub(r"\s+", "_", stem)[:70].strip("_")
    return f"{code}_{stem}.pdf"


def download(item: dict, doc_dir: Path) -> str:
    dest = doc_dir / item["filename"]
    if dest.exists():
        return "skipped"
    if fetch(item["url"], dest=dest, timeout=180) is None or not dest.exists():
        dest.unlink(missing_ok=True)
        return "failed"
    time.sleep(1.0)  # these agencies throttle bursts; stay polite
    head = dest.read_bytes()[:4]
    # Stale links are answered with an HTML error page, which curl still writes.
    if head not in (b"%PDF", b"PK\x03\x04"):
        dest.unlink()
        return "failed"
    return "downloaded"


def collect(country: str) -> list[dict]:
    entry = COUNTRIES[country]
    log.info(f"=== {country} — {entry['survey']} ===")
    items, seen = [], set()
    for spec in entry["sources"]:
        kind = spec["kind"]
        log.info(f"  [{kind}] {spec['url'][:88]}")
        if kind == "direct":
            found = from_direct(spec)
        elif kind == "page":
            found = from_page(spec["url"])
        elif kind == "ftp":
            found = from_ftp(spec["url"])
        elif kind == "catalog":
            found = from_catalog(spec["url"])
        else:
            raise ValueError(f"unknown source kind {kind!r}")
        for item in found:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            item["filename"] = slugify(item["title"], item["code"], item["url"],
                                       prefer_title=(kind == "catalog"))
            items.append(item)
    return items


def report(country: str, items: list[dict]) -> None:
    blocked = COUNTRIES[country].get("blocked", {})
    for code in ("C", "M", "G"):
        hits = [i for i in items if i["code"] == code]
        if hits:
            log.info(f"  [{code}] {len(hits)}")
            for h in hits[:6]:
                log.info(f"        {h['title'][:76]}")
            if len(hits) > 6:
                log.info(f"        … {len(hits) - 6} more")
        elif code in blocked:
            log.info(f"  [{code}] none — {blocked[code]}")
        else:
            log.info(f"  [{code}] none")


def save_manifest(country: str, items: list[dict], results: dict[str, str]) -> None:
    path = get_raw_dir(country) / "documentacion" / "manifest_docs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source_code", "filename", "title", "url", "result", "downloaded_on"])
        w.writeheader()
        for i in items:
            w.writerow({
                "source_code": i["code"], "filename": i["filename"], "title": i["title"],
                "url": i["url"], "result": results.get(i["filename"], ""),
                "downloaded_on": date.today().isoformat(),
            })


def coverage() -> None:
    """Print what each country can and cannot supply, without fetching."""
    print(f"{'country':<17}{'C':<4}{'M':<4}{'G':<4} blocked")
    for country, entry in sorted(COUNTRIES.items()):
        blocked = entry.get("blocked", {})
        cells = "".join(f"{('—' if c in blocked else '·'):<4}" for c in "CMG")
        print(f"{country:<17}{cells} {', '.join(sorted(blocked)) or '-'}")
    print("\n·  reachable by this scraper      —  documented as not fetchable")
    print("Run without --coverage to see how many documents each source yields.")


def run() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", choices=sorted(COUNTRIES), action="append")
    ap.add_argument("--list", action="store_true", help="classify only, download nothing")
    ap.add_argument("--coverage", action="store_true", help="print the gap table and exit")
    args = ap.parse_args()

    if args.coverage:
        coverage()
        return

    totals = {"downloaded": 0, "skipped": 0, "failed": 0}
    for country in args.country or sorted(COUNTRIES):
        items = collect(country)
        report(country, items)
        if args.list:
            continue
        doc_dir = get_raw_dir(country) / "documentacion"
        doc_dir.mkdir(parents=True, exist_ok=True)
        results = {}
        for item in items:
            results[item["filename"]] = download(item, doc_dir)
            totals[results[item["filename"]]] += 1
        save_manifest(country, items, results)
        log.info("  " + ", ".join(f"{v} {k}" for k, v in
                                  sorted(__count(results).items())))

    if not args.list:
        log.info("TOTAL — " + ", ".join(f"{k}: {v}" for k, v in totals.items()))


def __count(results: dict[str, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in results.values():
        out[v] = out.get(v, 0) + 1
    return out


if __name__ == "__main__":
    run()
