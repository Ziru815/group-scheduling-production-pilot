"""Adversarial structural tests for the Lab 4 report evidence gate."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from xml.etree import ElementTree as ET

from docs.lab4 import generate_report


def _write_junit(path: Path, names: list[str], *, skipped_index: int | None = None) -> None:
    suite = ET.Element("testsuite", tests=str(len(names)), failures="0", errors="0")
    for index, name in enumerate(names):
        case = ET.SubElement(suite, "testcase", name=name)
        if index == skipped_index:
            ET.SubElement(case, "skipped")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


class ReportEvidenceGateTests(TestCase):
    def test_junit_gate_rejects_a_skipped_case(self) -> None:
        with TemporaryDirectory() as directory:
            junit = Path(directory) / "skipped.xml"
            _write_junit(junit, ["case-a"], skipped_index=0)
            with patch.object(generate_report, "JUNIT", junit):
                with self.assertRaisesRegex(AssertionError, "skipped"):
                    generate_report.load_junit()

    def test_junit_gate_rejects_duplicate_case_names(self) -> None:
        with TemporaryDirectory() as directory:
            junit = Path(directory) / "duplicate.xml"
            _write_junit(junit, ["case-a", "case-a"])
            with patch.object(generate_report, "JUNIT", junit):
                with self.assertRaisesRegex(AssertionError, "duplicate"):
                    generate_report.load_junit()

    def test_attendance_path_evidence_includes_later_matching_items(self) -> None:
        busy_later_match = ["N8", "N6", "N7", "N8", "N9"]
        available_later_match = ["N12", "N10", "N11", "N12", "N13"]

        self.assertTrue(any(
            any(path[index : index + len(busy_later_match)] == busy_later_match
                for index in range(len(path) - len(busy_later_match) + 1))
            for path in generate_report.PA_PATHS
        ))
        self.assertTrue(any(
            any(path[index : index + len(available_later_match)] == available_later_match
                for index in range(len(path) - len(available_later_match) + 1))
            for path in generate_report.PA_PATHS
        ))
