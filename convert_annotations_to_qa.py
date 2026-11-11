#!/usr/bin/env python3
"""Convert Glaucoma Med span annotations into fixed-question QA records."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


# Fixed label-to-question mapping from the experiment plan. A None question
# means that the label is intentionally excluded.
QUESTION_BY_LABEL: dict[str, str | None] = {
    "DRUG": "Which medication is mentioned?",
    "ROUTE": "Which route or eye designation is mentioned?",
    "FREQUENCY": "How often is the medication used?",
    "DOSAGE": "What amount of the medication is used at one time?",
    "STRENGTH": "What medication strength or concentration is mentioned?",
    "DURATION": "How long is the medication used?",
    "DRUG USE": (
        "Which word or phrase indicates medication use or continuation?"
    ),
    "DRUG STOP": (
        "Which word or phrase indicates that medication was stopped or not used?"
    ),
    "ADHERENCE": (
        "What medication adherence or tolerability statement is mentioned?"
    ),
    "***": None,
}

DEFAULT_INPUT = Path("Annotations/Combined_annotations.jsonl")
DEFAULT_OUTPUT = Path("QA/glaucoma_med_qa.jsonl")
DEFAULT_STATS = Path("QA/glaucoma_med_qa_stats.json")


def repair_released_json(line: str) -> str:
    """Repair only the two known JSON defects in the released annotation file.

    Some de-identified IDs are bare asterisks instead of JSON strings, and a
    few text values contain a literal backslash before asterisks. Both forms
    are invalid JSON. This repair preserves their displayed values.
    """

    repaired = re.sub(
        r'^(\s*\{\s*"id"\s*:\s*)(\*+)(\s*,)',
        lambda match: (
            f"{match.group(1)}{json.dumps(match.group(2))}{match.group(3)}"
        ),
        line,
    )
    # A JSON backslash must introduce a valid escape. Doubling an otherwise
    # invalid backslash preserves it as a literal character after parsing.
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", repaired)


def parse_annotation_line(
    line: str, line_number: int
) -> tuple[dict[str, Any], bool]:
    """Parse one released JSONL record and report whether repair was needed."""

    try:
        return json.loads(line), False
    except json.JSONDecodeError as original_error:
        try:
            return json.loads(repair_released_json(line)), True
        except json.JSONDecodeError as repair_error:
            raise ValueError(
                f"Cannot parse annotation line {line_number}: {repair_error}"
            ) from original_error


def _label_slug(label: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", label.lower()))


def _validate_record(record: dict[str, Any], line_number: int) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"Line {line_number}: record must be an object")
    if not isinstance(record.get("text"), str):
        raise ValueError(f"Line {line_number}: text must be a string")
    if not isinstance(record.get("labels"), list):
        raise ValueError(f"Line {line_number}: labels must be an array")


def convert_record(
    record: dict[str, Any],
    line_number: int,
    *,
    invalid_label_policy: str = "error",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert all supported spans in one annotation record."""

    if invalid_label_policy not in {"error", "skip"}:
        raise ValueError("invalid_label_policy must be 'error' or 'skip'")

    _validate_record(record, line_number)
    text = record["text"]
    converted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []

    for label_index, annotation in enumerate(record["labels"]):
        if not isinstance(annotation, list) or len(annotation) != 3:
            raise ValueError(
                f"Line {line_number}, label {label_index}: "
                "expected [start, end, label]"
            )

        start, end, label = annotation
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
        ):
            raise ValueError(
                f"Line {line_number}, label {label_index}: "
                "offsets must be integers"
            )

        if start < 0 or end <= start or end > len(text):
            message = (
                f"Line {line_number}, label {label_index}: invalid range "
                f"[{start}, {end}) for text length {len(text)}"
            )
            if invalid_label_policy == "skip":
                invalid.append(
                    {
                        "line": line_number,
                        "label_index": label_index,
                        "label": label,
                        "start": start,
                        "end": end,
                        "text_length": len(text),
                        "reason": message,
                    }
                )
                continue
            raise ValueError(message)

        if label not in QUESTION_BY_LABEL:
            raise ValueError(
                f"Line {line_number}, label {label_index}: "
                f"unknown label {label!r}"
            )

        question = QUESTION_BY_LABEL[label]
        if question is None:
            excluded.append(
                {
                    "label": label,
                    "line_number": line_number,
                    "label_index": label_index,
                }
            )
            continue

        converted.append(
            {
                "qa_id": (
                    f"glaucoma-med-{line_number:05d}-{label_index + 1:02d}-"
                    f"{_label_slug(label)}"
                ),
                "context": text,
                "question": question,
                "reference_answer": text[start:end],
                "label": label,
                "answer_start": start,
                "answer_end": end,
                "source_record_id": record.get("id"),
                "source_line": line_number,
                "source_label_index": label_index,
            }
        )

    return converted, excluded, invalid


def convert_file(
    input_path: Path, *, strict: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert a released annotation JSONL file and return QA items and stats."""

    lines = input_path.read_text(encoding="utf-8").splitlines()
    qa_items: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    repaired_input_lines = 0
    excluded_unknown_labels = 0
    invalid_annotations: list[dict[str, Any]] = []
    input_records = 0

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        input_records += 1

        record, repaired = parse_annotation_line(line, line_number)
        repaired_input_lines += int(repaired)
        converted, excluded, invalid = convert_record(
            record,
            line_number,
            invalid_label_policy="error" if strict else "skip",
        )
        excluded_unknown_labels += len(excluded)
        invalid_annotations.extend(invalid)
        qa_items.extend(converted)
        label_counts.update(item["label"] for item in converted)

    stats: dict[str, Any] = {
        "input_records": input_records,
        "repaired_input_lines": repaired_input_lines,
        "output_qa_items": len(qa_items),
        "excluded_unknown_labels": excluded_unknown_labels,
        "skipped_invalid_annotations": len(invalid_annotations),
        "invalid_annotations": invalid_annotations,
        "output_items_by_label": dict(sorted(label_counts.items())),
    }
    return qa_items, stats


def write_output(
    output_path: Path,
    stats_path: Path,
    qa_items: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for item in qa_items:
            output_file.write(
                json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            )

    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert Glaucoma Med labeled spans to fixed-question QA JSONL."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Stop on the first invalid annotation range.",
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    qa_items, stats = convert_file(args.input.resolve(), strict=args.strict)
    output_path = args.output.resolve()
    stats_path = args.stats.resolve()
    write_output(output_path, stats_path, qa_items, stats)

    print(f"Wrote {stats['output_qa_items']} QA items to {output_path}")
    print(f"Wrote conversion report to {stats_path}")
    print(f"Repaired {stats['repaired_input_lines']} released JSONL lines")
    print(f"Excluded {stats['excluded_unknown_labels']} labels named ***")
    print(f"Skipped {stats['skipped_invalid_annotations']} invalid annotations")


if __name__ == "__main__":
    main()

