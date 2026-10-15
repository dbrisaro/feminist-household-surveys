"""Put the twelve final-run samples on one footing: households and persons in one calendar quarter.

For each country: households and resident persons with an interview in one calendar
quarter, unweighted, from the national microdata under data/raw/<country>/microdatos/.
Where a full year is held, also the distinct households of that year, following each
household across the waves of the rotating panel when the identifiers allow it. Each
count is set next to the sample size stated in the survey's own documentation, with a
ratio only where unit and period match. Writes COMPARABLE_SAMPLE.md (Table 4 of the paper).

The helpers refuse to read a microdata file that is not fully on disk.

    python scripts/final_run_comparable_sample.py --dir outputs/final_run_2026-10-08
"""
import argparse
import os
import zipfile
from pathlib import Path

import pandas as pd
import pyreadstat

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def local(path: Path) -> Path:
    st = os.stat(path)
    if st.st_blocks * 512 < st.st_size:
        raise SystemExit(f"{path} is not fully on disk; download it first")
    return path


def sav(path, cols, encoding=None):
    df, _ = pyreadstat.read_sav(str(local(path)), usecols=cols, encoding=encoding)
    return df


def csv(path, cols, sep=",", encoding="latin-1"):
    return pd.read_csv(local(path), usecols=cols, sep=sep, encoding=encoding, low_memory=False)


def n_unique(df, cols):
    return int(df[cols].drop_duplicates().shape[0])


def num(s):
    return pd.to_numeric(s, errors="coerce")


def same_head_sex(heads, key, sex):
    """Share of households seen more than once whose head has the same sex every time."""
    g = heads.groupby(key)[sex].agg(["size", "nunique"])
    g = g[g["size"] > 1]
    return float((g["nunique"] == 1).mean())


def pct(x):
    return f"{x * 100:.0f}%"


# Each function returns {"quarter": (period, households, persons), "year": (year, household-waves,
# distinct households or None) or None, "note": str, "year_note": str, "diff": str}.

def argentina():
    d = RAW / "argentina/microdatos/2023"
    H = []
    for q in range(1, 5):
        h = csv(d / f"EPH_2023_q{q}_hogar.txt", ["CODUSU", "NRO_HOGAR", "REALIZADA"], sep=";")
        H.append(h.assign(q=q))
    H = pd.concat(H)
    assert (H["REALIZADA"] == 1).all()
    p4 = csv(d / "EPH_2023_q4_personas.txt", ["CODUSU", "NRO_HOGAR", "COMPONENTE"], sep=";")
    h4 = H[H["q"] == 4]
    waves = H.groupby(["CODUSU", "NRO_HOGAR"])["q"].apply(lambda s: tuple(sorted(s)))
    pat = waves.value_counts()
    return {
        "quarter": ("Q4 2023", n_unique(h4, ["CODUSU", "NRO_HOGAR"]), len(p4)),
        "year": ("2023", len(H), len(waves)),
        "note": "Household and person user files. Household = CODUSU + NRO_HOGAR; person = row of the person file. "
                "No interview filter is needed: every household in the file has REALIZADA = 1, and the person file holds only members of those households.",
        "year_note": f"The four quarters of 2023. CODUSU identifies the dwelling in every wave, so CODUSU + NRO_HOGAR follows the household. "
                     f"The pattern of appearances is that of the 2-2-2 rotation scheme: {pat.get((1, 2), 0):,} households in quarters 1 and 2, {pat.get((2, 3), 0):,} in 2 and 3, "
                     f"{pat.get((3, 4), 0):,} in 3 and 4, {pat.get((1, 4), 0):,} in 1 and 4 (they entered in Q4 2022 and returned in Q4 2023), and none in more than two. "
                     f"The file does not flag a change of household within the same dwelling: if a household moves out and another enters with the same NRO_HOGAR, it counts as one.",
        "diff": f"{len(h4):,} households were counted, two thirds of the 25,000 of the design. These files cannot separate non-response from design changes: "
                f"the documentation gives no sample figure after the 1998 one, except for Q2 2020 (26,940 dwellings selected, "
                f"11,841 responding), which refers to the pandemic period and to dwellings.",
    }


def bolivia():
    p = sav(RAW / "bolivia/microdatos/2024/ECE_2024_q4.sav", ["id_hogar", "id_persona"])
    A = []
    for q in range(1, 5):
        a = sav(RAW / f"bolivia/microdatos/2023/ECE_2023_q{q}.sav", ["id_hogar", "id_hog_panel", "s1_05", "s1_02"])
        A.append(a.assign(q=q))
    A = pd.concat(A)
    hw = A.drop_duplicates(["id_hogar", "q"])
    moved = hw.groupby("id_hogar")["q"].nunique().gt(1).sum()
    nq = A.drop_duplicates(["id_hog_panel", "q"]).groupby("id_hog_panel")["q"].nunique().value_counts().sort_index()
    same = same_head_sex(A[A["s1_05"] == 1], "id_hog_panel", "s1_02")
    return {
        "quarter": ("Q4 2024", n_unique(p, ["id_hogar"]), n_unique(p, ["id_persona"])),
        "year": ("2023", len(hw), A["id_hog_panel"].nunique()),
        "note": "Single person file. Household = id_hogar; person = id_persona. Every household has exactly one head (s1_05 = 1). "
                "There is no interview-result or residence variable: the file holds only interviewed households and their members.",
        "year_note": f"The only complete year held is 2023 (only Q4 of 2024 is held, and Q4 of 2025 is missing). id_hogar changes every quarter "
                     f"(no value repeats across quarters{'' if moved == 0 else f', except {moved}'}), but id_hog_panel follows the household: of the distinct households, {nq.get(1, 0):,} appear in one quarter, {nq.get(2, 0):,} in two, "
                     f"{nq.get(3, 0):,} in three and {nq.get(4, 0):,} in all four. Among those that appear more than once, the head's sex is the same every time in {pct(same)} of cases.",
        "diff": f"The {n_unique(p, ['id_hogar']):,} households are {pct(n_unique(p, ['id_hogar']) / 17784)} of the 17,784 dwellings of the design, but the units differ "
                f"(a dwelling can hold more than one household) and the file does not allow dwellings to be counted, so the number of dwellings interviewed is unknown.",
    }


def chile():
    files = {"efm": "02_efm", "amj": "05_amj", "jas": "08_jas", "ond": "11_ond"}
    A = []
    for k, f in files.items():
        p = csv(RAW / f"chile/microdatos/2020/ENE_2020_{f}.csv", ["id_identificacion", "hogar", "mes_encuesta", "proveedor"], sep=";")
        A.append(p.assign(t=k))
    A = pd.concat(A)
    # Enero-marzo de 2020, not julio-septiembre: changed on 2026-10-14 at the authors' request.
    efm = A[A["t"] == "efm"]
    hw = A.drop_duplicates(["id_identificacion", "hogar", "t"])
    prov = efm.groupby(["id_identificacion", "hogar"])["proveedor"].apply(lambda s: int((s == 1).sum()))
    per = hw.groupby("t").size()
    seen = hw.drop_duplicates(["id_identificacion", "t"]).groupby("id_identificacion")["t"].apply("+".join).value_counts()
    return {
        "quarter": ("Jan–Mar 2020", n_unique(efm, ["id_identificacion", "hogar"]), len(efm)),
        "year": ("2020", len(hw), None),
        "note": "The January–February–March 2020 rolling quarter (`ENE_2020_02_efm.csv`) coincides with the first calendar quarter; an earlier version "
                "of this table used July–September 2020 (`ENE_2020_08_jas.csv`). Household = id_identificacion + hogar; person = row. The file has no "
                f"interview-result variable: it holds interviewed households and their members. {int((prov == 0).sum()):,} households have no main provider marked "
                f"(proveedor = 1) and {int((prov > 1).sum()):,} have more than one; in July–September every household had exactly one.",
        "year_note": f"The four calendar quarters of 2020 are held (efm, amj, jas, ond): {per['efm']:,} + {per['amj']:,} + {per['jas']:,} + {per['ond']:,} households. "
                     f"The distinct households of the year cannot be counted: id_identificacion repeats only between jas and ond ({seen.get('jas+ond', 0):,} households, always three months "
                     f"apart in mes_encuesta), and no household from efm or amj reappears in another quarter. With dwellings staying six quarters in the sample, this "
                     f"indicates that the identifier was recoded between files, not that the whole sample was renewed; if so, efm and amj cannot be linked to the rest.",
        "diff": "The roughly 54,000 dwellings stated apply from April–June 2020, after the quarter counted, so they are not compared. The files "
                "hold no dwellings without an interview and no contact result.",
    }


def colombia():
    H, P = [], []
    for m in ("07", "08", "09"):
        z = zipfile.ZipFile(local(RAW / f"colombia/microdatos/2024/GEIH_2024_{m}.zip"))
        with z.open("CSV/Características generales, seguridad social en salud y educación.CSV") as f:
            P.append(pd.read_csv(f, sep=";", usecols=["DIRECTORIO", "SECUENCIA_P", "ORDEN"], encoding="latin-1").assign(m=m))
        with z.open("CSV/Datos del hogar y la vivienda.CSV") as f:
            H.append(pd.read_csv(f, sep=";", usecols=["DIRECTORIO", "SECUENCIA_P"], encoding="latin-1").assign(m=m))
    H, P = pd.concat(H), pd.concat(P)
    repeat = H.drop_duplicates(["DIRECTORIO", "m"]).groupby("DIRECTORIO").size().gt(1).sum()
    return {
        "quarter": ("Q3 2024", n_unique(H, ["m", "DIRECTORIO", "SECUENCIA_P"]), n_unique(P, ["m", "DIRECTORIO", "SECUENCIA_P", "ORDEN"])),
        "year": None,
        "note": f"Sum of the monthly files of July, August and September 2024. Household = DIRECTORIO + SECUENCIA_P (household and dwelling module); person = + ORDEN "
                f"(general characteristics module). {'No dwelling (DIRECTORIO) repeats' if repeat == 0 else f'{repeat} dwellings (DIRECTORIO) repeat'} across the three months, so the sum does not count the same household twice. "
                f"The published files hold only interviewed households and their residents.",
        "year_note": "The twelve months of 2024 are held, but only the three months of the quarter were read for this table. The GEIH is not a panel and, in the quarter "
                     "counted, no dwelling repeats across months, so with the twelve months the number of distinct households of the year would be expected "
                     "to equal the sum of the monthly counts.",
        "diff": "None that can be measured: the stated figure is annual and approximate, and the year was not counted.",
    }


def ecuador():
    d = RAW / "ecuador/microdatos/2026"
    v = sav(d / "ENEMDU_2026_q1_vivienda_v2.sav", ["id_vivienda", "id_hogar"])
    viv = n_unique(v, ["id_vivienda"])
    p = sav(d / "ENEMDU_2026_q1_personas_v2.sav", ["id_persona"])
    a = sav(RAW / "ecuador/microdatos/2025/ENEMDU_2025_personas.sav", ["id_hogar", "periodo", "p04", "p02"])
    month = (a["periodo"] % 100).astype(int).astype(str).str.zfill(2)
    assert (a["id_hogar"].str[-2:] == month).all()
    a["k"] = a["id_hogar"].str[:-2]
    hw = a.drop_duplicates(["id_hogar"])
    n = hw.groupby("k").size().value_counts()
    m = (hw["periodo"] % 100).astype(int)
    gap = m.groupby(hw["k"]).agg(lambda s: s.max() - s.min())
    gap = gap[hw.groupby("k").size() > 1].value_counts()
    same = same_head_sex(a[a["p04"] == 1], "k", "p02")
    return {
        "quarter": ("Q1 2026", n_unique(v, ["id_hogar"]), n_unique(p, ["id_persona"])),
        "year": ("2025", len(hw), hw["k"].nunique()),
        "note": "Cumulative file for Q1 2026 (_v2 files: January, February and March). Household = id_hogar (dwelling file); person = id_persona. "
                "Each household appears in a single month of the quarter. The files hold only interviewed households and their members.",
        "year_note": f"Annual person file for 2025 (all twelve months). id_hogar ends in the two digits of the month, so it changes at each visit; without them, the rest "
                     f"(PSU, panel, dwelling, household) follows the household: {n.get(1, 0):,} households appear once and {n.get(2, 0):,} twice in the year ({gap.get(3, 0):,} three months "
                     f"apart and {gap.get(9, 0):,} nine months apart). Among those that appear twice, the head's sex is the same in {pct(same)} of cases.",
        "diff": f"The dwelling file allows dwellings to be counted: {viv:,} in the quarter, {pct(viv / 27048)} of the 27,048 stated. That is the comparison in the "
                f"same unit, but it is left out of the ratio column because that column is for households. It is not known whether the 27,048 are selected or "
                f"interviewed dwellings; if they are selected dwellings, the response rate would be very high for a household survey.",
    }


def spain():
    p = csv(RAW / "spain/microdatos/2021/EPA_2021_q1.csv", ["CICLO", "NVIVI", "NPERS", "RELPP1"], sep="\t")
    h = n_unique(p, ["CICLO", "NVIVI"])
    assert h == int((p["RELPP1"] == 1).sum())
    return {
        "quarter": ("Q1 2021", h, len(p)),
        "year": ("2021", None, None),
        "note": "Household = CICLO + NVIVI, which the record layout (`dr_EPA_2021.xlsx`) defines as the \"household order number\"; it gives the same count as reference persons "
                "(RELPP1 = 1), one per household. An earlier count labelled this figure as dwellings: the number is the same, but the unit given by the record layout is the household. "
                "Person = row, of all ages (NIVEL 1, aged 16 and over; NIVEL 2, under 16). The file holds only interviewed households.",
        "year_note": "The four quarters of 2021 are held, but households cannot be followed across waves: NVIVI is an order number "
                     "within each quarterly file and the public file carries no stable identifier or rotation group. Only the first quarter was read for this table.",
        "diff": f"With 3,822 sections and 22 theoretical dwellings per section, the 2020 sample was about 84,000 dwellings; the {h:,} households counted are "
                f"{pct(h / (3822 * 22))} of that. The file holds no dwellings without an interview, so non-response, empty or unlocated dwellings "
                f"and the change of sectioning that began in 2021 cannot be told apart.",
    }


def italy():
    z = zipfile.ZipFile(local(RAW / "italy/microdatos/2025/RCFL_2025_q3.zip"))
    with z.open("MICRODATI/RCFL_Microdati_2025_Terzo_trimestre.txt") as f:
        p = pd.read_csv(f, sep="\t", usecols=["RELPARM", "WAVQUA"], dtype=str, encoding="latin-1")
    h = int((p["RELPARM"].str.strip() == "01").sum())
    return {
        "quarter": ("Q3 2025", h, len(p)),
        "year": ("2025", None, None),
        "note": "The file has no family identifier, so families are counted by their reference person (RELPARM = 01), as in the territorial figures. "
                "Person = row, of all ages (CLETAS runs from 0–2 to 75 and over). The file holds only interviewed families.",
        "year_note": "The four quarters of 2025 are held, but without a family identifier a family cannot be followed across "
                     "quarters. WAVQUA gives the interview number of each person (1st to 4th), not their identity.",
        "diff": f"The ratio is compatible with non-response of about {pct(1 - h / 70000)} of the theoretical sample, but the documentation gives no response rate to "
                f"confirm it. The {dec(len(p) / h)} persons per family is the lowest value in the table; unweighted, this may reflect higher response among small and older "
                "families, but these data cannot show it.",
    }


def mexico():
    d = RAW / "mexico/microdatos/2023"
    keys = ["cd_a", "ent", "con", "v_sel", "n_pro_viv", "n_hog", "h_mud"]
    viv = n_unique(csv(d / "ENOE_2023_q1_viv.csv", keys[:5]), keys[:5])
    s = csv(d / "ENOE_2023_q1_sdem.csv", keys[:5] + ["r_def", "c_res"])
    res = (num(s["r_def"]) == 0) & s["c_res"].isin([1, 3])
    A = []
    for q in range(1, 5):
        h = csv(d / f"ENOE_2023_q{q}_hog.csv", keys + ["r_def", "n_ent"])
        h = h[num(h["r_def"]) == 0]
        A.append(h.assign(q=q))
    A = pd.concat(A)
    # A household entering in quarter q - n_ent: separates two households that reuse the same keys.
    A["entry"] = A["q"] - num(A["n_ent"])
    distinct = n_unique(A, keys + ["entry"])
    n = A.groupby(keys + ["entry"]).size().value_counts().sort_index()
    return {
        "quarter": ("Q1 2023", int((A["q"] == 1).sum()), int(res.sum())),
        "year": ("2023", len(A), distinct),
        "note": "Household = cd_a + ent + con + v_sel + n_pro_viv + n_hog + h_mud, with a complete interview (r_def = 00). Person = usual resident (c_res 1 or 3) "
                "with a complete interview in the sociodemographic file.",
        "year_note": f"The household files of the four quarters of 2023 (the sociodemographic files are not needed to count households). The same keys follow "
                     f"the household and n_ent (interview number, 1 to 5) rises by one each quarter. To avoid merging two households that "
                     f"reuse the keys, the entry quarter (quarter − n_ent) was added. Of the distinct households, {n.get(1, 0):,} appear once, {n.get(2, 0):,} twice, "
                     f"{n.get(3, 0):,} three times and {n.get(4, 0):,} four times.",
        "diff": f"The dwelling file of the quarter has {viv:,} dwellings, with and without an interview, the figure the interviewer manual prints as \"150 566 mil viviendas "
                f"cada trimestre\" and that is read as 150,566; the {int((A['q'] == 1).sum()):,} households with a complete interview are {pct((A['q'] == 1).sum() / viv)} of those dwellings, in different units.",
    }


def paraguay():
    cols = ["UPM", "NVIVI", "NHOGA", "P02", "P03", "P06"]
    p = sav(RAW / "paraguay/microdatos/2026/EPHC_2026_q1.sav", cols)
    A = []
    for q in range(1, 5):
        a = sav(RAW / f"paraguay/microdatos/2025/EPHC_2025_q{q}.sav", cols)
        A.append(a.assign(q=q))
    A = pd.concat(A)
    k = ["UPM", "NVIVI", "NHOGA"]
    q1, q1n = A[A["q"] == 1], p
    upm_back = len(set(q1["UPM"]) & set(q1n["UPM"]))
    j = q1[q1["P03"] == 1].merge(q1n[q1n["P03"] == 1], on=k, suffixes=("", "_n"))
    A = A.drop_duplicates(k + ["q"])
    upm_q = A.drop_duplicates(["UPM", "q"]).groupby("UPM").size().max()
    return {
        "quarter": ("Q1 2026", n_unique(p, ["UPM", "NVIVI", "NHOGA"]), len(p)),
        "year": ("2025", len(A), n_unique(A, k)),
        "note": "Household = UPM + NVIVI + NHOGA; person = row. The file holds only interviewed households and their members; there is no result variable.",
        "year_note": f"The four quarters of 2025. {'No PSU appears in more than one quarter of the year' if upm_q == 1 else f'Some PSUs appear in up to {upm_q} quarters'}, so no household repeats within the year and the "
                     f"distinct households are the sum. Repetition is across years: {upm_back:,} of the {q1['UPM'].nunique():,} PSUs of Q1 2025 return in Q1 2026, "
                     f"with {len(j):,} households matching on the three keys; in these, the head has the same sex in {pct((j['P06'] == j['P06_n']).mean())} "
                     f"of cases and is one year older in {pct((j['P02_n'] - j['P02'] == 1).mean())}.",
        "diff": "The documentation states no sample figure to compare with.",
    }


def peru():
    d = RAW / "peru/microdatos/2024"
    k = ["CONGLOME", "VIVIENDA", "HOGAR"]
    h = sav(d / "ENAHO_2024_mod100.sav", k + ["MES", "RESULT", "PANEL"])
    p = sav(d / "ENAHO_2024_mod200.sav", k + ["CODPERSO", "P204", "P205", "P206"])
    ok = h[h["RESULT"].isin([1, 2])]
    viv_all, viv_ok = n_unique(h, k[:2]), n_unique(ok, k[:2])
    resident = ((p["P204"] == 1) & (p["P205"] == 2)) | ((p["P204"] == 2) & (p["P206"] == 1))
    pr = p[resident].merge(ok[k + ["MES"]], on=k)
    q4 = ok["MES"].astype(int) >= 10
    return {
        "quarter": ("Q4 2024", int(q4.sum()), int((pr["MES"].astype(int) >= 10).sum())),
        "year": ("2024", len(ok), n_unique(ok, k)),
        "note": f"Modules 100 (dwelling and household) and 200 (household members) of 2024, downloaded from INEI (`966-Modulo01.zip`, 9 MB; `966-Modulo02.zip`, 7 MB) "
                f"and saved as `ENAHO_2024_mod100.sav` and `ENAHO_2024_mod200.sav`. Household = CONGLOME + VIVIENDA + HOGAR with a complete or incomplete interview (RESULT 1 or 2); "
                f"the quarter comes from MES. Person = usual resident as defined by INEI (household member not absent for 30 days or more, or non-member present "
                f"for 30 days or more: P204, P205, P206) in those households. Module 500, used in an earlier count, holds only persons aged 14 and over.",
        "year_note": f"The annual ENAHO is a cross-sectional sample with a panel component across years (PANEL = 1 in {int((ok['PANEL'] == 1).sum()):,} of the households, "
                     f"also interviewed in 2023). Within the year each household appears once, so the distinct households equal those interviewed.",
        "diff": f"In the year, {viv_ok:,} dwellings have at least one interviewed household, {pct(viv_ok / 36594)} of the 36,594 stated for 2024. What remains "
                f"unexplained is that module 100 holds {viv_all:,} dwellings in total, counting refusals, absences, vacant dwellings and other results: more than the stated "
                f"sample. The technical sheet figure may exclude replacements or dwellings added in the field, but the documentation does not say.",
    }


def united_kingdom():
    z = zipfile.ZipFile(local(RAW / "united_kingdom/microdatos/8806tab_45738F0DE3A8EB75202602B51697180B6B848413391424121301BCB6F20DEF40_V1.zip"))
    with z.open("UKDA-8806-tab/tab/lfsp_jm21_eul_pwt24.tab") as f:
        p = pd.read_csv(f, sep="\t", usecols=["HSERIALP", "HOUT", "IOUTCOME", "HRP", "THISWV"], dtype=str)
    ok = p[p["HOUT"].isin(["11", "12", "20"])]
    bf = p[p["HOUT"].isin(["37", "41"])]
    w1 = ok[ok["THISWV"] == "1"]
    return {
        "quarter": ("Jan–Mar 2021", ok["HSERIALP"].nunique(), len(ok)),
        "year": None,
        "note": f"The file used in an earlier count (March–May 2022) is not a calendar quarter. January–March 2021 is (`8806tab_…_V1.zip`, "
                f"`lfsp_jm21_eul_pwt24.tab`), and, unlike the 2022 file, it carries the complete household identifier (HSERIALP). "
                f"Household = HSERIALP with an interview in the quarter (HOUT 11 complete interview, 12 inactive, 20 partly cooperating household). Excluded are "
                f"{bf['HSERIALP'].nunique():,} households ({len(bf):,} persons) with a circumstantial refusal or no contact (HOUT 37 and 41), whose data are carried forward from the "
                f"previous quarter. Person = every person in those households, including proxy responses and children under 16; {int((ok['IOUTCOME'] == '6').sum()):,} of them, "
                f"in partly cooperating households, also carry data forward from the previous quarter. Counting by reference person (HRP = 1) gives {int((ok['HRP'] == '1').sum()):,} "
                f"households: {ok['HSERIALP'].nunique() - int((ok['HRP'] == '1').sum()):,} have no HRP marked. Wave 1 holds {w1['HSERIALP'].nunique():,} households and {len(w1):,} persons.",
        "year_note": "No complete year is held: only January–March and February–April 2021 are. The other three calendar quarters of 2021 (April–June, "
                     "July–September and October–December) would be needed from the UK Data Service, which requires registration. With them, HSERIALP would follow the household "
                     "across waves, unless it is suppressed as in the 2022 file.",
        "diff": f"The documentation cites about 69,000 persons in wave 1 from July–September 2020. In this quarter wave 1 has {len(w1):,} persons; the five "
                f"waves together, with an interview, have {len(ok):,}, a figure close to the one in the document. The document may refer to the whole sample rather than to "
                f"wave 1 only, but that is a conjecture: the text says \"wave 1\" and the difference is unresolved. The 25,800 new addresses refer to 2024 and cannot be "
                f"compared with 2021.",
    }


def uruguay():
    p = csv(RAW / "uruguay/microdatos/2022/ECH_2022_merged.csv", ["ID", "mes"])
    q4 = p[p["mes"] >= 10]
    per_month = p.groupby("mes")["ID"].nunique()
    return {
        "quarter": ("Q4 2022", q4["ID"].nunique(), len(q4)),
        "year": ("2022", p.drop_duplicates(["ID", "mes"]).shape[0], p["ID"].nunique()),
        "note": f"Annual implantation file for 2022 (none closer to 2024 is held). Household = ID; person = row; quarter = months 10 to 12. Each month a new rotation group "
                f"enters ({per_month.min():,} to {per_month.max():,} households per month), so this is not the monthly labour market sample, which combines the "
                f"telephone follow-up visits of six groups and is not in the file.",
        "year_note": "Each household appears once in the implantation file, so the distinct households equal those interviewed. The monthly panel follow-ups "
                     "(the same households, by telephone) are not in the file.",
        "diff": f"{per_month.min():,} to {per_month.max():,} households enter each month, {pct(per_month.min() / 2000)} to {pct(per_month.max() / 2000)} of the roughly 2,000 "
                f"respondents expected per rotation group at implantation. This is the closest comparison, but the documentation does not say that one group enters per month, so "
                f"it is not carried into the table.",
    }


# (country, files for the quarter, declared figure, unit, period, ratio allowed, why not / caveat)
DECLARED = {
    "Argentina": ("25,000", "households", "per quarter (1998 design proposal, cited in 2003)", 25000,
                  "Unit and period match. The figure is the 1998 design proposal and refers to households to be surveyed, not households that responded; the ratio mixes non-response and design changes over 25 years."),
    "Bolivia": ("17,784", "dwellings", "per quarter", None,
                "The figure refers to selected dwellings and the file does not identify dwellings separately from households."),
    "Chile": ("≈ 54,000", "dwellings", "per rolling quarter, from Apr–Jun 2020, with oversample", None,
              "The figure refers to dwellings, is approximate and applies from April–June 2020, after the quarter counted."),
    "Colombia": ("≈ 315,000", "households", "per year", None,
                 "The figure is annual; converting it to a quarter assumes the sample is spread evenly across quarters, and the full year was not counted."),
    "Ecuador": ("27,048", "dwellings", "per quarter", None,
                "The figure refers to dwellings."),
    "Spain": ("3,822 sections × 22 theoretical dwellings (2020); 5,298 × 13 (from 2024)", "", "per quarter", None,
              "The figure refers to theoretical dwellings, and the quarter counted (2021) falls in the transition between the two sizes."),
    "Italy": ("≈ 70,000", "families", "per quarter (theoretical sample)", 70000,
              "Unit and period match. The figure is the theoretical sample (families to be interviewed), approximate."),
    "Mexico": ("150,566", "dwellings", "per quarter (printed as \"150 566 mil\" in the interviewer manual)", None,
               "The figure refers to dwellings."),
    "Paraguay": ("not found in the documentation", "", "", None, "No figure is stated."),
    "Peru": ("36,594", "dwellings", "in 2024", None,
             "The figure refers to dwellings and is annual."),
    "United Kingdom": ("25,800 + 80 + 1,300", "new addresses (wave 1)", "per quarter, from Jan–Mar 2024", None,
                       "The figure refers to new wave-1 addresses, not to households in all five waves, and starts in 2024."),
    "Uruguay": ("≈ 10,000", "households", "per month (six rotation groups of ≈ 2,000)", None,
                "The figure is monthly and adds follow-up visits of six rotation groups to the same households; it cannot be converted into distinct households in a quarter."),
}

COUNTRIES = [
    ("Argentina", "EPH_2023_q1–q4_hogar.txt, EPH_2023_q4_personas.txt", argentina),
    ("Bolivia", "ECE_2024_q4.sav; ECE_2023_q1–q4.sav", bolivia),
    ("Chile", "ENE_2020_02_efm.csv; ENE_2020_05_amj, 08_jas, 11_ond.csv", chile),
    ("Colombia", "GEIH_2024_07.zip, _08.zip, _09.zip", colombia),
    ("Ecuador", "ENEMDU_2026_q1_vivienda_v2.sav, _personas_v2.sav; ENEMDU_2025_personas.sav", ecuador),
    ("Spain", "EPA_2021_q1.csv", spain),
    ("Italy", "RCFL_2025_q3.zip", italy),
    ("Mexico", "ENOE_2023_q1_sdem.csv; ENOE_2023_q1–q4_hog.csv", mexico),
    ("Paraguay", "EPHC_2026_q1.sav; EPHC_2025_q1–q4.sav", paraguay),
    ("Peru", "ENAHO_2024_mod100.sav, ENAHO_2024_mod200.sav", peru),
    ("United Kingdom", "8806tab_…_V1.zip (lfsp_jm21_eul_pwt24.tab)", united_kingdom),
    ("Uruguay", "ECH_2022_merged.csv", uruguay),
]


def fmt(n):
    return "n/a" if n is None else f"{n:,}"


def dec(x, d=2):
    return f"{x:.{d}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "outputs" / "final_run_2026-10-08")
    args = ap.parse_args()
    out = args.dir if args.dir.is_absolute() else ROOT / args.dir
    q_rows, y_rows, notes = [], [], []
    for name, files, fn in COUNTRIES:
        r = fn()
        period, h, p = r["quarter"]
        fig, unit, when, value, why = DECLARED[name]
        ratio = dec(h / value) if value else ""
        declared = " ".join(x for x in (fig, unit, when) if x)
        q_rows.append(f"| {name} | {period} | {fmt(h)} | {fmt(p)} | {dec(p / h)} | {declared} | {ratio} |")
        if r["year"] and r["year"][1] is not None:
            yr, hw, dist = r["year"]
            y_rows.append(f"| {name} | {yr} | {fmt(hw)} | {fmt(dist) if dist is not None else 'cannot be counted'} | "
                          f"{dec(hw / dist) if dist else ''} |")
        else:
            y_rows.append(f"| {name} | {r['year'][0] if r['year'] else 'n/a'} | n/a | cannot be counted | |")
        notes.append(f"**{name}** (`{files}`). " + r["note"] + f" *Stated figure:* {why} *Differences:* " + r["diff"]
                     + " *Year:* " + r["year_note"])
        print(name, period, h, p, r["year"])
    L = ["# Sample sizes on a common basis", "",
         "Generated by `scripts/final_run_comparable_sample.py`. For each country, households and resident persons with an interview in one calendar quarter "
         "are counted, unweighted, from the national microdata under `data/raw/<country>/microdatos/`. Where the file does not identify households, they are "
         "counted by reference person, as in the territorial figures. The stated figure is the sample size given in the survey's own documentation. The ratio of "
         "households counted to the stated figure is given only where unit and period match; otherwise the column is empty and the country note says why.", "",
         "Compared with the first count of these samples: Colombia goes from one month to the sum of three; Peru goes from module 500 (persons aged 14 and over) "
         "to modules 100 and 200 (all residents) and from the whole year to one quarter; the United Kingdom goes from March–May 2022 to January–March 2021, the "
         "only recent calendar quarter held; Uruguay goes from the year to Q4; Spain and Italy now have households; Chile goes from July–September to "
         "January–March 2020.", "",
         "## One calendar quarter", "",
         "| Country | Period counted | Households | Persons | Persons per household | Stated figure (unit, period) | Households / stated figure |",
         "|---|---|---|---|---|---|---|", *q_rows, "",
         "## Distinct households in one year", "",
         "Household-waves counts each household as many times as it was interviewed in the year; distinct households counts it once, following it across waves "
         "with the identifiers in the file.", "",
         "| Country | Year | Household-waves | Distinct households | Waves per household |",
         "|---|---|---|---|---|", *y_rows, "",
         "## Notes by country", "", *[n + "\n" for n in notes]]
    (out / "COMPARABLE_SAMPLE.md").write_text("\n".join(L), encoding="utf-8")
    print(f"-> {(out / 'COMPARABLE_SAMPLE.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
