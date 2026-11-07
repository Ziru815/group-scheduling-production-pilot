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

    def test_uses_committed_evidence_and_immutable_github_links(self) -> None:
        self.assertEqual(
            generate_report.JUNIT,
            generate_report.ROOT / "docs/lab4/evidence/lab4-junit.xml",
        )
        self.assertEqual(
            generate_report.EVIDENCE_SHA,
            "57ee15814f7c8c5da7541f8e566b87d7fe85f7fe",
        )
        self.assertIn(generate_report.EVIDENCE_SHA, generate_report.EVIDENCE_URL)
        self.assertIn(generate_report.PILOT_SHA, generate_report.PILOT_URL)

    def test_actual_outputs_are_observed_literals_not_placeholders(self) -> None:
        actuals = [row[4] for row in generate_report.black_cases + generate_report.iv_cases]
        combined = "\n".join(actuals)
        for placeholder in (
            "exact public message",
            "exact range detail",
            "exact overlap detail",
            "literal ascending endpoints",
        ):
            self.assertNotIn(placeholder, combined)

        self.assertIn(
            "ValueError: Minimum-Attendee Threshold must be positive",
            actuals,
        )
        self.assertIn(
            "HTTP 422: Availability must be inside the session date range",
            actuals,
        )
        self.assertIn(
            "HTTP 422: Availability intervals cannot overlap",
            actuals,
        )
        self.assertIn(
            "[(10:00–11:00), (11:00–12:00)] SGT",
            actuals,
        )

    def test_reported_basis_paths_are_complete_entry_to_exit_paths(self) -> None:
        interval_paths = [row[1] for row in generate_report.iv_cases]
        attendance_paths = [row[1] for row in generate_report.pa_cases]

        self.assertTrue(all(path.startswith("N1-") and path.endswith("-N10") for path in interval_paths))
        self.assertTrue(all(path.startswith("N1-") and path.endswith("-N15") for path in attendance_paths))
        self.assertTrue(all("loop valid" not in path for path in interval_paths))
        self.assertTrue(all("(T)" in path or "(F)" in path for path in interval_paths + attendance_paths))
