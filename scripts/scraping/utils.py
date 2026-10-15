import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; feminist-survey-research/1.0; academic)"
}

# File extensions for documentation vs microdata
DOC_EXTENSIONS = {".pdf", ".doc", ".docx"}
MICRODATA_EXTENSIONS = {".csv", ".sav", ".dta", ".xlsx", ".xls", ".zip", ".rar", ".7z"}
ALL_EXTENSIONS = DOC_EXTENSIONS | MICRODATA_EXTENSIONS

# Keywords to identify relevant documents across languages
DOC_KEYWORDS = {
    "questionnaire": ["cuestionario", "questionnaire", "fragebogen", "enquête", "questionário"],
    "methodology": ["metodolog", "methodology", "methodolog", "méthodolog", "methodiek"],
    "sampling": ["muestral", "sampling", "muestreo", "stichproef", "sondage", "amostra"],
    "design": ["diseño de registro", "record design", "diseño", "record layout"],
    "microdata": ["microdato", "microdata", "base de datos", "base datos", "dataset",
                  "datos abiertos", "open data", "microdonnée", "mikrodaten",
                  "individual data", "raw data", "datos individuales"],
    "codebook": ["codebook", "diccionario", "libro de códigos", "registro", "variable",
                 "code book", "data dictionary"],
}


def setup_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def get_raw_dir(country: str) -> Path:
    base = Path(__file__).parent.parent.parent / "data" / "raw"
    dest = base / country.lower().replace(" ", "_")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def get_page(url: str, session: requests.Session | None = None) -> BeautifulSoup:
    s = session or requests.Session()
    response = s.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content, "lxml")


def download_file(
    url: str,
    dest_path: Path,
    session: requests.Session | None = None,
    delay: float = 1.5,
) -> bool:
    s = session or requests.Session()
    try:
        response = s.get(url, headers=HEADERS, timeout=60, stream=True)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        time.sleep(delay)
        return True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to download {url}: {e}")
        return False


def is_relevant(text: str) -> str | None:
    """Return the matched category name if text matches any doc keyword, else None."""
    text_lower = text.lower()
    for category, keywords in DOC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return None
