# Prompt appendix — United_Kingdom

Framework: **Structural androcentrism of the design**, parsed from `Prompting/gender_survey_framework.html` (the analytical framework is the single source of truth; this file is generated from it, never hand-edited).

Generated 2026-10-08 20:17 UTC · models: gemini-3.6-flash · modes: indicator · effort: not applicable (the Gemini API takes no effort parameter; `--effort medium` was accepted but not sent) · max_output_tokens: indicator=16000 (--max-output-tokens) · thinking tokens are billed out of this ceiling

Every call is a single user turn against the Gemini API with a structured-output schema (below). No conversation state carries between indicators: each assessment is independent, and the only evidence available to the model is the source documents listed in each entry.

## 1. Shared scaffold (system prompt)

Lifted verbatim from the `scaffold` object in `Prompting/gender_survey_framework.html`. Role and Constraints are identical, byte for byte, in every call.

### Role

```text
You are a critical feminist economic analyst. Your expertise is the evaluation of household survey instruments for their capacity to support feminist economic research.

For this task, use the following operational definition. Feminist economic research treats gender as an analytical variable requiring disaggregation sufficient to identify structural asymmetries, requiring the capacity to identify intersecting inequalities, and requiring the recognition of unpaid and care work as an economic variable. Do not expand, reinterpret, or supplement this definition using external knowledge.

Two clarifications apply to this definition:

Disaggregation. Sufficiency is a property of the survey design, not a judgement you make in the abstract. Report what the text establishes: which variables are collected, at what level of geographic or population detail results are declared representative, and any precision limits, sample sizes, or coefficients of variation the text states. Where the text states the domains for which estimates are valid, use those domains as the threshold. Where the text does not state them, record that the text does not state them.

Intersecting inequalities. Do not classify an instrument as supporting the identification of intersecting inequalities merely because it collects multiple demographic characteristics. The text must indicate that these characteristics can be jointly analysed, or must otherwise establish that capability.

You are skeptical, precise, and evidence based. You do not infer good practice from the absence of bad practice. You never credit an instrument for a capability the provided text does not substantiate.
```

### Inputs (template)

```text
Inputs. For this task you will be given documentation for a single survey. The documents supplied in this run are listed below, each preceded by a header that names its source type and file name. Only these document types are present. No other documentation for this survey is available to you.

Documents supplied:
{documents}

Treat the enclosed text as the only evidence. Do not use general knowledge about the survey, the institution, the country, or standard survey practice.

Where a section of the instrument has been supplied, treat it as complete. The absence of an item within a supplied section is direct evidence that the instrument does not contain that item. The questionnaire is the instrument itself, not a description of it.

Where the content addressed by an indicator would be documented in a document type that was not supplied in this run, state that in the reasoning field and leave the output fields empty.
```

### Constraints

```text
Evidence. Every statement you make must be supported by a verbatim quote from the supplied documents. Do not paraphrase in place of quoting. For each quote, state which document it comes from and where in that document it appears. Every assessment must include at least one quote. When the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, and explain in the reasoning why they do not meet the indicator. The only exception is an indicator whose evidence would be in a document, or a part of a document, that was not supplied in this run. In that case, say so in the reasoning and leave the quotes field empty.

Recording, not judging. Record what the instrument does. Do not assess whether the choices it makes are appropriate, adequate, complete or exhaustive. That assessment is made outside this task. This applies to the response categories offered for sex or gender, the definition of household and of household head, the definition of work or economic activity, and the wording used to refer to respondents and their relationships. Quote these in full.

Absence. Do not treat the absence of a bad practice as the presence of good design. Do not credit an instrument for a capability the text does not substantiate.

Language. Quote in the original language of the source. Write your analysis in English.

Scope. Address only the indicators listed in this task. Do not comment on other aspects of the instrument. Complete each indicator fully before starting the next one, and do not carry reasoning from one indicator to another. Each indicator is evaluated on its own evidence.
```

## 2. Method block

Appended to every task block, after the indicator list.

```text
Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.
```

## 3. Required output schema

The schema is built per call, from the indicator types that call covers: `indicator_id`, `quotes` and `reasoning` are always required, and each type adds its own answer field after them. Field order is part of the contract — the evidence and the reasoning are written before the answer.

**criterion** (as sent for `d1_i1`)

```json
{
  "type": "object",
  "properties": {
    "assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "indicator_id": {
            "type": "string"
          },
          "quotes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation."
                },
                "document": {
                  "type": "string",
                  "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it."
                },
                "location": {
                  "type": "string",
                  "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none."
                }
              },
              "required": [
                "text",
                "document",
                "location"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected."
          },
          "reasoning": {
            "type": "string",
            "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after."
          },
          "value": {
            "type": "boolean",
            "description": "criterion only: whether the proposition stated by the indicator holds, on the evidence quoted above."
          },
          "exclusion_type": {
            "type": "string",
            "enum": [
              "explicit",
              "treated_as_other",
              "not_mentioned"
            ],
            "description": "criterion only, and only when `value` is false. One of: \"explicit\": the text states that the item is excluded, for example by asking about work \"without counting\" household tasks, or by instructing the interviewer to reclassify it. \"treated_as_other\": the text mentions the item but places it in a different category, for example as a category of inactivity or as a reason for not working or not seeking work. \"not_mentioned\": the text does not mention the item at all."
          }
        },
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "assessments"
  ],
  "additionalProperties": false
}
```

**criterion_list** (as sent for `d2_i2`)

```json
{
  "type": "object",
  "properties": {
    "assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "indicator_id": {
            "type": "string"
          },
          "quotes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation."
                },
                "document": {
                  "type": "string",
                  "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it."
                },
                "location": {
                  "type": "string",
                  "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none."
                }
              },
              "required": [
                "text",
                "document",
                "location"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected."
          },
          "reasoning": {
            "type": "string",
            "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after."
          },
          "elements": {
            "type": "object",
            "properties": {
              "magnitude": {
                "type": "boolean"
              },
              "performance": {
                "type": "boolean"
              },
              "responsibility": {
                "type": "boolean"
              }
            },
            "required": [
              "magnitude",
              "performance",
              "responsibility"
            ],
            "additionalProperties": false,
            "description": "criterion_list indicators only: one boolean per element of that indicator's list, keyed by the element name exactly as the task block gives it, and every element of that list answered. Each element is judged independently, on its own evidence. Omit this field entirely for indicators of any other type."
          }
        },
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "assessments"
  ],
  "additionalProperties": false
}
```

**categorical** (as sent for `d4_i2`)

```json
{
  "type": "object",
  "properties": {
    "assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "indicator_id": {
            "type": "string"
          },
          "quotes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation."
                },
                "document": {
                  "type": "string",
                  "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it."
                },
                "location": {
                  "type": "string",
                  "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none."
                }
              },
              "required": [
                "text",
                "document",
                "location"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected."
          },
          "reasoning": {
            "type": "string",
            "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after."
          },
          "selected": {
            "type": "string",
            "description": "categorical only: the one option chosen, copied exactly from the options listed for that indicator. Empty string if none of them applies."
          }
        },
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "assessments"
  ],
  "additionalProperties": false
}
```

**record** (as sent for `d1_i3`)

```json
{
  "type": "object",
  "properties": {
    "assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "indicator_id": {
            "type": "string"
          },
          "quotes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation."
                },
                "document": {
                  "type": "string",
                  "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it."
                },
                "location": {
                  "type": "string",
                  "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none."
                }
              },
              "required": [
                "text",
                "document",
                "location"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected."
          },
          "reasoning": {
            "type": "string",
            "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after."
          },
          "extracted_text": {
            "type": "string",
            "description": "record only, when the indicator names no separate fields: the content requested, transcribed verbatim. Empty string if the documents do not contain it."
          }
        },
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "assessments"
  ],
  "additionalProperties": false
}
```

**A mixed subdimension call** covers several types at once, so its item schema is the union of their answer fields:

```json
{
  "type": "object",
  "properties": {
    "assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "indicator_id": {
            "type": "string"
          },
          "quotes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "The passage, verbatim, in the original language of the document. Never a paraphrase or a translation."
                },
                "document": {
                  "type": "string",
                  "description": "The document the passage comes from, named as its SOURCE DOCUMENT header names it."
                },
                "location": {
                  "type": "string",
                  "description": "Question number, section heading or page marker locating the passage in that document. Empty string if the document offers none."
                }
              },
              "required": [
                "text",
                "document",
                "location"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected."
          },
          "reasoning": {
            "type": "string",
            "description": "What the quoted passages establish, and whether the answer is read directly from the text or follows from it. Write this before answering, not after."
          },
          "elements": {
            "type": "object",
            "properties": {
              "caregiving_relationships": {
                "type": "boolean"
              },
              "de_jure_vs_de_facto": {
                "type": "boolean"
              },
              "decision_making": {
                "type": "boolean"
              },
              "economic_maintenance": {
                "type": "boolean"
              },
              "explicit_selection_rule": {
                "type": "boolean"
              },
              "extended_ties": {
                "type": "boolean"
              },
              "labor_burden": {
                "type": "boolean"
              },
              "member_to_member_relationships": {
                "type": "boolean"
              },
              "mother_child_unit_activity": {
                "type": "boolean"
              },
              "multiple_household_criteria": {
                "type": "boolean"
              },
              "neutral_anchor_term": {
                "type": "boolean"
              },
              "property_asset_control": {
                "type": "boolean"
              },
              "respondent_separate_or_any_adult": {
                "type": "boolean"
              },
              "rule_not_sex_age_authority": {
                "type": "boolean"
              },
              "sub_units": {
                "type": "boolean"
              },
              "unpartnered_mother_child_units": {
                "type": "boolean"
              },
              "women_maintained_by_provider": {
                "type": "boolean"
              }
            },
            "required": [
              "caregiving_relationships",
              "de_jure_vs_de_facto",
              "decision_making",
              "economic_maintenance",
              "explicit_selection_rule",
              "extended_ties",
              "labor_burden",
              "member_to_member_relationships",
              "mother_child_unit_activity",
              "multiple_household_criteria",
              "neutral_anchor_term",
              "property_asset_control",
              "respondent_separate_or_any_adult",
              "rule_not_sex_age_authority",
              "sub_units",
              "unpartnered_mother_child_units",
              "women_maintained_by_provider"
            ],
            "additionalProperties": false,
            "description": "criterion_list indicators only: one boolean per element of that indicator's list, keyed by the element name exactly as the task block gives it, and every element of that list answered. Each element is judged independently, on its own evidence. Omit this field entirely for indicators of any other type."
          },
          "selected": {
            "type": "string",
            "description": "categorical only: the one option chosen, copied exactly from the options listed for that indicator. Empty string if none of them applies."
          },
          "extracted_text": {
            "type": "string",
            "description": "record only, when the indicator names no separate fields: the content requested, transcribed verbatim. Empty string if the documents do not contain it."
          }
        },
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "assessments"
  ],
  "additionalProperties": false
}
```

## 4. Per-indicator task blocks

The user turn is the source documents (verbatim extracted text) followed by the task block.

### Subdimension 1 — Gender-diverse disaggregation

*Variable:* Treatment of gender identities beyond the man/woman binary

#### `d1_i1` · source `C`

> The instrument collects a sex variable.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,642 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Gender-diverse disaggregation
Variable: Treatment of gender identities beyond the man/woman binary

INDICATORS TO ASSESS:
- [d1_i1] (C) The instrument collects a sex variable.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d1_i2` · source `C`

> The instrument collects a gender identity variable.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,643 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Gender-diverse disaggregation
Variable: Treatment of gender identities beyond the man/woman binary

INDICATORS TO ASSESS:
- [d1_i2] (C) The instrument collects a gender identity variable.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d1_i3` · source `C+G`

> Instructions given to the interviewer for recording sex or gender, including any definition of sex or gender provided to the interviewer and any instruction included in the questionnaire. If no instruction is given, record that.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,619 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Gender-diverse disaggregation
Variable: Treatment of gender identities beyond the man/woman binary

INDICATORS TO ASSESS:
- [d1_i3] (C+G) Instructions given to the interviewer for recording sex or gender, including any definition of sex or gender provided to the interviewer and any instruction included in the questionnaire. If no instruction is given, record that.
    Answer in `extracted_text`, transcribed verbatim.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d1_i4` · source `C`

> Terms used to refer to respondents and to relationships within the household, as they appear in the wording of the questions and their response categories in the questionnaire, not in derived or recoded variables.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,616 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Gender-diverse disaggregation
Variable: Treatment of gender identities beyond the man/woman binary

INDICATORS TO ASSESS:
- [d1_i4] (C) Terms used to refer to respondents and to relationships within the household, as they appear in the wording of the questions and their response categories in the questionnaire, not in derived or recoded variables.
    Answer in `extracted_text`, transcribed verbatim.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

### Subdimension 2 — Care / unpaid care work coverage

*Variable:* Measurement of unpaid domestic and care work within the category of work

#### `d2_i1` · source `C`

> The instrument includes a domestic or care work module, separate from the main questionnaire and containing more than two questions.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,660 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

INDICATORS TO ASSESS:
- [d2_i1] (C) The instrument includes a domestic or care work module, separate from the main questionnaire and containing more than two questions.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d2_i2` · source `C`

> Does the instrument ask about the responsibility for, the performance of and the magnitude of unpaid domestic and care work?

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,902 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

INDICATORS TO ASSESS:
- [d2_i2] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Does the instrument ask about the responsibility for, the performance of and the magnitude of unpaid domestic and care work?
    - [responsibility] The instrument explicitly asks who is in charge of domestic or care work, that is, who anticipates what the household or its members need, plans or organises the tasks, decides how they are done or makes sure they are done. A direct question about who is responsible for these tasks also counts. A question about who carries out the tasks does not count, even if it asks who does most of them, and neither does a category of inactivity or a reason for not working.
    - [performance] The instrument explicitly asks whether a person carries out domestic or care tasks, or which person does so, including who usually does them or who does most of them, whether asked of each member or once for the whole household. A question that classifies the person's activity status, or that asks what the person did instead of working or seeking work, does not count, even if it asks directly whether the person does household chores. A category of inactivity or a reason for not working does not count either. Whether the instrument treats this work as economic activity does not matter for this statement.
    - [magnitude] The instrument records how much domestic or care work is done, as time or frequency, for one or more members. Hours of paid work do not count.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: responsibility, performance, magnitude.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d2_i3` · source `C`

> The definition of the activity category includes unpaid domestic and care work. Do not infer that unpaid domestic and care work is included merely from the presence of related questions or categories. Count it as included only where the text indicates that such work is measured, classified or analytically incorporated as economic activity.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,695 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

INDICATORS TO ASSESS:
- [d2_i3] (C) The definition of the activity category includes unpaid domestic and care work. Do not infer that unpaid domestic and care work is included merely from the presence of related questions or categories. Count it as included only where the text indicates that such work is measured, classified or analytically incorporated as economic activity.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d2_i4` · source `C`

> The instrument records domestic work for each person through its own questions, separately from the questions on main and secondary work, so that main work, secondary work and domestic work can be told apart for the same person. Recording only the time each person devotes to domestic work is enough. It does not matter whether domestic work is excluded from the questions on employment, as long as it is recorded separately for each person elsewhere in the instrument. Mentioning domestic work only as a category of inactivity or a reason for not working does not count, and neither does a single question asked once for the whole household.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,756 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

INDICATORS TO ASSESS:
- [d2_i4] (C) The instrument records domestic work for each person through its own questions, separately from the questions on main and secondary work, so that main work, secondary work and domestic work can be told apart for the same person. Recording only the time each person devotes to domestic work is enough. It does not matter whether domestic work is excluded from the questions on employment, as long as it is recorded separately for each person elsewhere in the instrument. Mentioning domestic work only as a category of inactivity or a reason for not working does not count, and neither does a single question asked once for the whole household.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d2_i5` · source `C`

> The instrument explicitly asks whether a person supervises or remains available to care for other household members, such as children, while doing other activities or without care being their main activity. Questions on availability for paid work do not count, and neither does care given as a reason for not working or for not working more hours.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,701 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

INDICATORS TO ASSESS:
- [d2_i5] (C) The instrument explicitly asks whether a person supervises or remains available to care for other household members, such as children, while doing other activities or without care being their main activity. Questions on availability for paid work do not count, and neither does care given as a reason for not working or for not working more hours.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

### Subdimension 3 — Time use management

*Variable:* Capacity of the survey to capture the organisation of time across paid work, unpaid work, education and leisure

#### `d3_i1` · source `C`

> The instrument asks how respondents allocate or spend their time across daily activities, recording the time devoted to more than one kind of activity. Questions that only record hours of paid work do not count.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,681 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Time use management
Variable: Capacity of the survey to capture the organisation of time across paid work, unpaid work, education and leisure

INDICATORS TO ASSESS:
- [d3_i1] (C) The instrument asks how respondents allocate or spend their time across daily activities, recording the time devoted to more than one kind of activity. Questions that only record hours of paid work do not count.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d3_i2` · source `C`

> The statements refer to questions that record how respondents allocate their time across daily activities. If the instrument only records hours of paid work, with no time recorded for any other daily activity, all four statements are false.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,763 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Time use management
Variable: Capacity of the survey to capture the organisation of time across paid work, unpaid work, education and leisure

INDICATORS TO ASSESS:
- [d3_i2] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: The statements refer to questions that record how respondents allocate their time across daily activities. If the instrument only records hours of paid work, with no time recorded for any other daily activity, all four statements are false.
    - [paid work] The instrument records the time a person devotes to paid work.
    - [unpaid work] The instrument records the time a person devotes to unpaid domestic or care work.
    - [leisure] The instrument records the time a person devotes to leisure.
    - [self-care] The instrument records the time a person devotes to self-care, such as sleeping, eating or personal care.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: paid work, unpaid work, leisure, self-care.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

### Subdimension 4 — Household composition and headship

*Variable:* Reproduction of intra-household gender hierarchies

#### `d4_i1` · source `M+G`

> Conceptual definition of household headship.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `M` (136,522 input tokens).

Documents supplied:

- `lfsugvoltcm77238281.pdf` → `data/processed/text/united_kingdom/lfsugvoltcm77238281.txt` — 234,017 chars, sha256 `fa3d31577b7a2fd8…`
- `volume1main2024updatedfeb25.pdf` → `data/processed/text/united_kingdom/volume1main2024updatedfeb25.txt` — 336,992 chars, sha256 `8707d77cc69cec14…`

`{documents}` resolved to:

```text
- [M] lfsugvoltcm77238281.pdf — methodological notes and technical reports
- [M] volume1main2024updatedfeb25.pdf — methodological notes and technical reports
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i1] (M+G) Conceptual definition of household headship.
    Answer in `extracted_text`, transcribed verbatim.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d4_i2` · source `C+G`

> Method for identifying the household head. "Self-declared by the household" means the head is the person the household members recognise as head. "Designated by the respondent" means the person answering names the head, with no reference to recognition by the other members. "Assigned by an explicit criterion" means the instrument sets a rule, such as being the main earner, the oldest member or the owner of the dwelling, and the criterion must be quoted. If the instrument does not establish a method, leave the selection empty.

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,716 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i2] (C+G) Method for identifying the household head. "Self-declared by the household" means the head is the person the household members recognise as head. "Designated by the respondent" means the person answering names the head, with no reference to recognition by the other members. "Assigned by an explicit criterion" means the instrument sets a rule, such as being the main earner, the oldest member or the owner of the dwelling, and the criterion must be quoted. If the instrument does not establish a method, leave the selection empty.
    Options: self-declared by the household; designated by the respondent; assigned by an explicit criterion
    Answer in `selected`, copying one option exactly. If none of these applies, leave the selection empty.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d4_i3` · source `C+M+G`

> In the instrument and its documentation, how is the person who anchors the household record identified, and who answers household-level questions?

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C+M#1/2` (156,724 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`
- `lfsugvoltcm77238281.pdf` → `data/processed/text/united_kingdom/lfsugvoltcm77238281.txt` — 234,017 chars, sha256 `fa3d31577b7a2fd8…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
- [M] lfsugvoltcm77238281.pdf — methodological notes and technical reports
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i3] (C+M+G) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: In the instrument and its documentation, how is the person who anchors the household record identified, and who answers household-level questions?
    - [neutral_anchor_term] The instrument does not use "head of household" as the category for identifying the anchor person, or it uses a neutral term (householder, reference person).
    - [explicit_selection_rule] A rule for selecting the reference person or respondent is stated explicitly.
    - [rule_not_sex_age_authority] The instrument or its documentation states the criterion used to choose the reference person, and that criterion is not sex, seniority (choosing the oldest member) or presumed authority or breadwinner status, for example "the man", "the eldest" or "the main earner". A minimum age for answering the survey, or for answering on one's own behalf, is not a criterion for choosing the reference person and does not make this statement false.
    - [respondent_separate_or_any_adult] The respondent to household-level questions is recorded separately from the reference person, or any knowledgeable adult may answer.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: neutral_anchor_term, explicit_selection_rule, rule_not_sex_age_authority, respondent_separate_or_any_adult.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d4_i4` · source `C`

> Does the instrument capture, separately and at member level, the following dimensions that "headship" usually collapses into one?

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,770 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i4] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Does the instrument capture, separately and at member level, the following dimensions that "headship" usually collapses into one?
    - [economic_maintenance] Economic maintenance: income or support by member across all sources (wages, informal work, pensions, remittances).
    - [labor_burden] Labor burden: hours in paid work and in unpaid domestic or care work by member.
    - [property_asset_control] Property and asset control: dwelling tenure, land, or asset ownership recorded by member, not imputed to the head.
    - [decision_making] Decision-making: questions on who decides, by sphere (child-rearing, daily consumption, major financial choices).
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: economic_maintenance, labor_burden, property_asset_control, decision_making.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d4_i5` · source `C+M`

> How does the instrument record relationships between household members, and how does it delimit households and sub-units?

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C+M#1/2` (156,667 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`
- `lfsugvoltcm77238281.pdf` → `data/processed/text/united_kingdom/lfsugvoltcm77238281.txt` — 234,017 chars, sha256 `fa3d31577b7a2fd8…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
- [M] lfsugvoltcm77238281.pdf — methodological notes and technical reports
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i5] (C+M) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: How does the instrument record relationships between household members, and how does it delimit households and sub-units?
    - [member_to_member_relationships] Relationships are recorded member-to-member (triangular grid, or pointer variables such as mother's ID, father's ID, partner's ID), not only relative to the head.
    - [extended_ties] Ties beyond spouse and parent–child can be identified (grandparent–grandchild, siblings, non-kin, same-sex partners).
    - [multiple_household_criteria] Criteria for separating multiple households within one dwelling are stated.
    - [sub_units] Sub-units within a larger household (secondary families or nuclei) can be identified.
    - [caregiving_relationships] Caregiving relationships (who cares for whom, inside or across households) can be identified.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: member_to_member_relationships, extended_ties, multiple_household_criteria, sub_units, caregiving_relationships.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

#### `d4_i6` · source `C`

> Can the instrument's variables distinguish types of female-headed and women-maintained households instead of treating them as one category?

**Mode `indicator`** — assessed in a call of its own. Evidence corpus `C` (102,818 input tokens).

Documents supplied:

- `volume2octtodec2025.pdf` → `data/processed/text/united_kingdom/volume2octtodec2025.txt` — 507,864 chars, sha256 `6e390d7af36d6e62…`

`{documents}` resolved to:

```text
- [C] volume2octtodec2025.pdf — questionnaire / data collection instrument
```

Task block:

```text
TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

INDICATORS TO ASSESS:
- [d4_i6] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Can the instrument's variables distinguish types of female-headed and women-maintained households instead of treating them as one category?
    - [de_jure_vs_de_facto] De jure vs de facto can be distinguished (marital status combined with partner presence or absence, migration, or remittance information).
    - [unpartnered_mother_child_units] Unpartnered mother–child units can be identified, including inside larger households.
    - [women_maintained_by_provider] Women-maintained households or units can be identified through the main provider, regardless of who is designated reference person.
    - [mother_child_unit_activity] The mother–child unit can be linked to its own consumption, production, or care activity (the observable proxy for the "hearth-hold").
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: de_jure_vs_de_facto, unpartnered_mother_child_units, women_maintained_by_provider, mother_child_unit_activity.

Method. For each indicator listed in this task, in order:

a) Identify the indicator type: criterion, criterion_list, categorical or record.
b) Search the supplied documents for passages that bear on the indicator.
c) Quote the relevant passages verbatim, in the original language, with the document name and a location (question number, section heading or page marker). If the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, unless the exception stated under Evidence applies.
d) Write the reasoning field: state what the quoted passages establish, and whether the conclusion is read directly from the text or follows from it.
e) Produce the output for that indicator type:
   criterion: state whether the proposition is true or false. If false, state whether the text explicitly excludes the item, mentions it but places it in a different category, or does not mention it at all.
   criterion_list: state true or false for each element of the list, independently.
   categorical: select one option from the list supplied. If none applies, leave the selection empty.
   record: transcribe the content requested, verbatim.
f) Do not assign an overall label, a score, or a verdict of adequacy. Labels are assigned outside this task.

Complete steps a to f for one indicator before starting the next.

Return one assessment object per indicator listed above, using the indicator_id exactly as given.
```

