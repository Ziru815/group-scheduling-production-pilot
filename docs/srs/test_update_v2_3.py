"""Regression tests for the Pilot-aligned SRS v2.3 transformation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from docx import Document

from docs.srs.update_v2_3 import create_v2_3


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/SRS Group Scheduling Application v2.2.docx"


def _row(document: Document, table_index: int, key: str) -> list[str]:
    for row in document.tables[table_index].rows:
        values = [cell.text for cell in row.cells]
        if values and values[0] == key:
            return values
    raise AssertionError(f"missing row {key!r} in table {table_index}")


class SrsV23RegressionTests(TestCase):
    def setUp(self) -> None:
        self.temp_directory = TemporaryDirectory()
        output = Path(self.temp_directory.name) / "srs-v2.3.docx"
        create_v2_3(SOURCE, output)
        self.document = Document(output)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_separates_recommendation_run_status_from_combination_feasibility(self) -> None:
        feasibility = _row(self.document, 38, "FeasibilityStatus")
        self.assertEqual(feasibility[3], "FEASIBLE, EXCLUDED, or DATA_UNAVAILABLE.")
        self.assertNotIn("BEST_AVAILABLE_BELOW_THRESHOLD", " ".join(feasibility))

        glossary_combination = _row(self.document, 25, "Combination Status")
        self.assertNotIn("BEST_AVAILABLE_BELOW_THRESHOLD", " ".join(glossary_combination))
        run_status = _row(self.document, 25, "Recommendation Run Status")
        self.assertIn("BEST_AVAILABLE_BELOW_THRESHOLD", " ".join(run_status))
        self.assertIn("NO_TIMESLOT_MEETS_THRESHOLD", " ".join(run_status))
        glossary_feasibility = " ".join(_row(self.document, 25, "Feasibility Status"))
        self.assertIn("FEASIBLE, EXCLUDED, and DATA_UNAVAILABLE", glossary_feasibility)
        self.assertNotIn("pending", glossary_feasibility.lower())

        derived = _row(self.document, 43, "RecommendationRunStatus")
        self.assertIn("BEST_AVAILABLE_BELOW_THRESHOLD", " ".join(derived))

    def test_resolves_every_occurrence_of_the_four_adopted_constants(self) -> None:
        self.assertIn("10", " ".join(_row(self.document, 25, "Venue Shortlist")))
        self.assertIn(
            "60 minutes",
            " ".join(_row(self.document, 25, "Maximum Journey Time Threshold")),
        )

        expected = {
            "Minimum Attendee Threshold": ("default is 2", "default value = 2"),
            "Candidate Timeslot": ("15-minute intervals", "step = 15 minutes"),
            "Venue Shortlist": ("size is 10", "shortlist size = 10"),
            "Maximum Journey Time Threshold": ("60 minutes", "value = 60 minutes"),
        }
        for key, fragments in expected.items():
            row_text = " | ".join(_row(self.document, 45, key))
            for fragment in fragments:
                self.assertIn(fragment, row_text, (key, fragment, row_text))
            self.assertNotIn("still to be confirmed", row_text)
            self.assertNotIn("still needs clarification", row_text)
            self.assertNotIn("= TBD", row_text)

        fr_c4 = " | ".join(_row(self.document, 12, "FR-C4"))
        self.assertIn("N = 10", fr_c4)
        self.assertNotIn("TBD-2]", fr_c4)
        fr_d3 = " | ".join(_row(self.document, 13, "FR-D3"))
        self.assertIn("60 minutes", fr_d3)
        self.assertNotIn("TBD-1]", fr_d3)

        all_text = "\n".join(
            paragraph.text for paragraph in self.document.paragraphs
        ) + "\n" + "\n".join(
            cell.text
            for table in self.document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertNotIn("30-minute", all_text)
        self.assertNotIn("step = 30 minutes", all_text)

    def test_records_as_built_testing_approval(self) -> None:
        revision_text = " | ".join(cell.text for cell in self.document.tables[0].rows[-1].cells)
        self.assertIn("approved by Ziru Gao", revision_text)
        self.assertIn("as-built production Pilot", revision_text)

    def test_recovery_resumes_with_venue_filtering_and_shortlisting(self) -> None:
        text = "\n".join(paragraph.text for paragraph in self.document.paragraphs)
        self.assertIn("continues with steps 3 to 6", text)
        self.assertNotIn("continues with steps 4 to 6", text)
