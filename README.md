# Feminist household surveys: replication materials

Code, evaluation framework, corpus records and results for the paper *Is there a feminist approach to statistical data collection? Assessing gender dimensions in National Household Surveys design*, by Daniela Belén Risaro and Micaela Fernández Erlauer (2026).

The study assesses the official household or labour force survey of thirteen countries against a framework of seventeen indicators. A language model (Gemini 3.6 Flash) answers each indicator from the survey documentation, three times per indicator, and the labels are derived from its answers by fixed rules. This repository holds everything needed to check and reproduce that assessment, except the survey documents and microdata themselves, which belong to the national statistics offices and are not redistributed.

## Repository structure

```
framework/            Evaluation framework: FRAMEWORK.md (readable), framework.json (parsed) and
                      gender_survey_framework.html (editable source)
config/               Corpus map per country (corpus_map.<country>.json), manual corpus decisions
                      (manual_overrides.json) and the microdata years held (microdata_years.json)
corpus/               documents.csv: the 48 documents of the final run, with source URL and SHA-256 of the extracted text
                      not_obtained.csv: the scraper's record of documents that could not be obtained, with the reason
data/inventory/       surveys_inventory.csv: survey, statistics office, corpus counts and microdata years (Table 1)
outputs/<country>/runs/all__gemini-3.6-flash__indicator__x3__2026-10-08_01/
                      The final run for each of the twelve countries: manifest.json (settings, documents and their
                      hashes, cost), prompts_appendix.md (the exact prompt of every call), raw.jsonl (one row per call),
                      responses/ (every model response, verbatim) and report/ (result tables)
outputs/final_run_2026-10-08/
                      Cross-country outputs: runs.json, COMPARABLE_SAMPLE.md (Table 4), RESULTS_SUMMARY.md
                      (results by indicator and country, and Table 5), SURVEY_DESIGN.md (survey design by country,
                      according to the corpus), APPENDIX_A_prompt.md (Appendix A) and figures/ (the paper's figures,
                      CAPTIONS.md, and the data behind Figure 1)
scripts/scraping/     Document collection (scrape_docs.py) and source-type rules (routing.py)
scripts/llm/          Corpus assembly, text extraction, classification pipeline, reports, figures, Appendix A
scripts/              Microdata counts, Table 1 inventory and territorial figures
```

Brazil is in Table 1 and has a corpus map, but it was not assessed: no questionnaire could be obtained.

## The evaluation framework

`framework/FRAMEWORK.md` is the document for reading the framework: the four subdimensions with their variables and, for each indicator, its identifier, type, source types and text, including the elements of each criterion list and the options of the categorical indicator. It is written by `scripts/llm/framework_doc.py` from `framework/framework.json`, which is what the classification reads. `framework/gender_survey_framework.html` is the editable source from which `scripts/llm/parse_framework.py` generates `framework.json`. The labels of the diagram in that HTML file are illustrative; the wording of the subdimensions and indicators is the one in `framework.json` and `FRAMEWORK.md`. The HTML file also outlines a second dimension, microdata analysis and representation, which is not evaluated in this study and is not carried into `framework.json`.

Each run's records keep the paths they had on the day of the run. The `manifest.json` and `prompts_appendix.md` of the final run name the framework source as `Prompting/gender_survey_framework.html`, the folder's name at the time; it is now `framework/gender_survey_framework.html`, with the same content.

## Setup

Python 3.13 and `pdftotext` from poppler (`brew install poppler` or `apt install poppler-utils`).

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The scripts are run from the repository root. API keys are read from environment variables (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) or from a local `.env` file, which is git-ignored. No key is needed to regenerate the figures, the tables built from the run, or Appendix A.

## What can be reproduced from this repository alone

| Paper item | File | Command | Needs |
|---|---|---|---|
| Table 2. Indicators | `framework/framework.json`, `framework/FRAMEWORK.md` | `python scripts/llm/parse_framework.py`, then `python scripts/llm/framework_doc.py` | nothing |
| Table 3. Label rules | `label_of()` in `scripts/llm/report.py` | `python -m pytest scripts/llm/test_labels.py` | nothing |
| Table 5. Framework elements satisfied by each instrument, by subdimension | `outputs/final_run_2026-10-08/RESULTS_SUMMARY.md` | `python scripts/llm/final_run_results.py` | nothing |
| Table 6. Household anchor and headship | `report/results_indicators.csv` of each run | none | nothing |
| Figure 2. Results by indicator and country | `outputs/final_run_2026-10-08/figures/fig2_results_by_country.png` | `python scripts/llm/final_run_figures.py` | nothing |
| Figure 3. Unpaid domestic and care work | `.../figures/fig3_unpaid_work_exclusions.png` | same | nothing |
| Figure 4. Elements of subdimension 4 | `.../figures/fig4_household_elements.png` | same | nothing |
| Figure B1. Corpus tokens by source type | `.../figures/figB1_tokens_by_source.png` | same | nothing |
| Figure B2. Run by country | `.../figures/figB2_run_summary.png` | same | nothing |
| Figure D1. Vote stability | `.../figures/figD1_stability.png` | same | nothing |
| Figure E1. Exclusion types | `.../figures/figE1_exclusion_types.png` | same | nothing |
| Appendix A. Classification prompt | `outputs/final_run_2026-10-08/APPENDIX_A_prompt.md` | `python scripts/llm/appendix_prompt.py` | nothing |

In Table 6, the identification method is the `selected` column of d4_i2, the conceptual definition is the `extracted_text` column of d4_i1, and the anchor term is read from the text quoted in d1_i4 or, for Italy and the United Kingdom, from the quotes of d4_i1 to d4_i3.

`final_run_figures.py` reads `runs.json`, each run's `report/`, `raw.jsonl` and `manifest.json`, and `figures/tokens_by_source.json`. It writes the figures above and `figures/CAPTIONS.md`, with the caption of each figure of the paper and its file. `appendix_prompt.py` rebuilds Appendix A from the code that built the calls and checks every task block against the run's `prompts_appendix.md`.

## What needs the microdata

| Paper item | File | Command |
|---|---|---|
| Table 1. Microdata years | `data/inventory/surveys_inventory.csv`, `config/microdata_years.json` | `python scripts/microdata_years.py`, then `python scripts/inventory.py --go` |
| Table 4. Sample sizes on a common basis | `outputs/final_run_2026-10-08/COMPARABLE_SAMPLE.md` | `python scripts/final_run_comparable_sample.py` |
| Figure 1. Female-headed households by territorial unit | `.../figures/fig1_female_heads_by_unit.png`, data in `fig1_female_heads_by_unit.csv` and `fig1_female_heads_whole_year.csv` | `python scripts/final_run_territory_figures.py` |
| Table C1. Quarter counted in Table 4 and design sample stated by each office | `outputs/final_run_2026-10-08/COMPARABLE_SAMPLE.md`, `outputs/final_run_2026-10-08/SURVEY_DESIGN.md` | `python scripts/final_run_comparable_sample.py` |

The design sample figures stated by each office are written in the `DECLARED` dictionary of `scripts/final_run_comparable_sample.py`; the document, page and supporting quote of each one are in `SURVEY_DESIGN.md`, which is written by hand and generated by no script.

The microdata are downloaded from each statistics office and placed under `data/raw/<country>/microdatos/`; the file names each script reads are written in the script, next to the period counted. The corpus columns of Table 1 (C, M and G counts) come from the corpus maps and need no microdata.

## Rebuilding the corpus and rerunning the classification

**Collection.** `python scripts/scraping/scrape_docs.py --country <country>` downloads the documents a statistics office publishes reachably into `data/raw/<country>/documentacion/`; `--coverage` prints, without fetching, which source types each office does not make available. The reasons are kept in the scraper's registry and exported to `corpus/not_obtained.csv`, which separates documents an office does not publish from documents that could not be retrieved, as recorded when the corpus was collected. Its `verified` column says whether the reason was checked on the office's website during collection (`yes`) or carried over from earlier notes without that check (`no`). In `corpus/documents.csv`, `url_kind` is `file` when the URL points to the document itself (for the Peruvian questionnaires of modules 100 and 200, to the INEI package that contains it) and `landing page, downloaded manually` when the document was obtained by hand from that page or, for Italy and Peru, from the microdata packages it ships in.

**Corpus assembly.** `python scripts/llm/triage_corpus.py --country <country>` classifies each document by file name and folder, deduplicates versions, keeps the most recent and caps each source type at four documents, writing a draft map to `config/draft/`. Documents the rules cannot classify are read from their first page by Claude Sonnet 5 when `--go` is given. The maps used in the final run are the ones in `config/`, which include the manual decisions recorded in `config/manual_overrides.json`; every exclusion is listed in each map with its reason.

**Text extraction.** The pipeline extracts each document with `pdftotext`, splitting long documents at page boundaries, and caches the text under `data/processed/text/<country>/`. The SHA-256 of each extracted text is in `corpus/documents.csv` and in each run's `manifest.json`, so a rebuilt corpus can be checked against the one assessed.

**Classification.** With the documents in place and a Gemini key set, each country was run as

```
python scripts/llm/run_eval_gemini.py --country <country> --model gemini-3.6-flash --mode indicator --repeat 3 \
    --billing paid --max-output-tokens 16000 --budget-usd <cap> --go
```

which writes a new run folder under `outputs/<country>/runs/`. Without `--go` it is a dry run that prints the planned calls and their projected cost; the final run cost USD 18.49 for the twelve countries. Model outputs vary between runs, so a new run will not reproduce the stored responses exactly; the stored responses are the record the paper is based on. The result tables of a run are written by `python scripts/llm/report.py --country <country> --run <run folder>`, which needs the corpus documents in place because it checks which source types each country holds, and the cross-country summary by `python scripts/llm/final_run_results.py`.

## License

Code (`scripts/`) is released under the MIT License. Data and results (`framework/`, `config/`, `corpus/`, `data/`, `outputs/`) are released under Creative Commons Attribution 4.0 International. See `LICENSE`.

## Citation

See `CITATION.cff`.
