# Glaucoma Med QA Dataset

This repository contains a question-answering conversion of the medication
span annotations from the public
[Glaucoma Med Dataset](https://github.com/jche253/Glaucoma_Med_Dataset).
The original dataset was published with:

> Lin WC, Chee YE, Singh P, et al. Development of an Open-Source Annotated
> Glaucoma Medication Dataset From Clinical Notes in the Electronic Health
> Record. *Translational Vision Science & Technology*. 2022;11(11):20.
> [doi:10.1167/tvst.11.11.20](https://doi.org/10.1167/tvst.11.11.20)

The source dataset is distributed under the BSD 3-Clause license. This
repository retains that license and should be used with attribution to the
original authors and repository.

## What this repository contains

| File | Purpose |
| --- | --- |
| `glaucoma_med_qa.jsonl` | 6,466 converted, fragment-grounded QA records |
| `convert_annotations_to_qa.py` | Dependency-free Python conversion script |
| `test_convert_annotations_to_qa.py` | Automated checks for conversion behavior |
| `glaucoma_med_qa_stats.json` | Conversion counts and invalid-span audit |
| `LICENSE` | BSD 3-Clause license from the source dataset |

The converted file is **fragment-grounded**, not full-note-grounded. Each
`context` is the annotated sentence or fragment supplied by the original
annotation file. The public release does not provide a verified mapping from
annotation IDs to the hashed filenames in `Deidentified_Notes`, so this
repository does not claim such a mapping.

## How the JSONL was produced

The source file is:

```text
Annotations/Combined_annotations.jsonl
```

For each supported labeled span, the converter creates one question. The text
inside the span becomes the reference answer.

| Source label | Fixed question |
| --- | --- |
| `DRUG` | Which medication is mentioned? |
| `ROUTE` | Which route or eye designation is mentioned? |
| `FREQUENCY` | How often is the medication used? |
| `DOSAGE` | What amount of the medication is used at one time? |
| `STRENGTH` | What medication strength or concentration is mentioned? |
| `DURATION` | How long is the medication used? |
| `DRUG USE` | Which word or phrase indicates medication use or continuation? |
| `DRUG STOP` | Which word or phrase indicates that medication was stopped or not used? |
| `ADHERENCE` | What medication adherence or tolerability statement is mentioned? |
| `***` | Excluded because the source label has no defined meaning |

The converter also:

- repairs the released JSON formatting for masked, unquoted IDs and invalid
  backslash escapes without changing annotation text;
- preserves source line numbers, record IDs, span indexes, and character
  offsets for auditing;
- skips invalid character ranges instead of inventing reference answers; and
- writes a separate statistics report describing repairs, exclusions, and
  invalid spans.

The completed conversion contains:

```text
Input annotation records:       5,520
Generated QA records:           6,466
Repaired released JSONL lines:  1,276
Excluded *** spans:                67
Skipped invalid spans:              2
```

## Reproduce the converted dataset

Python 3.10 or newer is required. The converter uses only the Python standard
library.

Clone the original dataset next to this repository:

```bash
git clone https://github.com/jche253/Glaucoma_Med_Dataset.git source_dataset
```

Then run the converter from this repository:

```bash
python3 convert_annotations_to_qa.py \
  --input source_dataset/Annotations/Combined_annotations.jsonl \
  --output glaucoma_med_qa.jsonl \
  --stats glaucoma_med_qa_stats.json
```

Expected summary:

```text
Wrote 6466 QA items
Repaired 1276 released JSONL lines
Excluded 67 labels named ***
Skipped 2 invalid annotations
```

Run the automated tests with:

```bash
python3 -m unittest -v test_convert_annotations_to_qa.py
```

Use `--strict` if an invalid annotation range should stop conversion instead
of being skipped:

```bash
python3 convert_annotations_to_qa.py \
  --input source_dataset/Annotations/Combined_annotations.jsonl \
  --output glaucoma_med_qa.jsonl \
  --stats glaucoma_med_qa_stats.json \
  --strict
```

## How to inspect the data

JSONL stores one JSON object per line. Display the first three records with:

```bash
head -n 3 glaucoma_med_qa.jsonl
```

Pretty-print the first record with Python:

```bash
python3 - <<'PY'
import json

with open("glaucoma_med_qa.jsonl", encoding="utf-8") as file:
    print(json.dumps(json.loads(next(file)), indent=2))
PY
```

Iterate through records programmatically:

```python
import json

with open("glaucoma_med_qa.jsonl", encoding="utf-8") as file:
    for line in file:
        item = json.loads(line)
        print(item["question"], "->", item["reference_answer"])
```

Each record contains:

| Field | Meaning |
| --- | --- |
| `qa_id` | Stable ID derived from the source line, label position, and label |
| `context` | Annotated source sentence or fragment |
| `question` | Fixed question generated from the label |
| `reference_answer` | Exact text inside the annotated span |
| `label` | Original source label |
| `answer_start`, `answer_end` | Zero-based, end-exclusive span offsets |
| `source_record_id` | ID from the released annotation record |
| `source_line` | One-based line in `Combined_annotations.jsonl` |
| `source_label_index` | Zero-based position in the source record's label list |

For example, a record with `source_line: 4` can be traced back with:

```bash
sed -n '4p' source_dataset/Annotations/Combined_annotations.jsonl
```

`source_record_id` identifies the annotation record, not a full-note filename.
Do not infer a full-note association from that value.

