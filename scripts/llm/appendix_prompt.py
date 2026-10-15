"""Write Appendix A of the paper (the classification prompt) from the code that built the final run's calls.

A.1 system instruction and A.2 user turn come from prompts.system_prompt(), corpus.build_shards() and
prompts.dimension_block(), fed placeholder documents and a placeholder subdimension so that the parts
that vary between calls print as <angle-bracket> markers. A.3 is prompts.indicator_lines() for the 17
indicators; A.4 is prompts.output_schema() as run_eval_gemini.gemini_schema() sent it. Nothing is typed
by hand, so the appendix cannot drift from what the model received.

Before writing, every generated piece is checked against the run's own prompts_appendix.md in each
country: the role, inputs and constraints blocks, and the full task block of every indicator that was
sent. A mismatch stops the script.

    python scripts/llm/appendix_prompt.py
    python scripts/llm/appendix_prompt.py --dir outputs/final_run_2026-10-08 --run all__gemini-3.6-flash__indicator__x3__2026-10-08_01
"""
import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus  # noqa: E402
import framework as framework_mod  # noqa: E402
import prompts as P  # noqa: E402
from run_eval_gemini import gemini_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUN = "all__gemini-3.6-flash__indicator__x3__2026-10-08_01"

CODE, NAME, LABEL = "<source type>", "<file name>", "<source type description>"
TEXT = "<full extracted text of the document>"
SUB = {"title": "<subdimension>", "variable": "<variable>"}
ENTRY = "<indicator entry>"


def placeholder_blocks(split: bool):
    """Document blocks and manifest for one placeholder document, whole or in two parts, as
    corpus.build_shards() emits them. The fake token counter only decides whether the document is
    split: it makes the two-page text too large for one call and each page small enough for one."""
    budget = corpus.SHARD_BUDGET_TOKENS
    if split:
        text = TEXT.replace("document", "document, part 1") + "\f" + TEXT.replace("document", "document, part 2")
        count = lambda t: 2 * budget if "\f" in t else 1  # noqa: E731
    else:
        text, count = TEXT, (lambda t: 1)
    doc = corpus.Doc(CODE, NAME, ROOT / "placeholder.txt", text)
    (blocks, manifest, _), = corpus.build_shards("placeholder", (CODE,), {CODE: [doc]}, count)
    return blocks, manifest


def task_template(fw) -> str:
    """The task block with the subdimension, variable and indicator entry left as markers."""
    ind = fw["subdimensions"][0]["indicators"][0]
    block = P.dimension_block(fw["dimension"], SUB, [ind])
    entry = "\n".join(P.indicator_lines(ind))
    assert block.count(entry) == 1
    return block.replace(entry, ENTRY)


def check(fw, run: str) -> int:
    """Every generated piece must appear verbatim in each country's prompts_appendix.md."""
    apps = {Path(p).parts[-4]: Path(p).read_text(encoding="utf-8")
            for p in glob.glob(str(ROOT / f"outputs/*/runs/{run}/prompts_appendix.md"))}
    if len(apps) != 12:
        sys.exit(f"expected 12 run appendices for {run}, found {sorted(apps)}")
    before, after = P.INPUTS.split(P.DOCUMENTS_PLACEHOLDER)
    for c, t in apps.items():
        for name, piece in (("role", P.ROLE), ("inputs", before.strip()), ("inputs", after.strip()),
                            ("constraints", P.CONSTRAINTS)):
            if piece not in t:
                sys.exit(f"{c}: {name} block differs from the run")
    checked = 0
    for s in fw["subdimensions"]:
        for i in s["indicators"]:
            block = P.dimension_block(fw["dimension"], s, [i])
            for c, t in apps.items():
                head = f"#### `{i['indicator_id']}`"
                if head not in t:
                    continue
                section = t.split(head, 1)[1].split("\n#### ", 1)[0]
                if "Not sent to the model" in section:
                    continue  # source_missing: no call was made
                if block not in section:
                    sys.exit(f"{c} {i['indicator_id']}: task block differs from the run")
                checked += 1
    # A split document is listed with its part in some country, as the placeholder shows it.
    if not any(", part 1 of " in t for t in apps.values()):
        sys.exit("no split document found in the run appendices")
    return checked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "outputs" / "final_run_2026-10-08")
    ap.add_argument("--run", default=RUN)
    args = ap.parse_args()
    out_dir = args.dir if args.dir.is_absolute() else ROOT / args.dir

    fw = framework_mod.load()
    subs = fw["subdimensions"]
    inds = [i for s in subs for i in s["indicators"]]
    checked = check(fw, args.run)
    labels = {CODE: LABEL}

    whole, whole_man = placeholder_blocks(split=False)
    parts, parts_man = placeholder_blocks(split=True)
    codes = framework_mod.source_codes()

    L = ["# Appendix A. Classification prompt", "",
         "This appendix reproduces the text sent to the model in the final run. It was generated with the same "
         "functions that built the calls of the run, not copied by hand. Each call consists of a system "
         "instruction (A.1) and a single user turn (A.2), which holds the supplied documents followed by a task "
         "block, and the response is constrained by the schema in A.4. Each indicator is assessed in a separate "
         "call, with no conversation state carried from one call to the next. The parts of the text that change "
         "from call to call are shown between angle brackets; A.3 gives, for each of the seventeen indicators, the "
         "text that replaces them in the task block.", "",
         "## A.1 System instruction", "",
         "The system instruction is identical in every call except for the list of supplied documents, which has "
         "one line per document placed in the user turn. Each line gives the document's source type, its file name "
         f"and the fixed description of that source type: \"{codes['C']}\" for C, \"{codes['M']}\" for M and "
         f"\"{codes['G']}\" for G.", "",
         "```text", P.system_prompt(whole_man, labels), "```", "",
         "When a document is too long for one call and is split into parts at page boundaries, its line in the "
         "list names the part:", "",
         "```text", P.documents_supplied(parts_man[:1], labels), "```", "",
         "## A.2 User turn", "",
         "The user turn holds the full extracted text of each supplied document, each preceded by a header with "
         "its source type and file name, followed by the task block. The pieces are separated by a blank line.", "",
         "```text", *[b + "\n" for b in whole], "<further documents in the same form>", "", task_template(fw), "```", "",
         "When the documents of an indicator do not fit in one call, they are distributed over several calls, "
         "each with the same task block. A document too long for one call is split at page boundaries and its "
         "parts go into different calls, where a part may sit next to other documents; its header names the "
         "part:", "",
         "```text", parts[0], "```", ""]

    # A.3
    L += ["## A.3 Indicator entries", "",
          "For each indicator, the text that replaces <subdimension>, <variable> and <indicator entry> in the "
          "task block of A.2. The code in parentheses after the identifier is the source type the indicator is "
          "routed to (C questionnaire, M methodological notes, G interviewer manuals).", ""]
    for s in subs:
        L += [f"### {s['title']}", "", "```text", f"SUBDIMENSION: {s['title']}", f"Variable: {s['variable']}", ""]
        for n, i in enumerate(s["indicators"]):
            L += P.indicator_lines(i)
            if n < len(s["indicators"]) - 1:
                L.append("")
        L += ["```", ""]

    # A.4
    crit = next(i for i in inds if i["indicator_id"] == "d2_i3")
    clist = next(i for i in inds if i["indicator_id"] == "d2_i2")
    cat = next(i for i in inds if i["type"] == "categorical")
    rec = next(i for i in inds if i["indicator_id"] == "d1_i3")
    excl = P.EXCLUSION_TYPES
    L += ["## A.4 Response schema", "",
          "Each call is constrained by a JSON schema. The response is an object with a single required field, "
          "assessments, an array holding one assessment object per indicator in the call. In the final run every "
          "call covers one indicator, so the array holds one object.", "",
          "Every assessment object starts with three required fields, written in this order. The first is "
          "indicator_id, a string repeating the identifier given in the task block. The second is quotes, an "
          "array of objects, each with three required string fields: text, the passage verbatim in the original "
          "language; document, the document it comes from, named as its source header names it; and location, "
          "the question number, section heading or page marker, or an empty string if the document offers none. "
          "The third is reasoning, a string stating what the quoted passages establish and whether the answer is "
          "read directly from the text or follows from it, written before the answer.", "",
          "When the call supplies every source type the indicator draws on and the corpus is not split into "
          "parts, quotes must hold at least one passage, and for a negative answer the passages examined and set "
          "aside. In a call that lacks one of the indicator's source types, or in one part of a split corpus, the "
          "minimum is dropped and the field may be empty when the evidence would be in a document, or part of a "
          "document, that was not supplied.", "",
          "The answer comes after the reasoning, in a field that depends on the indicator type. A criterion "
          "answers in value, a boolean, followed by exclusion_type when value is false. The exclusion type is a "
          f"string restricted to three values: {excl[0]}, when the text states that the item is excluded; "
          f"{excl[1]}, when the text mentions the item but places it in a different category; and {excl[2]}, "
          "when the text does not mention it at all. A criterion list answers in elements, an object with one "
          "boolean per element, keyed by the element names given in the task block; every element is required. "
          "A categorical indicator answers in selected, a string copying one of the listed options exactly, or "
          "an empty string if none applies. A record indicator answers in extracted_text, a string with the "
          "requested content transcribed verbatim, or an empty string if the documents do not contain it.", "",
          "The order of the fields is part of the schema: the property ordering sent with it places quotes and "
          "reasoning before any answer field, so the answer cannot be written before the evidence and the "
          "reasoning that support it. The schema is sent to the Gemini API in its own format, which accepts only "
          "a subset of JSON Schema; the keyword that forbids extra fields is removed on the way and the property "
          "ordering is added. The schemas below are the ones sent in the final run, one per indicator type, for a "
          "call that supplies every source type. For other criterion lists only the element names change.", ""]
    for label, i in (("Criterion (d2_i3)", crit), ("Criterion list (d2_i2)", clist),
                     (f"Categorical ({cat['indicator_id']})", cat), ("Record (d1_i3)", rec)):
        L += [f"### {label}", "", "```json",
              json.dumps(gemini_schema(P.output_schema([i], complete=True)), indent=2, ensure_ascii=False),
              "```", ""]
    quotes = gemini_schema(P.output_schema([crit], complete=False))["properties"]["assessments"]["items"]
    L += ["### quotes, in a call without every source type or in one part of a split corpus", "", "```json",
          json.dumps(quotes["properties"]["quotes"], indent=2, ensure_ascii=False), "```", "",
          "## Generation", "",
          f"Written by `scripts/llm/appendix_prompt.py` from `framework/framework.json` and the prompt code of run "
          f"`{args.run}`. The role, inputs and constraints blocks and {checked} task blocks (every indicator sent "
          "to the model, in every country) were checked to appear verbatim in the run's `prompts_appendix.md`.", ""]

    out = out_dir / "APPENDIX_A_prompt.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"checked {checked} task blocks against the run -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
