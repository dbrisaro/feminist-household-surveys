"""Which countries are in the study, and which were dropped.

Single source of truth, imported by every figure. Kept in one module because
the scope appears in more than one display and a figure that disagrees with
another about who is in the sample is worse than no figure.

Scope decision of 2026-08-20, settled. The study compares national household
surveys over time, so the line is drawn where national microdata exists.
`scripts/microdata_years.py` found no waves at all for germany, netherlands,
portugal and sweden, and a single year (2024) for france. Those five are out.

Checked against each office's website in October 2026. Germany, the
Netherlands, Portugal and Sweden release labour force survey microdata only to
eligible institutions: the Mikrozensus Scientific Use File goes to EU-based
institutions only, CBS through Remote Access, INE Portugal to researchers
accredited in the Portuguese science system, and SCB after a confidentiality
review. France is different: INSEE publishes Enquête Emploi files openly for
2003-2025, so France is out because only the 2024 file was collected, not
because the microdata are unavailable.

Eurostat public-use files do not change the picture: they are the harmonised
EU LFS, not the national instrument, so they cannot evidence national
questionnaire design, which is what the paper is about.

The reason strings below are what the caption prints, so keep them short and
free of em dashes.
"""

from __future__ import annotations

EXCLUDED: dict[str, str] = {
    "france": "only the 2024 file collected",
    "germany": "SUF for EU institutions only",
    "netherlands": "CBS Remote Access only",
    "portugal": "accredited national researchers only",
    "sweden": "SCB approved research access only",
}

# ADM0_A3, not ISO_A3: Natural Earth records France's ISO_A3 as "-99".
ISO3: dict[str, str] = {
    "argentina": "ARG", "bolivia": "BOL", "brazil": "BRA", "chile": "CHL",
    "colombia": "COL", "ecuador": "ECU", "france": "FRA", "germany": "DEU",
    "italy": "ITA", "mexico": "MEX", "netherlands": "NLD", "paraguay": "PRY",
    "peru": "PER", "portugal": "PRT", "spain": "ESP", "sweden": "SWE",
    "united_kingdom": "GBR", "uruguay": "URY",
}

LABEL = {"united_kingdom": "United Kingdom"}


def is_excluded(country: str) -> bool:
    return country in EXCLUDED


def included(countries) -> list[str]:
    return [c for c in countries if c not in EXCLUDED]


def label(country: str) -> str:
    return LABEL.get(country, country.replace("_", " ").title())
