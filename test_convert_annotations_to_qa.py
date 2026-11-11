from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from convert_annotations_to_qa import (  # noqa: E402
    QUESTION_BY_LABEL,
    convert_record,
    parse_annotation_line,
)


class ConvertAnnotationsToQATest(unittest.TestCase):
    def test_converts_every_planned_label_to_fixed_question(self) -> None:
        examples = {
            "DRUG": "Latanoprost",
            "ROUTE": "OU",
            "FREQUENCY": "BID",
            "DOSAGE": "1 drop",
            "STRENGTH": "0.5%",
            "DURATION": "2 weeks",
            "DRUG USE": "Continue",
            "DRUG STOP": "stopped",
            "ADHERENCE": "Good drop compliance",
        }

        for label, text in examples.items():
            with self.subTest(label=label):
                record = {"id": 1, "text": text, "labels": [[0, len(text), label]]}
                converted, excluded, invalid = convert_record(record, 1)
                self.assertEqual(len(converted), 1)
                self.assertEqual(excluded, [])
                self.assertEqual(invalid, [])
                self.assertEqual(converted[0]["question"], QUESTION_BY_LABEL[label])
                self.assertEqual(converted[0]["reference_answer"], text)
                self.assertNotIn("dataset", converted[0])
                self.assertEqual(converted[0]["answer_start"], 0)
                self.assertEqual(converted[0]["answer_end"], len(text))

    def test_excludes_unknown_asterisk_label(self) -> None:
        converted, excluded, invalid = convert_record(
            {"id": 1, "text": "unknown", "labels": [[0, 7, "***"]]}, 1
        )
        self.assertEqual(converted, [])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(invalid, [])

    def test_repairs_masked_ids_and_invalid_backslash_escapes(self) -> None:
        line = r'{"id": *****, "text": "1.\***** OU", "labels": [[9, 11, "ROUTE"]]}'
        record, repaired = parse_annotation_line(line, 157)
        self.assertTrue(repaired)
        self.assertEqual(record["id"], "*****")
        self.assertEqual(record["text"], r"1.\***** OU")

        converted, _, _ = convert_record(record, 157)
        self.assertEqual(converted[0]["reference_answer"], "OU")

    def test_rejects_invalid_annotation_offsets(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid range"):
            convert_record(
                {"id": 1, "text": "OU", "labels": [[0, 3, "ROUTE"]]}, 1
            )

    def test_can_skip_invalid_offsets_for_full_conversion(self) -> None:
        converted, _, invalid = convert_record(
            {"id": 1, "text": "OU", "labels": [[0, 3, "ROUTE"]]},
            1,
            invalid_label_policy="skip",
        )
        self.assertEqual(converted, [])
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]["text_length"], 2)


if __name__ == "__main__":
    unittest.main()

