"""Route a document title or filename to a framework source code (C / M / G).

Single source of truth for classification, shared by the scrapers and safe to
import from the triage step. The framework's indicators declare which source
family answers them, so a misrouted document is not a cosmetic problem: it
either supplies the wrong evidence or leaves an indicator `source_missing`.

Order matters. G is tested first because an interviewer manual names the
instrument it administers ("Manual de recolección", "Manual del entrevistador")
and would otherwise be swallowed by the C rules. M is tested last because
"metodología" appears in the title of a great many things that are not survey
methodology.
"""

import re

# Languages present in the corpus: ES, PT, EN, FR, DE, NL, SV, IT.
RULES = [
    ("G", r"manual del (entrevistador|encuestador|supervisor|cr[ií]tico)"
          r"|manual de recolecc|manual do (entrevistador|agente)"
          r"|instructivo|interviewer (manual|instruction|guide)"
          r"|intervjuarhandledning|handbok f[oö]r intervjuare"
          r"|manuel de l'?enqu[eê]teur|manuale (di )?rilevaz|interviewerhandbuch"
          r"|handleiding (voor )?enqu[eê]teur"),
    ("C", r"cuestionario|question[aá]rio|questionnaire|fragebogen|formulario"
          r"|blankett|vragenlijst|boleta|c[eé]dula censal"),
    ("M", r"metodolog|methodolog|m[eé]thodolog|methoden en definities|metodologi"
          r"|qualit[aä]tsbericht|quality report|ficha t[eé]cnica|ficha metodol"
          r"|c[oó]mo se hace|m[eé]todos y procedimientos|nota t[eé]cnica"
          r"|note m[eé]thodologique|dise[nñ]o (muestral|de la muestra)"
          r"|background and methodology|user guide|documenta[cç][aã]o metodol"),
]

# Titles that satisfy a rule above without being the instrument itself. Checked
# before the rules, so an exclusion always wins.
NOT_DOCUMENTATION = re.compile(
    r"control de cambios|diccionario|dicion[aá]rio|data dictionary|tabulado"
    r"|indicadores estrat|infolaboral|glosario|gloss[aá]rio|cat[aá]logo"
    r"|clasificaci[oó]n|classifica[cç][aã]o|sintaxis|syntax"
    r"|reconstrucci[oó]n de variables|estructura de la base"
    # INE Uruguay files release notes under titles naming a methodology
    # ("Nota bases cortas con variables de pobreza metodología 2017"); they
    # document a published series, not the instrument.
    r"|^nota (aclaratoria|bases|microdatos|cambio)"
    # Results bulletins and press material quote methodology in their titles.
    r"|comunicado|press release|bolet[ií]n|informe de resultados"
    r"|presentaci[oó]n|empalme",
    re.I,
)

# One deliberate exception to the exclusions: Chile publishes its sex/gender/
# orientation measurement work as "informe de resultados…". Those documents are
# the strongest positive evidence in the whole sample, so a gender/sex mention
# overrides the exclusion — the same guard triage_corpus.py applies.
GENDER_OVERRIDE = re.compile(
    r"g[eé]nero|gender|sexo|orientaci[oó]n sexual|k[oö]n|geschlecht", re.I
)


def classify(text: str) -> str | None:
    """Return "C", "M", "G", or None when the text names no source family."""
    if NOT_DOCUMENTATION.search(text) and not GENDER_OVERRIDE.search(text):
        return None
    for code, pattern in RULES:
        if re.search(pattern, text, re.I):
            return code
    return None
