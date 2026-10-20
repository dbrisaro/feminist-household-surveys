"""Figure 1 and territorial microdata counts for the final run.

Figure 1 of the paper: Female-headed households per territorial unit, one panel per country,
ordered by median (written as fig1_female_heads_by_unit.png, with its data in
fig1_female_heads_by_unit.csv and fig1_female_heads_whole_year.csv).

Counts are unweighted, from the national microdata under data/raw/<country>/microdatos/
for the calendar quarter of Table 4.

    python scripts/final_run_territory_figures.py --dir outputs/final_run_2026-10-08
"""
import argparse
import sys
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "llm"))
from final_run_comparable_sample import local, sav  # noqa: E402
from final_run_figures import (AXIS, GRID, INK, INK_2, MUTED, PNG_DPI,  # noqa: E402
                               TEXT, cap, load, region)

RAW = ROOT / "data" / "raw"

T2 = {
    "en": {"fh_axis": "female-headed households per territorial unit (log scale, unweighted)",
           "zero": "with 0", "units": "units", "median": "median",
           "iqr": "quartiles 1 to 3", "cases60": "60 cases (INE Chile threshold)"},
}

UNIT_NAME = {  # (es, en)
    "argentina": ("aglomerado", "agglomeration"), "bolivia": ("departamento", "department"),
    "chile": ("comuna", "commune"), "colombia": ("departamento", "department"),
    "ecuador": ("código de ciudad", "city code"), "spain": ("provincia", "province"),
    "italy": ("región", "region"), "mexico": ("municipio", "municipality"),
    "paraguay": ("estrato geográfico", "geographic stratum"), "peru": ("distrito", "district"),
    "united_kingdom": ("región de residencia", "region of residence"), "uruguay": ("segmento censal", "census segment"),
}

NOTES: dict = {}
CASES = 60  # INE Chile's publication threshold in sample cases, from its documentation, drawn in every panel
WHITE = "#ffffff"
# Figure 1 colours: saturated, with a lightness gap that survives greyscale (blended at DOT_ALPHA on white, L* 55 vs 73).
FIG1_REGION = {"latam": "#9e3418", "europe": "#3aaa58"}
DOT_ALPHA = 0.7


def heads(c, year=False):
    """(DataFrame unit -> heads and female heads, (kinship var/code, sex var/code, unit var)).

    The quarter of Table 4 by default. `year=True` keeps the whole-year counts,
    for Peru (module 500) and Uruguay (implantation file) only; the text
    cites them to say that not even a year of sample reaches the threshold there.
    """
    loc = local
    if year and c not in ("peru", "uruguay"):
        raise ValueError(f"no whole-year count for {c}")
    if c == "argentina":
        d = pd.read_csv(loc(RAW / "argentina/microdatos/2023/EPH_2023_q4_personas.txt"), sep=";",
                        usecols=["CH03", "CH04", "AGLOMERADO"])
        h = d[d["CH03"] == 1]; female = h["CH04"] == 2; unit = h["AGLOMERADO"].astype(str)
        meta = ("CH03 = 1 (jefe/a)", "CH04 = 2 (mujer)", "AGLOMERADO")
    elif c == "bolivia":
        d = sav(RAW / "bolivia/microdatos/2024/ECE_2024_q4.sav", ["s1_05", "s1_02", "depto"])
        h = d[d["s1_05"] == 1]; female = h["s1_02"] == 2; unit = h["depto"].astype(int).astype(str)
        meta = ("s1_05 = 1 (jefa o jefe del hogar)", "s1_02 = 2 (mujer)", "depto")
    elif c == "chile":
        d = pd.read_csv(loc(RAW / "chile/microdatos/2020/ENE_2020_02_efm.csv"), sep=";", encoding="latin-1",
                        usecols=["id_identificacion", "hogar", "proveedor", "sexo", "r_p_c"])
        n_prov = d.groupby(["id_identificacion", "hogar"])["proveedor"].transform(lambda x: int((x == 1).sum()))
        per_hh = d.assign(n=n_prov).drop_duplicates(["id_identificacion", "hogar"])["n"]
        NOTES["chile_households"] = len(per_hh)
        NOTES["chile_no_provider"] = int((per_hh == 0).sum())
        NOTES["chile_multi_provider"] = int((per_hh > 1).sum())
        h = d[(d["proveedor"] == 1) & (n_prov == 1)]; female = h["sexo"] == 2; unit = h["r_p_c"].astype(str)
        meta = ("proveedor = 1 (proveedor/a principal; la ENE no usa jefatura)", "sexo = 2 (mujer)", "r_p_c (comuna)")
    elif c == "colombia":
        parts = []
        for m in ("07", "08", "09"):
            z = zipfile.ZipFile(loc(RAW / f"colombia/microdatos/2024/GEIH_2024_{m}.zip"))
            with z.open("CSV/Características generales, seguridad social en salud y educación.CSV") as f:
                parts.append(pd.read_csv(f, sep=";", usecols=["DIRECTORIO", "P6050", "P3271", "DPTO"],
                                         encoding="latin-1").assign(m=m))
        d = pd.concat(parts)
        assert not d.drop_duplicates(["DIRECTORIO", "m"])["DIRECTORIO"].duplicated().any(), \
            "a Colombian dwelling appears in two months of the quarter"
        h = d[d["P6050"] == 1]; female = h["P3271"] == 2; unit = h["DPTO"].astype(str)
        meta = ("P6050 = 1 (jefe/a del hogar)", "P3271 = 2 (mujer)", "DPTO")
    elif c == "ecuador":
        d = sav(RAW / "ecuador/microdatos/2026/ENEMDU_2026_q1_personas_v2.sav", ["p04", "p02", "ciudad"])
        h = d[d["p04"] == 1]; female = h["p02"] == 2; unit = h["ciudad"].astype(int).astype(str)
        meta = ("p04 = 1 (jefe)", "p02 = 2 (mujer)", "ciudad")
    elif c == "spain":
        d = pd.read_csv(loc(RAW / "spain/microdatos/2021/EPA_2021_q1.csv"), sep="\t", usecols=["RELPP1", "SEXO1", "PROV"])
        h = d[d["RELPP1"] == 1]; female = h["SEXO1"] == 6; unit = h["PROV"].astype(str)
        meta = ("RELPP1 = 1 (persona de referencia)", "SEXO1 = 6 (mujer)", "PROV")
    elif c == "italy":
        z = zipfile.ZipFile(loc(RAW / "italy/microdatos/2025/RCFL_2025_q3.zip"))
        with z.open("MICRODATI/RCFL_Microdati_2025_Terzo_trimestre.txt") as f:
            d = pd.read_csv(f, sep="\t", usecols=["RELPARM", "SESSO", "REGMCR"], dtype=str, encoding="latin-1")
        h = d[d["RELPARM"].str.strip() == "01"]; female = h["SESSO"].str.strip() == "2"; unit = h["REGMCR"].str.strip()
        meta = ("RELPARM = 01 (persona di riferimento)", "SESSO = 2 (femmina)", "REGMCR (regione)")
    elif c == "mexico":
        d = pd.read_csv(loc(RAW / "mexico/microdatos/2023/ENOE_2023_q1_sdem.csv"), encoding="latin-1", low_memory=False,
                        usecols=["par_c", "sex", "ent", "mun", "r_def", "c_res"])
        ok = (pd.to_numeric(d["r_def"], errors="coerce") == 0) & d["c_res"].isin([1, 3])
        par = pd.to_numeric(d["par_c"], errors="coerce")
        h = d[ok & (par == 101)]; female = pd.to_numeric(h["sex"], errors="coerce") == 2
        unit = h["ent"].astype(str) + "-" + h["mun"].astype(str)
        meta = ("par_c = 101 (jefe/a), residentes con entrevista completa", "sex = 2 (mujer)", "ent + mun (municipio)")
    elif c == "paraguay":
        d = sav(RAW / "paraguay/microdatos/2026/EPHC_2026_q1.sav", ["P03", "P06", "ESTGEO"])
        h = d[d["P03"] == 1]; female = h["P06"] == 6; unit = h["ESTGEO"].astype(int).astype(str)
        meta = ("P03 = 1 (jefe/a)", "P06 = 6 (mujer)", "ESTGEO (estrato geográfico)")
    elif c == "peru" and year:
        d = sav(RAW / "peru/microdatos/2024/ENAHO_2024_mod500.sav", ["P203", "P207", "UBIGEO"])
        h = d[d["P203"] == 1]; female = h["P207"] == 2; unit = h["UBIGEO"].astype(str)
        meta = ("P203 = 1 (jefe/jefa)", "P207 = 2 (mujer)", "UBIGEO (distrito)")
    elif c == "peru":
        k = ["CONGLOME", "VIVIENDA", "HOGAR"]
        hh = sav(RAW / "peru/microdatos/2024/ENAHO_2024_mod100.sav", k + ["MES", "RESULT", "UBIGEO"])
        hh = hh[hh["RESULT"].isin([1, 2]) & (hh["MES"].astype(int) >= 10)]
        m = sav(RAW / "peru/microdatos/2024/ENAHO_2024_mod200.sav", k + ["P203", "P207"])
        h = m[m["P203"] == 1].merge(hh[k + ["UBIGEO"]], on=k)
        female = h["P207"] == 2; unit = h["UBIGEO"].astype(str)
        meta = ("P203 = 1 (jefe/jefa)", "P207 = 2 (mujer)", "UBIGEO (distrito)")
    elif c == "united_kingdom":
        z = zipfile.ZipFile(loc(RAW / "united_kingdom/microdatos/8806tab_45738F0DE3A8EB75202602B51697180B6B848413391424121301BCB6F20DEF40_V1.zip"))
        with z.open("UKDA-8806-tab/tab/lfsp_jm21_eul_pwt24.tab") as f:
            d = pd.read_csv(f, sep="\t", usecols=["HSERIALP", "HOUT", "HRP", "SEX", "URESMC"], dtype=str)
        d = d[d["HOUT"].isin(["11", "12", "20"])]
        h = d[d["HRP"] == "1"]; female = h["SEX"] == "2"; unit = h["URESMC"]
        NOTES["uk_no_hrp"] = d["HSERIALP"].nunique() - h["HSERIALP"].nunique()
        meta = ("HRP = 1 (household reference person)", "SEX = 2 (female)", "URESMC (region of usual residence)")
    elif c == "uruguay":
        d = pd.read_csv(loc(RAW / "uruguay/microdatos/2022/ECH_2022_merged.csv"), encoding="latin-1",
                        usecols=["e30", "e26", "dpto", "secc", "segm", "mes"], low_memory=False)
        if not year:
            d = d[d["mes"] >= 10]
        h = d[pd.to_numeric(d["e30"], errors="coerce") == 1]; female = pd.to_numeric(h["e26"], errors="coerce") == 2
        unit = h["dpto"].astype(str) + "-" + h["secc"].astype(str) + "-" + h["segm"].astype(str)
        meta = ("e30 = 1 (referente del hogar)", "e26 = 2 (mujer)", "dpto + secc + segm (segmento censal)")
    out = pd.DataFrame({"unit": unit.values, "female": female.values})
    g = out.groupby("unit").agg(heads=("female", "size"), female_heads=("female", "sum")).reset_index()
    return g, meta


def legend_below(ax, handles, y=-0.1, ncol=None):
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, y), ncol=ncol or len(handles),
              frameon=False, fontsize=8, handlelength=1.4)


def by_median(fh, cs):
    """Countries from the highest median of female heads per unit to the lowest; the mean breaks ties."""
    return sorted(cs, key=lambda c: (-np.median(fh[c][0]["female_heads"]), -fh[c][0]["female_heads"].mean()))


def fig_heads_panels(D, T, lang, fh, out):
    """One panel per country: every unit as a dot, the interquartile box and the median, and the 60-case line."""
    cs = by_median(fh, D["ids"])
    L = T2[lang]
    k = 0 if lang == "es" else 1
    rng = np.random.default_rng(7)
    num = lambda x: f"{x:,.0f}".replace(",", "." if lang == "es" else ",")
    fig, axes = plt.subplots(len(cs), 1, figsize=(8.6, 0.62 * len(cs) + 0.9), sharex=True, facecolor=WHITE)
    for ax, c in zip(axes, cs):
        v = fh[c][0]["female_heads"].to_numpy()
        col = FIG1_REGION[region(c)]
        ax.set_facecolor(WHITE)
        pos = v[v > 0]
        ax.scatter(pos, rng.uniform(-0.3, 0.3, len(pos)), s=8, color=col, alpha=DOT_ALPHA, linewidth=0, zorder=3)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ax.add_patch(plt.Rectangle((q1, -0.38), q3 - q1, 0.76, facecolor="none", edgecolor=INK, linewidth=1, zorder=4))
        ax.plot([med, med], [-0.38, 0.38], color=INK, linewidth=1.8, zorder=5)
        ax.axvline(CASES, color=INK_2, linewidth=1, linestyle=(0, (2, 2)), zorder=2)
        zero = int((v == 0).sum())
        # Two lines, so the label column is narrower and the plot area wider.
        note = f"{num(len(v))} {L['units']}" + (f"\n{num(zero)} {L['zero']}" if zero else "")
        ax.text(1.01, 0, note, transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=7, color=MUTED)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([0])
        ax.set_yticklabels([f"{T['country'][c]}\n({UNIT_NAME[c][k]})"], fontsize=8, color=INK_2)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", which="both", labelsize=7.5, length=0)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8, which="major")
        ax.set_axisbelow(True)
        for sp in ("left", "top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
    ax = axes[-1]
    ax.set_xscale("log")
    ax.set_xlim(0.8, max(fh[c][0]["female_heads"].max() for c in cs) * 1.6)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: num(x)))
    ax.set_xlabel(cap(L["fh_axis"]), fontsize=8.5)
    fig.subplots_adjust(hspace=0.25)
    h = [Patch(facecolor=FIG1_REGION[r], alpha=DOT_ALPHA, label=T["region"][r]) for r in ("latam", "europe")]
    h += [Patch(facecolor="none", edgecolor=INK, linewidth=1, label=cap(L["iqr"])),
          Line2D([], [], color=INK, linewidth=1.8, label=cap(L["median"])),
          Line2D([], [], color=INK_2, linewidth=1, linestyle=(0, (2, 2)), label=L["cases60"])]
    legend_below(ax, h, y=-0.9)
    fig.savefig(out / "fig1_female_heads_by_unit.png", dpi=PNG_DPI, bbox_inches="tight", facecolor=WHITE)
    plt.close(fig)
    print(f"-> {(out / 'fig1_female_heads_by_unit.png').relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "outputs" / "final_run_2026-10-08")
    args = ap.parse_args()
    base = args.dir if args.dir.is_absolute() else ROOT / args.dir
    D = load(base)
    fh = {c: heads(c) for c in D["ids"]}
    fh_year = {c: heads(c, year=True) for c in ("peru", "uruguay")}
    out_en = base / "figures"
    out_en.mkdir(parents=True, exist_ok=True)
    # CSVs next to the English figures.
    pd.concat([fh[c][0].assign(country=c, unit_variable=fh[c][1][2], reference_person=fh[c][1][0], sex=fh[c][1][1])
               for c in D["ids"]])[["country", "unit_variable", "unit", "heads", "female_heads", "reference_person", "sex"]] \
        .to_csv(out_en / "fig1_female_heads_by_unit.csv", index=False)
    pd.concat([fh_year[c][0].assign(country=c, period="2024" if c == "peru" else "2022", unit_variable=fh_year[c][1][2])
               for c in fh_year])[["country", "period", "unit_variable", "unit", "heads", "female_heads"]] \
        .to_csv(out_en / "fig1_female_heads_whole_year.csv", index=False)
    T = TEXT["en"]
    fig_heads_panels(D, T, "en", fh, out_en)


if __name__ == "__main__":
    main()
