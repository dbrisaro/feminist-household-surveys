"""Draw the figures of the paper built from the final run (Figures 2 to 4, B1, B2, D1 and E1), with captions.

Reads <dir>/runs.json and, for each run, report/results_indicators.csv,
report/cost_summary.csv, raw.jsonl and manifest.json, plus
<dir>/figures/tokens_by_source.json for the size of each country's corpus by
source type. Writes the figures to <dir>/figures/ and <dir>/figures/CAPTIONS.md,
with the captions of the paper's figures, with the paper's numbering. Figure 1
is drawn by scripts/final_run_territory_figures.py.

    python scripts/llm/final_run_figures.py --dir outputs/final_run_2026-10-08

tokens_by_source.json is Gemini's countTokens over each document's text file, as
the run used it (sha256 checked against the manifest). countTokens is free and
generates nothing; `--count-tokens` refreshes the file, everything else is offline.
"""
import argparse
import hashlib
import json
import re
import sys
import textwrap
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import dotenv_values
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "llm"))
import framework as F  # noqa: E402

# --- palette ------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
# The two chromatic slots are carried over unchanged from the validated verdict
# palette (light, surface #fcfcfb): they pass lightness, chroma, CVD separation,
# normal-vision floor and 3:1 contrast. Do not substitute by eye.
LABEL_COLOR = {
    "met": "#2a78d6",                  # categorical slot 1
    "partially_met": "#eb6834",        # slot 2 — a different hue, not a tint of
                                       # met: partial is its own finding
    "unmet": "#898781",                # muted ink: the capability is absent, which
                                       # is not a category — deliberately achromatic
    "insufficient_evidence": "#e1e0d9",  # chrome: our gap, not the survey's
    "not_labelled": "#e1e0d9",
    # A cell no run has filled: this model never assessed this indicator. Not a
    # finding, not even a failed one — the pooled table is ragged whenever the
    # models were pointed at different scopes, which is the normal state while a
    # framework is being worked through one subdimension at a time.
    "not_run": SURFACE,
}
LABEL_INK = {
    "met": "#ffffff", "partially_met": "#ffffff", "unmet": "#ffffff",
    "insufficient_evidence": MUTED, "not_labelled": MUTED, "not_run": MUTED,
}

mpl.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": AXIS,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9, "axes.titlesize": 11, "figure.dpi": 130,
})

# A PNG looked at on screen needs well above CSS pixel size; the PDF is vector and unaffected.
PNG_DPI = 220

LABELLED = ("criterion", "criterion_list")
LABELS = ("met", "partially_met", "unmet")
EUROPE = {"spain", "italy", "united_kingdom"}
EXCLUSIONS = ("explicit", "treated_as_other", "not_mentioned")
HATCH = "////"

ELEMENTS = {  # (es, en), keyed by the framework's element names
    "responsibility": ("Responsabilidad", "Responsibility"),
    "performance": ("Realización", "Performance"),
    "magnitude": ("Magnitud", "Magnitude"),
    "paid work": ("Trabajo pago", "Paid work"),
    "unpaid work": ("Trabajo no pago", "Unpaid work"),
    "leisure": ("Ocio", "Leisure"),
    "self-care": ("Autocuidado", "Self-care"),
    "neutral_anchor_term": ("Término neutro", "Neutral anchor term"),
    "explicit_selection_rule": ("Regla de selección explícita", "Explicit selection rule"),
    "rule_not_sex_age_authority": ("Regla sin sexo, edad ni autoridad",
                                   "Rule not based on sex, age or authority"),
    "respondent_separate_or_any_adult": ("Respondente aparte o cualquier adulto",
                                         "Respondent separate or any adult"),
    "economic_maintenance": ("Sostén económico", "Economic maintenance"),
    "labor_burden": ("Carga de trabajo", "Labour burden"),
    "property_asset_control": ("Control de bienes y propiedad", "Property and asset control"),
    "decision_making": ("Toma de decisiones", "Decision-making"),
    "member_to_member_relationships": ("Relaciones entre todos los miembros",
                                       "Member-to-member relationships"),
    "extended_ties": ("Vínculos ampliados", "Extended ties"),
    "multiple_household_criteria": ("Criterios para separar hogares",
                                    "Criteria for multiple households"),
    "sub_units": ("Subunidades", "Sub-units"),
    "caregiving_relationships": ("Relaciones de cuidado", "Caregiving relationships"),
    "de_jure_vs_de_facto": ("De jure o de facto", "De jure vs de facto"),
    "unpartnered_mother_child_units": ("Unidades madre-hijos sin pareja",
                                       "Unpartnered mother-child units"),
    "women_maintained_by_provider": ("Hogares sostenidos por mujeres",
                                     "Women-maintained households"),
    "mother_child_unit_activity": ("Actividad de la unidad madre-hijos",
                                   "Mother-child unit activity"),
}

TEXT = {
    "en": {
        "country": {"argentina": "Argentina", "bolivia": "Bolivia", "chile": "Chile",
                    "colombia": "Colombia", "ecuador": "Ecuador", "italy": "Italy",
                    "mexico": "Mexico", "paraguay": "Paraguay", "peru": "Peru",
                    "spain": "Spain", "united_kingdom": "United Kingdom", "uruguay": "Uruguay"},
        "ind": {
            "d1_i1": "Sex variable", "d1_i2": "Gender identity variable",
            "d1_i3": "Instructions for recording sex or gender",
            "d1_i4": "Terms for persons and kinship",
            "d2_i1": "Domestic or care work module",
            "d2_i2": "Responsibility, performance and magnitude",
            "d2_i3": "Unpaid work in the activity category",
            "d2_i4": "Domestic work recorded per person",
            "d2_i5": "Supervision or availability to care",
            "d3_i1": "Time allocation across activities",
            "d3_i2": "Time in paid work, unpaid work, leisure and self-care",
            "d4_i1": "Definition of headship", "d4_i2": "Method for identifying the head",
            "d4_i3": "Reference person and respondent",
            "d4_i4": "Dimensions of headship by member",
            "d4_i5": "Relationships and household delimitation",
            "d4_i6": "Types of female-headed households",
        },
        "sub": {"d1": "Gender-diverse disaggregation", "d2": "Unpaid care work",
                "d3": "Time use", "d4": "Household composition and headship"},
        "label": {"met": "met", "partially_met": "partially met", "unmet": "unmet",
                  "insufficient_evidence": "no source", "not_labelled": "no label"},
        "region": {"latam": "Latin America", "europe": "Europe"},
        "not_asked": "not asked",
        "stab_head": "Vote stability", "sim_head": "Text similarity (record)",
        "unstable": "Stability below 1",
        "measured": "Measured", "not_unanimous": "Vote not unanimous",
        "d4_axis": "Countries in which the element is true (of {n})",
        "excl_long": {"explicit": "Excluded explicitly", "treated_as_other": "Treated as another category",
                      "not_mentioned": "Not mentioned"},
        "empty": "(empty)", "tokens_axis": "thousand tokens (Gemini)",
        "cost": "actual cost (USD)", "cache": "input from cache (%)",
        "split": "split calls", "failed": "failed parts or repetitions",
        "nonunan": "non-unanimous votes",
    },
}


def cap(s: str) -> str:
    """Sentence case for text drawn in a figure: the first letter upper-cased,
    the rest as written ("(empty)" -> "(Empty)"). Captions keep lower case in prose."""
    m = re.search(r"[^\W\d_]", s or "")
    return s[:m.start()] + s[m.start()].upper() + s[m.start() + 1:] if m else s


def elem_name(k, lang):
    return ELEMENTS[k][0 if lang == "es" else 1]


# --- data ------------------------------------------------------------------

def count_tokens(base: Path) -> None:
    """Refresh tokens_by_source.json with Gemini's countTokens, one call per document."""
    key = dotenv_values(ROOT / ".env").get("GEMINI_API_KEY_PAID")
    if not key:
        sys.exit("GEMINI_API_KEY_PAID not set in .env")

    def count(text):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-3.6-flash:countTokens?key={key}")
        req = urllib.request.Request(url, data=json.dumps({"contents": [{"parts": [{"text": text}]}]}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:  # a failure stops the script
            return json.load(r)["totalTokens"]

    runs = json.loads((base / "runs.json").read_text(encoding="utf-8"))
    out = {}
    for c, run in runs.items():
        m = json.loads((ROOT / "outputs" / c / "runs" / run / "manifest.json").read_text(encoding="utf-8"))
        seen = {}
        for d in m["corpus"]["documents"]:
            if d["doc"] in seen:
                continue
            text = (ROOT / d["text_file"]).read_text(encoding="utf-8")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != d["sha256"]:
                sys.exit(f"{c}: {d['doc']} changed since the run")
            seen[d["doc"]] = {"source_code": d["source_code"], "tokens": count(text),
                              "chars": len(text), "sha256": d["sha256"]}
        out[c] = {"run": run, "documents": seen}
    (base / "figures" / "tokens_by_source.json").write_text(json.dumps(
        {"model": "gemini-3.6-flash", "counted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "note": "Gemini countTokens (REST) over each document's text file as used by the run "
                 "(sha256 checked against manifest.json); free endpoint, no generation.",
         "countries": out}, ensure_ascii=False, indent=1), encoding="utf-8")


def load(base: Path):
    runs = json.loads((base / "runs.json").read_text(encoding="utf-8"))
    tokens = json.loads((base / "figures" / "tokens_by_source.json").read_text(encoding="utf-8"))
    D = {"ids": list(runs), "ind": {}, "docs": {}, "tokens": {}, "run": {}}
    for c, run in runs.items():
        path = ROOT / "outputs" / c / "runs" / run
        D["ind"][c] = pd.read_csv(path / "report" / "results_indicators.csv").set_index("indicator_id")
        held = defaultdict(set)
        for d in json.loads((path / "manifest.json").read_text(encoding="utf-8"))["corpus"]["documents"]:
            held[d["source_code"]].add(d["doc"])
        D["docs"][c] = {k: len(v) for k, v in held.items()}
        if tokens["countries"][c]["run"] != run:
            sys.exit(f"tokens_by_source.json is for another run of {c}; rerun with --count-tokens")
        tok = defaultdict(int)
        for d in tokens["countries"][c]["documents"].values():
            tok[d["source_code"]] += d["tokens"]
        D["tokens"][c] = dict(tok)
        calls = [json.loads(line) for line in (path / "raw.jsonl").open(encoding="utf-8")]
        calls = [r for r in calls if r.get("call") and not r.get("merged") and not r.get("rep_merged")]
        ind = D["ind"][c]
        D["run"][c] = {
            "cost": sum(r["cost_usd"] for r in calls),
            "cache": 100 * float(pd.read_csv(path / "report" / "cost_summary.csv")["pct_input_from_cache"].iloc[0]),
            "split": sum(1 for r in calls if r.get("n_shards", 1) > 1),
            "failed": sum(1 for r in calls if r.get("error")),
            "nonunan": int(((ind["type"] != "record") & (ind["stability"] < 1)).sum()),
        }
    D["order"] = F.load()["subdimensions"]
    D["share"] = element_shares(D)
    return D


def element_shares(D):
    """(country, subdimension) -> (true elements, elements). A criterion is one element."""
    share = {}
    for c in D["ids"]:
        for s in D["order"]:
            t = n = 0
            for i in s["indicators"]:
                r = D["ind"][c].loc[i["indicator_id"]]
                if r["type"] not in LABELLED or r["label"] not in LABELS:
                    continue
                if r["type"] == "criterion":
                    t, n = t + int(r["label"] == "met"), n + 1
                else:
                    t, n = t + int(r["n_elements_true"]), n + int(r["n_elements"])
            share[(c, s["subdimension_id"])] = (t, n)
    return share


def total_share(D, c):
    t = sum(D["share"][(c, s["subdimension_id"])][0] for s in D["order"])
    n = sum(D["share"][(c, s["subdimension_id"])][1] for s in D["order"])
    return t, n


def region(c):
    return "europe" if c in EUROPE else "latam"


def elements_of(r):
    if r["label"] not in LABELS or not isinstance(r["elements"], str):
        return None
    return json.loads(r["elements"])


# --- drawing helpers ---------------------------------------------------------

def no_frame(ax) -> None:
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)


def grouped_rows(groups):
    """[(heading, [row keys])] -> one row list with a heading row per group."""
    rows = []
    for head, keys in groups:
        rows.append(("head", head))
        rows += [("row", k) for k in keys]
    return rows


def row_labels(ax, rows, name, x=-0.25, size=8) -> None:
    for y, (kind, v) in enumerate(rows):
        if kind == "head":
            ax.text(x, y + 0.62, v, ha="right", va="center", fontsize=size + 0.5, color=INK, fontweight="bold")
        else:
            ax.text(x, y + 0.5, name(v), ha="right", va="center", fontsize=size, color=INK_2)


def cell(ax, x, y, face, hatch=None, text=None, ink=INK, w=1, edge=SURFACE, size=7):
    ax.add_patch(Rectangle((x, y), w, 1, facecolor=face, edgecolor=edge, linewidth=2, hatch=hatch))
    if text:
        ax.text(x + w / 2, y + 0.5, text, ha="center", va="center", fontsize=size, color=ink)


def grid_axes(ax, ncols, nrows):
    ax.set_xlim(0, ncols)
    ax.set_ylim(nrows, 0)
    ax.set_xticks([]), ax.set_yticks([])
    no_frame(ax)


def sorted_ids(D, T):
    return sorted(D["ids"], key=lambda c: T["country"][c])


# --- figures -----------------------------------------------------------------

WHITE = "#ffffff"
# The paper's palette, for the figures that go into the manuscript (Figures 1 to 4 and the appendix figures):
# light green, terracotta, salmon and light grey on white. The green is the lightest that still keeps it
# apart from the salmon for red-green colour blindness: any lighter and the two meet in lightness (validate_palette.js --pairs all on white, the four together: CVD dE 8.3, normal 15.7).
# Dark ink reads on all four.
GREEN, TERRACOTTA, SALMON, LIGHT_GREY = "#5ea86d", "#b85c45", "#f6ae91", "#ebebe8"
SOFT = {"met": GREEN, "partially_met": SALMON, "unmet": LIGHT_GREY}
# A criterion that is not met, by how the text leaves the item out; the strongest negative is the darkest.
EXCL_SOFT = {"met": GREEN, "explicit": TERRACOTTA, "treated_as_other": SALMON, "not_mentioned": LIGHT_GREY}
PAPER_REGION = {"latam": TERRACOTTA, "europe": GREEN}


def by_elements_met(D, T):
    """Countries from the most elements met to the fewest; equal counts in alphabetical order."""
    return sorted(D["ids"], key=lambda c: (-total_share(D, c)[0], T["country"][c]))


def fig_labels_ranked(D, T, out):
    """Figure 2: the label of every ranked indicator by country, countries ordered by elements met, a dot on
    every cell whose vote was not unanimous (stability below 1; for a criterion list, the mean over its elements)."""
    cs = by_elements_met(D, T)
    groups = [(T["sub"][s["subdimension_id"]],
               [i["indicator_id"] for i in s["indicators"] if i["type"] in LABELLED]) for s in D["order"]]
    rows = grouped_rows(groups)
    # Upright headers: a column is as wide as the longest word of a country name at this size, and a
    # name longer than that (United Kingdom, Reino Unido) wraps onto a second line above its count.
    fig, ax = plt.subplots(figsize=(0.66 * len(cs) + 4.3, 0.34 * len(rows) + 2.0), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    seen, dots = set(), []
    for y, (kind, i) in enumerate(rows):
        if kind == "head":
            continue
        for x, c in enumerate(cs):
            r = D["ind"][c].loc[i]
            lab = r["label"]
            seen.add(lab)
            chrome = lab not in LABELS
            txt = (f"{int(r['n_elements_true'])}/{int(r['n_elements'])}"
                   if r["type"] == "criterion_list" and not chrome and pd.notna(r["n_elements"]) else None)
            cell(ax, x, y, SOFT.get(lab, LABEL_COLOR.get(lab, WHITE)), HATCH if chrome else None, txt,
                 INK if lab in SOFT else LABEL_INK[lab], edge=WHITE, size=8.5)
            if pd.notna(r["stability"]) and r["stability"] < 1:
                dots.append((x + 0.84, y + 0.24))
    if dots:
        ax.scatter(*zip(*dots), s=20, facecolor=WHITE, edgecolor=INK, linewidth=0.8, zorder=5)
    grid_axes(ax, len(cs), len(rows))
    row_labels(ax, rows, lambda i: T["ind"][i], x=-0.12, size=9.5)
    for x, c in enumerate(cs):
        name = "\n".join(textwrap.wrap(T["country"][c], 9))
        ax.text(x + 0.5, -0.15, f"{name}\n({total_share(D, c)[0]}/{total_share(D, c)[1]})", ha="center",
                va="bottom", multialignment="center", fontsize=9.5, color=INK_2, linespacing=1.2)
    keys = [k for k in (*LABELS, "insufficient_evidence", "not_labelled") if k in seen]
    h = [Patch(facecolor=SOFT.get(k, LABEL_COLOR[k]), edgecolor=WHITE, hatch=None if k in LABELS else HATCH,
               label=cap(T["label"][k])) for k in keys]
    if dots:
        h.append(Line2D([], [], marker="o", linestyle="", markersize=5, markerfacecolor=WHITE,
                        markeredgecolor=INK, markeredgewidth=0.8, label=T["unstable"]))
    ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0, -0.012), ncol=len(h), frameon=False, fontsize=9.5,
              handlelength=1.4, columnspacing=1.6)
    fig.savefig(out / "fig2_results_by_country.png", dpi=PNG_DPI, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    print(f"-> {(out / 'fig2_results_by_country.png').relative_to(ROOT)}")


def two_lines(text):
    """Split a label into two lines at the space that makes the longer line shortest."""
    words = text.split()
    if len(words) < 2:
        return text
    k = min(range(1, len(words)), key=lambda k: max(len(" ".join(words[:k])), len(" ".join(words[k:]))))
    return " ".join(words[:k]) + "\n" + " ".join(words[k:])


def fig_d2_negatives(D, T, out):
    """Subdimension 2's four criteria, countries as rows in the order of Figure 2: measured, or how the text
    leaves the item out. d2_i2 is not drawn: a criterion list has no exclusion type per element. A dot marks
    a cell whose vote was not unanimous, on the value or on the exclusion type."""
    cs = by_elements_met(D, T)
    cols = [i["indicator_id"] for s in D["order"] if s["subdimension_id"] == "d2"
            for i in s["indicators"] if i["type"] == "criterion"]
    # Column headers sit upright on two lines, so a column has to be as wide as half its longest name.
    fig, ax = plt.subplots(figsize=(1.9 * len(cols) + 1.6, 0.36 * len(cs) + 1.8), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    seen, dots = set(), []
    for y, c in enumerate(cs):
        for x, i in enumerate(cols):
            r = D["ind"][c].loc[i]
            k = "met" if r["label"] == "met" else r["exclusion_type"]
            k = k if k in EXCL_SOFT else None
            seen.add(k)
            cell(ax, x, y, EXCL_SOFT.get(k, WHITE), None if k else HATCH, edge=WHITE)
            if (pd.notna(r["stability"]) and r["stability"] < 1) or \
               (pd.notna(r.get("exclusion_stability")) and r["exclusion_stability"] < 1):
                dots.append((x + 0.93, y + 0.24))
    if dots:
        ax.scatter(*zip(*dots), s=20, facecolor=WHITE, edgecolor=INK, linewidth=0.8, zorder=5)
    grid_axes(ax, len(cols), len(cs))
    for y, c in enumerate(cs):
        ax.text(-0.06, y + 0.5, T["country"][c], ha="right", va="center", fontsize=9.5, color=INK_2)
    for x, i in enumerate(cols):
        ax.text(x + 0.5, -0.2, two_lines(T["ind"][i]), ha="center", va="bottom", fontsize=9.5, color=INK_2,
                linespacing=1.25)
    names = {"met": T["measured"], **{e: T["excl_long"][e] for e in EXCLUSIONS}}
    h = [Patch(facecolor=EXCL_SOFT[k], edgecolor=WHITE, label=names[k]) for k in EXCL_SOFT if k in seen]
    if None in seen:
        h.append(Patch(facecolor=WHITE, edgecolor=MUTED, hatch=HATCH, label=cap(T["empty"])))
    if dots:
        h.append(Line2D([], [], marker="o", linestyle="", markersize=5, markerfacecolor=WHITE,
                        markeredgecolor=INK, markeredgewidth=0.8, label=T["not_unanimous"]))
    ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0, -0.012), ncol=3, frameon=False, fontsize=9.5,
              handlelength=1.4, columnspacing=1.6)
    fig.savefig(out / "fig3_unpaid_work_exclusions.png", dpi=PNG_DPI, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    print(f"-> {(out / 'fig3_unpaid_work_exclusions.png').relative_to(ROOT)}")


def d4_element_counts(D):
    """[(indicator_id, element, countries where it is true)] for subdimension 4's criterion lists."""
    out = []
    for i in list_indicators(D):
        if i["indicator_id"] not in {x["indicator_id"] for s in D["order"] if s["subdimension_id"] == "d4"
                                     for x in s["indicators"]}:
            continue
        for e in i["elements"]:
            yes = []
            for c in D["ids"]:
                els = elements_of(D["ind"][c].loc[i["indicator_id"]])
                assert els is not None and e in els, f"{c} {i['indicator_id']} {e}: element not answered"
                if els[e]:
                    yes.append(c)
            out.append((i["indicator_id"], e, yes))
    return out


def fig_d4_elements(D, T, lang, out):
    """Subdimension 4: in how many of the countries each element of the four criterion lists is true.
    One bar per element, a heading row per indicator, framework order."""
    counts = d4_element_counts(D)
    rows = grouped_rows([(T["ind"][i], [(i, e, len(yes)) for j, e, yes in counts if j == i])
                         for i in dict.fromkeys(i for i, _, _ in counts)])
    n = len(D["ids"])
    fig, ax = plt.subplots(figsize=(8.2, 0.33 * len(rows) + 1.0), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    tr = ax.get_yaxis_transform()
    for y, (kind, v) in enumerate(rows):
        if kind == "head":
            ax.text(-0.02, y + 0.15, v, transform=tr, ha="right", va="center", fontsize=10, color=INK,
                    fontweight="bold")
            continue
        _, e, k = v
        ax.barh(y, k, height=0.62, color=GREEN, zorder=3)
        ax.text(k + 0.15, y, str(k), ha="left", va="center", fontsize=9.5, color=INK)
        ax.text(-0.02, y, elem_name(e, lang), transform=tr, ha="right", va="center", fontsize=9.5, color=INK_2)
    ax.set_xlim(0, n + 0.8)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.set_xticks(range(0, n + 1, 3))
    ax.tick_params(axis="x", labelsize=9, length=0, colors=INK_2)
    ax.set_yticks([])
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("left", "top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.set_xlabel(T["d4_axis"].format(n=n), fontsize=9.5, color=INK)
    fig.savefig(out / "fig4_household_elements.png", dpi=PNG_DPI, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    print(f"-> {(out / 'fig4_household_elements.png').relative_to(ROOT)}")


# --- appendix figures (B1, B2, D1, E1) ----------------------------------------
# Drawn like Figures 2 to 4: white background, the paper palette, upright text, 9.5 pt.

# One hue, light to dark, for a 0-1 agreement score (validate_palette.js --ordinal on white: monotone,
# gaps >= 0.06, light end 2.03:1 against the surface).
GREEN_SEQ = LinearSegmentedColormap.from_list("paper_green", ["#8fc298", "#62a670", "#3a8249", "#1f4f28"])
SOURCE_SOFT = {"C": TERRACOTTA, "M": SALMON, "G": GREEN}


def upright_header(ax, names, size=9.5) -> None:
    """Column names on top of a cell grid, upright and centred, wrapped onto a second line when long."""
    for x, n in enumerate(names):
        ax.text(x + 0.5, -0.15, "\n".join(textwrap.wrap(n, 9)), ha="center", va="bottom",
                multialignment="center", fontsize=size, color=INK_2, linespacing=1.2)


def paper_legend(ax, handles, ncol=3, y=-0.012):
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, y), ncol=ncol, frameon=False, fontsize=9.5,
              handlelength=1.4, columnspacing=1.6)


def hatched(ax, x, y) -> None:
    """A white cell with grey hatching: the hatch takes the edge colour, so it cannot share the white gap."""
    ax.add_patch(Rectangle((x, y), 1, 1, facecolor=WHITE, edgecolor=WHITE, linewidth=2))
    ax.add_patch(Rectangle((x + 0.04, y + 0.06), 0.92, 0.88, facecolor="none", edgecolor=AXIS, linewidth=0,
                           hatch=HATCH))


def white_save(fig, path: Path) -> None:
    fig.savefig(path, dpi=PNG_DPI, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    print(f"-> {path.relative_to(ROOT)}")


def not_unanimous(r) -> bool:
    """The vote was split on the value, or, for a negative criterion, on the exclusion type."""
    return bool((pd.notna(r["stability"]) and r["stability"] < 1) or
                (pd.notna(r.get("exclusion_stability")) and r["exclusion_stability"] < 1))


def fig_tokens_paper(D, T, out):
    """B1: the corpus of each country in thousand tokens by source type."""
    cs = sorted_ids(D, T)
    fig, ax = plt.subplots(figsize=(7.2, 0.34 * len(cs) + 1.2), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    ys = np.arange(len(cs))
    seen = set()
    for y, c in zip(ys, cs):
        left = 0
        for code in "CMG":
            v = D["tokens"][c].get(code, 0) / 1000
            if v:
                seen.add(code)
                ax.barh(y, v, left=left, height=0.62, color=SOURCE_SOFT[code], edgecolor=WHITE, linewidth=1.5)
            left += v
        ax.text(left + 4, y, f"{left:,.0f}", ha="left", va="center", fontsize=9.5, color=INK_2)
    ax.set_yticks(ys)
    ax.set_yticklabels([T["country"][c] for c in cs], fontsize=9.5, color=INK_2)
    ax.set_ylim(len(cs) - 0.5, -0.5)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=9, length=0, colors=INK_2)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("left", "top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.set_xlim(0, max(sum(D["tokens"][c].values()) for c in cs) / 1000 * 1.12)
    ax.set_xlabel(cap(T["tokens_axis"]), fontsize=9.5, color=INK)
    paper_legend(ax, [Patch(facecolor=SOURCE_SOFT[k], edgecolor=WHITE, label=k) for k in "CMG" if k in seen],
                 y=-0.13)
    white_save(fig, out / "figB1_tokens_by_source.png")


def fig_run_paper(D, T, out):
    """B2: the run by country, one panel per measure."""
    cs = sorted_ids(D, T)
    panels = [("cost", "{:.2f}", 0), ("cache", "{:.1f}", 0), ("split", "{:d}", 5), ("failed", "{:d}", 5),
              ("nonunan", "{:d}", 5)]
    fig, axes = plt.subplots(1, len(panels), figsize=(1.95 * len(panels) + 1.6, 0.34 * len(cs) + 1.3),
                             sharey=True, facecolor=WHITE)
    ys = np.arange(len(cs))
    for ax, (key, fmt, floor) in zip(axes, panels):
        ax.set_facecolor(WHITE)
        vals = [D["run"][c][key] for c in cs]
        top = max(max(vals), floor) or 1
        ax.barh(ys, vals, height=0.62, color=GREEN)
        for y, v in zip(ys, vals):
            ax.text(v + top * 0.04, y, fmt.format(v), ha="left", va="center", fontsize=9, color=INK_2)
        ax.set_xlim(0, top * 1.5)
        ax.set_xticks([])
        for sp in ("left", "top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel(textwrap.fill(cap(T[key]), 16), fontsize=9.5, color=INK)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([T["country"][c] for c in cs], fontsize=9.5, color=INK_2)
    axes[0].set_ylim(len(cs) - 0.5, -0.5)
    fig.subplots_adjust(wspace=0.15)
    white_save(fig, out / "figB2_run_summary.png")


def fig_stability_paper(D, T, out):
    """D1: vote stability and record text similarity by indicator and country; countries in the
    order of Figure 2."""
    cs = by_elements_met(D, T)
    voted = [i["indicator_id"] for s in D["order"] for i in s["indicators"] if i["type"] != "record"]
    records = [i["indicator_id"] for s in D["order"] for i in s["indicators"] if i["type"] == "record"]
    rows = grouped_rows([(T["stab_head"], voted), (T["sim_head"], records)])
    fig, ax = plt.subplots(figsize=(0.66 * len(cs) + 4.3, 0.34 * len(rows) + 2.3), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    not_asked = 0
    for y, (kind, i) in enumerate(rows):
        if kind == "head":
            continue
        col = "stability" if i in voted else "text_similarity"
        for x, c in enumerate(cs):
            r = D["ind"][c].loc[i]
            v = r[col]
            if r["label"] == "insufficient_evidence" or pd.isna(v):
                not_asked += 1
                hatched(ax, x, y)
                continue
            cell(ax, x, y, GREEN_SEQ(v), None, f"{v:.2f}" if v < 1 else None,
                 WHITE if v > 0.6 else INK, edge=WHITE, size=8.5)
    grid_axes(ax, len(cs), len(rows))
    row_labels(ax, rows, lambda i: T["ind"][i], x=-0.12, size=9.5)
    upright_header(ax, [T["country"][c] for c in cs])
    sm = mpl.cm.ScalarMappable(cmap=GREEN_SEQ, norm=mpl.colors.Normalize(0, 1))
    cax = ax.inset_axes([0, -0.07, 0.4, 0.022])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=9, length=0, colors=INK_2)
    if not_asked:
        ax.legend(handles=[Patch(facecolor=WHITE, edgecolor=AXIS, hatch=HATCH, label=cap(T["not_asked"]))],
                  loc="upper left", bbox_to_anchor=(0.5, -0.045), frameon=False, fontsize=9.5, handlelength=1.4)
    white_save(fig, out / "figD1_stability.png")


def fig_negatives_paper(D, T, out):
    """E1: every criterion by how it is met or left out; countries in the order of Figure 2, and a dot
    where the vote was not unanimous on the value or on the exclusion type, as in Figure 3."""
    cs = by_elements_met(D, T)
    groups = [(T["sub"][s["subdimension_id"]],
               [i["indicator_id"] for i in s["indicators"] if i["type"] == "criterion"]) for s in D["order"]]
    rows = grouped_rows([g for g in groups if g[1]])
    fig, ax = plt.subplots(figsize=(0.66 * len(cs) + 4.3, 0.34 * len(rows) + 2.0), facecolor=WHITE)
    ax.set_facecolor(WHITE)
    seen, dots = set(), []
    for y, (kind, i) in enumerate(rows):
        if kind == "head":
            continue
        for x, c in enumerate(cs):
            r = D["ind"][c].loc[i]
            k = "met" if r["label"] == "met" else r["exclusion_type"]
            k = k if k in EXCL_SOFT else None
            seen.add(k)
            if k:
                cell(ax, x, y, EXCL_SOFT[k], edge=WHITE)
            else:
                hatched(ax, x, y)
            if not_unanimous(r):
                dots.append((x + 0.84, y + 0.24))
    if dots:
        ax.scatter(*zip(*dots), s=20, facecolor=WHITE, edgecolor=INK, linewidth=0.8, zorder=5)
    grid_axes(ax, len(cs), len(rows))
    row_labels(ax, rows, lambda i: T["ind"][i], x=-0.12, size=9.5)
    upright_header(ax, [T["country"][c] for c in cs])
    names = {"met": cap(T["label"]["met"]), **{e: T["excl_long"][e] for e in EXCLUSIONS}}
    h = [Patch(facecolor=EXCL_SOFT[k], edgecolor=WHITE, label=names[k]) for k in EXCL_SOFT if k in seen]
    if None in seen:
        h.append(Patch(facecolor=WHITE, edgecolor=MUTED, hatch=HATCH, label=cap(T["empty"])))
    if dots:
        h.append(Line2D([], [], marker="o", linestyle="", markersize=5, markerfacecolor=WHITE,
                        markeredgecolor=INK, markeredgewidth=0.8, label=T["not_unanimous"]))
    paper_legend(ax, h)
    white_save(fig, out / "figE1_exclusion_types.png")
    return dots


def list_indicators(D):
    return [i for s in D["order"] for i in s["indicators"] if i["type"] == "criterion_list"]


# The captions of the paper's figures, as they are in the paper, with its numbering and the file of each.
PAPER_CAPTIONS = [
    ("1", "fig1_female_heads_by_unit.png",
     "Female-headed households per territorial unit in the microdata of the twelve surveys. Each point is one unit of "
     "the most disaggregated territorial variable released in each file (named in parentheses) with at least one "
     "sampled household in the quarter; the box spans the first to third quartile and the vertical line marks the "
     "median. Counts are unweighted and refer to the same file and quarter as Table 4, excluding 315 British "
     "households with no household reference person recorded and 1,929 Chilean households with no single main "
     "provider recorded. The horizontal axis is logarithmic, so units with no female-headed household are not drawn "
     "but are included in the quartiles and counted at the right of each panel. The dashed line marks 60 cases, the "
     "minimum below which INE Chile does not publish an estimate, applied here to all countries as a common "
     "reference."),
    ("2", "fig2_results_by_country.png",
     "Results of the thirteen ranked indicators by country. Countries are ordered by the number of framework "
     "elements satisfied (Table 5). A dot marks the five cells in which the three repetitions did not agree "
     "(Section 4.2.6)."),
    ("3", "fig3_unpaid_work_exclusions.png",
     "How unpaid domestic and care work enters each questionnaire. For each criterion of subdimension 2, the cell "
     "shows whether the instrument measures the item or, if not, how the documentation treats it, by explicit "
     "exclusion, by placing it in another category (typically a reason for inactivity), or by not mentioning it. "
     "The criterion list d2_i2 is not shown because its elements are only recorded as true or false. A dot marks "
     "the cells in which the repetitions did not agree on the answer or on the type of exclusion."),
    ("4", "fig4_household_elements.png",
     "Elements of subdimension 4 by the number of instruments that capture them. Elements are the components of "
     "the criterion lists d4_i3 to d4_i6 (Table 2)."),
    ("B1", "figB1_tokens_by_source.png",
     "Tokens in each country's corpus by document type (C questionnaire, M methodological documentation, G "
     "interviewer manual or guide), counted with the Gemini 3.6 Flash tokenizer. The number at the end of each bar "
     "is the country total. This is the size of the corpus and not what was billed, since each call receives only "
     "the document types its indicator draws on."),
    ("B2", "figB2_run_summary.png",
     "Run summary by country, with the actual cost in US dollars, the share of input served from cache, the calls "
     "belonging to indicators split into parts, the failed parts or repetitions and the non-unanimous votes. A "
     "failed part or repetition is a response that could not be read as a complete assessment."),
    ("D1", "figD1_stability.png",
     "Stability of the classification by indicator and country. The upper panel shows the voted indicators, where "
     "stability is the share of repetitions that agree with the vote, averaged over elements for criterion lists. "
     "The lower panel shows the record indicators, which are not voted, where the measure is the mean word-set "
     "similarity between the texts of the three repetitions, so low values can come from wording rather than "
     "content. Both measures run from 0 to 1 but measure different things. The definition of headship was not "
     "assessed in Paraguay, whose corpus has neither methodological documents nor a manual."),
    ("E1", "figE1_exclusion_types.png",
     "Type of exclusion for each unmet criterion, by indicator and country. An exclusion is explicit when the text "
     "states that the item is excluded, treated as another category when the text mentions the item but places it "
     "elsewhere (typically as a reason for inactivity), and not mentioned when the text does not refer to it. Met "
     "cells are marked as met, and criterion lists are not shown because they carry no exclusion type."),
]
# Added to E1 when the figure marks any non-unanimous cell; the same sentence as Figure 3.
DOT_SENTENCE = ("A dot marks the cells in which the repetitions did not agree on the answer or on the type of "
                "exclusion.")


def paper_captions(D, out) -> None:
    """CAPTIONS.md for the paper's figures: their numbering, file and caption as in the paper. E1 gets the
    sentence on non-unanimous cells when it draws any, which is read from the same rows the figure uses."""
    crit = [i["indicator_id"] for s in D["order"] for i in s["indicators"] if i["type"] == "criterion"]
    dots_e1 = sum(not_unanimous(D["ind"][c].loc[i]) for c in D["ids"] for i in crit)
    L = ["# Figure captions", "",
         "The figures of the paper, with the paper's numbering. Generated by `scripts/llm/final_run_figures.py`; the "
         "figures are in this folder.", ""]
    for num, fname, text in PAPER_CAPTIONS:
        if num == "E1" and dots_e1:
            text = f"{text} {DOT_SENTENCE}"
        assert (out / fname).exists(), f"{fname} is missing"
        L += [f"## Figure {num} (`{fname}`)", "", text, ""]
    path = out / "CAPTIONS.md"
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"-> {path.relative_to(ROOT)} (Figure E1: {dots_e1} cells with a dot)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "outputs" / "final_run_2026-10-08",
                    help="folder holding runs.json; figures go to <dir>/figures")
    ap.add_argument("--count-tokens", action="store_true",
                    help="refresh figures/tokens_by_source.json with Gemini countTokens (free)")
    args = ap.parse_args()
    base = args.dir if args.dir.is_absolute() else ROOT / args.dir
    out = base / "figures"
    out.mkdir(parents=True, exist_ok=True)
    if args.count_tokens:
        count_tokens(base)
    D = load(base)
    T = TEXT["en"]
    fig_labels_ranked(D, T, out)
    fig_d2_negatives(D, T, out)
    fig_d4_elements(D, T, "en", out)
    fig_tokens_paper(D, T, out)
    fig_run_paper(D, T, out)
    fig_stability_paper(D, T, out)
    fig_negatives_paper(D, T, out)
    paper_captions(D, out)


if __name__ == "__main__":
    main()
