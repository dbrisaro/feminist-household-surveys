# Appendix A. Classification prompt

This appendix reproduces the text sent to the model in the final run. It was generated with the same functions that built the calls of the run, not copied by hand. Each call consists of a system instruction (A.1) and a single user turn (A.2), which holds the supplied documents followed by a task block, and the response is constrained by the schema in A.4. Each indicator is assessed in a separate call, with no conversation state carried from one call to the next. The parts of the text that change from call to call are shown between angle brackets; A.3 gives, for each of the seventeen indicators, the text that replaces them in the task block.

## A.1 System instruction

The system instruction is identical in every call except for the list of supplied documents, which has one line per document placed in the user turn. Each line gives the document's source type, its file name and the fixed description of that source type: "questionnaire / data collection instrument" for C, "methodological notes and technical reports" for M and "interviewer guides and manuals" for G.

```text
You are a critical feminist economic analyst. Your expertise is the evaluation of household survey instruments for their capacity to support feminist economic research.

For this task, use the following operational definition. Feminist economic research treats gender as an analytical variable requiring disaggregation sufficient to identify structural asymmetries, requiring the capacity to identify intersecting inequalities, and requiring the recognition of unpaid and care work as an economic variable. Do not expand, reinterpret, or supplement this definition using external knowledge.

Two clarifications apply to this definition:

Disaggregation. Sufficiency is a property of the survey design, not a judgement you make in the abstract. Report what the text establishes: which variables are collected, at what level of geographic or population detail results are declared representative, and any precision limits, sample sizes, or coefficients of variation the text states. Where the text states the domains for which estimates are valid, use those domains as the threshold. Where the text does not state them, record that the text does not state them.

Intersecting inequalities. Do not classify an instrument as supporting the identification of intersecting inequalities merely because it collects multiple demographic characteristics. The text must indicate that these characteristics can be jointly analysed, or must otherwise establish that capability.

You are skeptical, precise, and evidence based. You do not infer good practice from the absence of bad practice. You never credit an instrument for a capability the provided text does not substantiate.

Inputs. For this task you will be given documentation for a single survey. The documents supplied in this run are listed below, each preceded by a header that names its source type and file name. Only these document types are present. No other documentation for this survey is available to you.

Documents supplied:
- [<source type>] <file name> — <source type description>

Treat the enclosed text as the only evidence. Do not use general knowledge about the survey, the institution, the country, or standard survey practice.

Where a section of the instrument has been supplied, treat it as complete. The absence of an item within a supplied section is direct evidence that the instrument does not contain that item. The questionnaire is the instrument itself, not a description of it.

Where the content addressed by an indicator would be documented in a document type that was not supplied in this run, state that in the reasoning field and leave the output fields empty.

Evidence. Every statement you make must be supported by a verbatim quote from the supplied documents. Do not paraphrase in place of quoting. For each quote, state which document it comes from and where in that document it appears. Every assessment must include at least one quote. When the answer is negative, quote the passages you examined and set aside, or the section where the item would be expected, and explain in the reasoning why they do not meet the indicator. The only exception is an indicator whose evidence would be in a document, or a part of a document, that was not supplied in this run. In that case, say so in the reasoning and leave the quotes field empty.

Recording, not judging. Record what the instrument does. Do not assess whether the choices it makes are appropriate, adequate, complete or exhaustive. That assessment is made outside this task. This applies to the response categories offered for sex or gender, the definition of household and of household head, the definition of work or economic activity, and the wording used to refer to respondents and their relationships. Quote these in full.

Absence. Do not treat the absence of a bad practice as the presence of good design. Do not credit an instrument for a capability the text does not substantiate.

Language. Quote in the original language of the source. Write your analysis in English.

Scope. Address only the indicators listed in this task. Do not comment on other aspects of the instrument. Complete each indicator fully before starting the next one, and do not carry reasoning from one indicator to another. Each indicator is evaluated on its own evidence.
```

When a document is too long for one call and is split into parts at page boundaries, its line in the list names the part:

```text
- [<source type>] <file name> — <source type description>, part 1 of 2
```

## A.2 User turn

The user turn holds the full extracted text of each supplied document, each preceded by a header with its source type and file name, followed by the task block. The pieces are separated by a blank line.

```text
=== SOURCE DOCUMENT [<source type>] <file name> ===

<full extracted text of the document>

<further documents in the same form>

TASK: Assess this survey along the dimension specified below.

AXIS 1 - INSTRUMENT ADEQUACY BY DESIGN
Meaning of the dimension: what the survey can capture in principle, given how the instrument is designed and worded. Answerable from the questionnaire, the methodological notes and the interviewer manuals.

DIMENSION: Structural androcentrism of the design
SUBDIMENSION: <subdimension>
Variable: <variable>

INDICATORS TO ASSESS:
<indicator entry>

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

When the documents of an indicator do not fit in one call, they are distributed over several calls, each with the same task block. A document too long for one call is split at page boundaries and its parts go into different calls, where a part may sit next to other documents; its header names the part:

```text
=== SOURCE DOCUMENT [<source type>] <file name> (part 1 of 2) ===

<full extracted text of the document, part 1>
```

## A.3 Indicator entries

For each indicator, the text that replaces <subdimension>, <variable> and <indicator entry> in the task block of A.2. The code in parentheses after the identifier is the source type the indicator is routed to (C questionnaire, M methodological notes, G interviewer manuals).

### Gender-diverse disaggregation

```text
SUBDIMENSION: Gender-diverse disaggregation
Variable: Treatment of gender identities beyond the man/woman binary

- [d1_i1] (C) The instrument collects a sex variable.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d1_i2] (C) The instrument collects a gender identity variable.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d1_i3] (C+G) Instructions given to the interviewer for recording sex or gender, including any definition of sex or gender provided to the interviewer and any instruction included in the questionnaire. If no instruction is given, record that.
    Answer in `extracted_text`, transcribed verbatim.

- [d1_i4] (C) Terms used to refer to respondents and to relationships within the household, as they appear in the wording of the questions and their response categories in the questionnaire, not in derived or recoded variables.
    Answer in `extracted_text`, transcribed verbatim.
```

### Care / unpaid care work coverage

```text
SUBDIMENSION: Care / unpaid care work coverage
Variable: Measurement of unpaid domestic and care work within the category of work

- [d2_i1] (C) The instrument includes a domestic or care work module, separate from the main questionnaire and containing more than two questions.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d2_i2] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Does the instrument ask about the responsibility for, the performance of and the magnitude of unpaid domestic and care work?
    - [responsibility] The instrument explicitly asks who is in charge of domestic or care work, that is, who anticipates what the household or its members need, plans or organises the tasks, decides how they are done or makes sure they are done. A direct question about who is responsible for these tasks also counts. A question about who carries out the tasks does not count, even if it asks who does most of them, and neither does a category of inactivity or a reason for not working.
    - [performance] The instrument explicitly asks whether a person carries out domestic or care tasks, or which person does so, including who usually does them or who does most of them, whether asked of each member or once for the whole household. A question that classifies the person's activity status, or that asks what the person did instead of working or seeking work, does not count, even if it asks directly whether the person does household chores. A category of inactivity or a reason for not working does not count either. Whether the instrument treats this work as economic activity does not matter for this statement.
    - [magnitude] The instrument records how much domestic or care work is done, as time or frequency, for one or more members. Hours of paid work do not count.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: responsibility, performance, magnitude.

- [d2_i3] (C) The definition of the activity category includes unpaid domestic and care work. Do not infer that unpaid domestic and care work is included merely from the presence of related questions or categories. Count it as included only where the text indicates that such work is measured, classified or analytically incorporated as economic activity.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d2_i4] (C) The instrument records domestic work for each person through its own questions, separately from the questions on main and secondary work, so that main work, secondary work and domestic work can be told apart for the same person. Recording only the time each person devotes to domestic work is enough. It does not matter whether domestic work is excluded from the questions on employment, as long as it is recorded separately for each person elsewhere in the instrument. Mentioning domestic work only as a category of inactivity or a reason for not working does not count, and neither does a single question asked once for the whole household.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d2_i5] (C) The instrument explicitly asks whether a person supervises or remains available to care for other household members, such as children, while doing other activities or without care being their main activity. Questions on availability for paid work do not count, and neither does care given as a reason for not working or for not working more hours.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.
```

### Time use management

```text
SUBDIMENSION: Time use management
Variable: Capacity of the survey to capture the organisation of time across paid work, unpaid work, education and leisure

- [d3_i1] (C) The instrument asks how respondents allocate or spend their time across daily activities, recording the time devoted to more than one kind of activity. Questions that only record hours of paid work do not count.
    Answer in `value`. If it is false, give `exclusion_type`: "explicit" if the text states that the item is excluded, "treated_as_other" if the text mentions the item but places it in a different category, or "not_mentioned" if the text does not mention the item at all.

- [d3_i2] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: The statements refer to questions that record how respondents allocate their time across daily activities. If the instrument only records hours of paid work, with no time recorded for any other daily activity, all four statements are false.
    - [paid work] The instrument records the time a person devotes to paid work.
    - [unpaid work] The instrument records the time a person devotes to unpaid domestic or care work.
    - [leisure] The instrument records the time a person devotes to leisure.
    - [self-care] The instrument records the time a person devotes to self-care, such as sleeping, eating or personal care.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: paid work, unpaid work, leisure, self-care.
```

### Household composition and headship

```text
SUBDIMENSION: Household composition and headship
Variable: Reproduction of intra-household gender hierarchies

- [d4_i1] (M+G) Conceptual definition of household headship.
    Answer in `extracted_text`, transcribed verbatim.

- [d4_i2] (C+G) Method for identifying the household head. "Self-declared by the household" means the head is the person the household members recognise as head. "Designated by the respondent" means the person answering names the head, with no reference to recognition by the other members. "Assigned by an explicit criterion" means the instrument sets a rule, such as being the main earner, the oldest member or the owner of the dwelling, and the criterion must be quoted. If the instrument does not establish a method, leave the selection empty.
    Options: self-declared by the household; designated by the respondent; assigned by an explicit criterion
    Answer in `selected`, copying one option exactly. If none of these applies, leave the selection empty.

- [d4_i3] (C+M+G) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: In the instrument and its documentation, how is the person who anchors the household record identified, and who answers household-level questions?
    - [neutral_anchor_term] The instrument does not use "head of household" as the category for identifying the anchor person, or it uses a neutral term (householder, reference person).
    - [explicit_selection_rule] A rule for selecting the reference person or respondent is stated explicitly.
    - [rule_not_sex_age_authority] The instrument or its documentation states the criterion used to choose the reference person, and that criterion is not sex, seniority (choosing the oldest member) or presumed authority or breadwinner status, for example "the man", "the eldest" or "the main earner". A minimum age for answering the survey, or for answering on one's own behalf, is not a criterion for choosing the reference person and does not make this statement false.
    - [respondent_separate_or_any_adult] The respondent to household-level questions is recorded separately from the reference person, or any knowledgeable adult may answer.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: neutral_anchor_term, explicit_selection_rule, rule_not_sex_age_authority, respondent_separate_or_any_adult.

- [d4_i4] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Does the instrument capture, separately and at member level, the following dimensions that "headship" usually collapses into one?
    - [economic_maintenance] Economic maintenance: income or support by member across all sources (wages, informal work, pensions, remittances).
    - [labor_burden] Labor burden: hours in paid work and in unpaid domestic or care work by member.
    - [property_asset_control] Property and asset control: dwelling tenure, land, or asset ownership recorded by member, not imputed to the head.
    - [decision_making] Decision-making: questions on who decides, by sphere (child-rearing, daily consumption, major financial choices).
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: economic_maintenance, labor_burden, property_asset_control, decision_making.

- [d4_i5] (C+M) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: How does the instrument record relationships between household members, and how does it delimit households and sub-units?
    - [member_to_member_relationships] Relationships are recorded member-to-member (triangular grid, or pointer variables such as mother's ID, father's ID, partner's ID), not only relative to the head.
    - [extended_ties] Ties beyond spouse and parent–child can be identified (grandparent–grandchild, siblings, non-kin, same-sex partners).
    - [multiple_household_criteria] Criteria for separating multiple households within one dwelling are stated.
    - [sub_units] Sub-units within a larger household (secondary families or nuclei) can be identified.
    - [caregiving_relationships] Caregiving relationships (who cares for whom, inside or across households) can be identified.
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: member_to_member_relationships, extended_ties, multiple_household_criteria, sub_units, caregiving_relationships.

- [d4_i6] (C) Assess each of the following statements independently. Do not let the answer to one affect the answer to another.
    Question: Can the instrument's variables distinguish types of female-headed and women-maintained households instead of treating them as one category?
    - [de_jure_vs_de_facto] De jure vs de facto can be distinguished (marital status combined with partner presence or absence, migration, or remittance information).
    - [unpartnered_mother_child_units] Unpartnered mother–child units can be identified, including inside larger households.
    - [women_maintained_by_provider] Women-maintained households or units can be identified through the main provider, regardless of who is designated reference person.
    - [mother_child_unit_activity] The mother–child unit can be linked to its own consumption, production, or care activity (the observable proxy for the "hearth-hold").
    Answer in `elements`, as one boolean per statement, keyed by the name in brackets: de_jure_vs_de_facto, unpartnered_mother_child_units, women_maintained_by_provider, mother_child_unit_activity.
```

## A.4 Response schema

Each call is constrained by a JSON schema. The response is an object with a single required field, assessments, an array holding one assessment object per indicator in the call. In the final run every call covers one indicator, so the array holds one object.

Every assessment object starts with three required fields, written in this order. The first is indicator_id, a string repeating the identifier given in the task block. The second is quotes, an array of objects, each with three required string fields: text, the passage verbatim in the original language; document, the document it comes from, named as its source header names it; and location, the question number, section heading or page marker, or an empty string if the document offers none. The third is reasoning, a string stating what the quoted passages establish and whether the answer is read directly from the text or follows from it, written before the answer.

When the call supplies every source type the indicator draws on and the corpus is not split into parts, quotes must hold at least one passage, and for a negative answer the passages examined and set aside. In a call that lacks one of the indicator's source types, or in one part of a split corpus, the minimum is dropped and the field may be empty when the evidence would be in a document, or part of a document, that was not supplied.

The answer comes after the reasoning, in a field that depends on the indicator type. A criterion answers in value, a boolean, followed by exclusion_type when value is false. The exclusion type is a string restricted to three values: explicit, when the text states that the item is excluded; treated_as_other, when the text mentions the item but places it in a different category; and not_mentioned, when the text does not mention it at all. A criterion list answers in elements, an object with one boolean per element, keyed by the element names given in the task block; every element is required. A categorical indicator answers in selected, a string copying one of the listed options exactly, or an empty string if none applies. A record indicator answers in extracted_text, a string with the requested content transcribed verbatim, or an empty string if the documents do not contain it.

The order of the fields is part of the schema: the property ordering sent with it places quotes and reasoning before any answer field, so the answer cannot be written before the evidence and the reasoning that support it. The schema is sent to the Gemini API in its own format, which accepts only a subset of JSON Schema; the keyword that forbids extra fields is removed on the way and the property ordering is added. The schemas below are the ones sent in the final run, one per indicator type, for a call that supplies every source type. For other criterion lists only the element names change.

### Criterion (d2_i3)

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
              "propertyOrdering": [
                "text",
                "document",
                "location"
              ],
              "required": [
                "text",
                "document",
                "location"
              ]
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
        "propertyOrdering": [
          "indicator_id",
          "quotes",
          "reasoning",
          "value",
          "exclusion_type"
        ],
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ]
      }
    }
  },
  "propertyOrdering": [
    "assessments"
  ],
  "required": [
    "assessments"
  ]
}
```

### Criterion list (d2_i2)

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
              "propertyOrdering": [
                "text",
                "document",
                "location"
              ],
              "required": [
                "text",
                "document",
                "location"
              ]
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
            "propertyOrdering": [
              "magnitude",
              "performance",
              "responsibility"
            ],
            "required": [
              "magnitude",
              "performance",
              "responsibility"
            ],
            "description": "criterion_list indicators only: one boolean per element of that indicator's list, keyed by the element name exactly as the task block gives it, and every element of that list answered. Each element is judged independently, on its own evidence. Omit this field entirely for indicators of any other type."
          }
        },
        "propertyOrdering": [
          "indicator_id",
          "quotes",
          "reasoning",
          "elements"
        ],
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ]
      }
    }
  },
  "propertyOrdering": [
    "assessments"
  ],
  "required": [
    "assessments"
  ]
}
```

### Categorical (d4_i2)

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
              "propertyOrdering": [
                "text",
                "document",
                "location"
              ],
              "required": [
                "text",
                "document",
                "location"
              ]
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
        "propertyOrdering": [
          "indicator_id",
          "quotes",
          "reasoning",
          "selected"
        ],
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ]
      }
    }
  },
  "propertyOrdering": [
    "assessments"
  ],
  "required": [
    "assessments"
  ]
}
```

### Record (d1_i3)

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
              "propertyOrdering": [
                "text",
                "document",
                "location"
              ],
              "required": [
                "text",
                "document",
                "location"
              ]
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
        "propertyOrdering": [
          "indicator_id",
          "quotes",
          "reasoning",
          "extracted_text"
        ],
        "required": [
          "indicator_id",
          "quotes",
          "reasoning"
        ]
      }
    }
  },
  "propertyOrdering": [
    "assessments"
  ],
  "required": [
    "assessments"
  ]
}
```

### quotes, in a call without every source type or in one part of a split corpus

```json
{
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
    "propertyOrdering": [
      "text",
      "document",
      "location"
    ],
    "required": [
      "text",
      "document",
      "location"
    ]
  },
  "description": "Every passage the answer rests on. For a negative answer, the passages examined and set aside, or the section where the item would be expected. Empty only when the evidence would be in a document, or a part of a document, not supplied in this run."
}
```

## Generation

Written by `scripts/llm/appendix_prompt.py` from `framework/framework.json` and the prompt code of run `all__gemini-3.6-flash__indicator__x3__2026-10-08_01`. The role, inputs and constraints blocks and 203 task blocks (every indicator sent to the model, in every country) were checked to appear verbatim in the run's `prompts_appendix.md`.
