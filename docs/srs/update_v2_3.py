#!/usr/bin/env python3
"""Create and verify the Pilot-aligned SRS v2.3 from the retained v2.2 DOCX."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
NS = {"w": W_NS}


def document_text(document: Document) -> str:
    """Return visible paragraph and table text for semantic assertions."""
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    return "\n".join(chunks)


def assert_v2_3(document: Document) -> None:
    """Assert that the document states the adopted Pilot behavior and constants."""
    text = document_text(document)
    required_fragments = (
        "Version 2.3",
        "BEST_AVAILABLE_BELOW_THRESHOLD",
        "NO_TIMESLOT_MEETS_THRESHOLD",
        "requested Minimum-Attendee Threshold",
        "actual attendance",
        "MaximumJourneyTimeMinutes",
        "DefaultMinimumAttendeeThreshold",
        "VenueShortlistN",
        "CandidateTimeslotStepMinutes",
    )
    for fragment in required_fragments:
        assert fragment in text, f"missing required v2.3 content: {fragment}"

    stale_fragments = (
        "continues with steps 4 to 6",
        "default value is still to be confirmed",
        "interval between possible start times is still to be confirmed",
        "its size still needs clarification (TBD-2)",
        "threshold is exceeded; its value is still to be confirmed (TBD-1)",
        "[N: see Appendix C, TBD-2]",
        "[Threshold value: see Appendix C, TBD-1]",
    )
    for fragment in stale_fragments:
        assert fragment not in text, f"stale v2.2 content remains: {fragment}"

    configuration = {row.cells[0].text: row.cells[2].text for row in document.tables[42].rows[1:]}
    assert configuration["MaximumJourneyTimeMinutes"] == "60"
    assert configuration["DefaultMinimumAttendeeThreshold"] == "2"
    assert configuration["VenueShortlistN"] == "10"
    assert configuration["CandidateTimeslotStepMinutes"] == "15"

    combination = {
        row.cells[0].text: [cell.text for cell in row.cells]
        for row in document.tables[38].rows[1:]
    }
    feasibility = combination["FeasibilityStatus"]
    assert feasibility[3] == "FEASIBLE, EXCLUDED, or DATA_UNAVAILABLE."
    assert "BEST_AVAILABLE_BELOW_THRESHOLD" not in " ".join(feasibility)

    derived = {row.cells[0].text for row in document.tables[43].rows[1:]}
    assert "RecommendationRunStatus" in derived


def visible_text(element: etree._Element) -> str:
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def replace_text(element: etree._Element, value: str) -> None:
    texts = element.xpath(".//w:t", namespaces=NS)
    if not texts:
        paragraph = element.find(".//w:p", namespaces=NS)
        if paragraph is None:
            paragraph = etree.SubElement(element, W + "p")
        run = etree.SubElement(paragraph, W + "r")
        texts = [etree.SubElement(run, W + "t")]
    texts[0].text = value
    if value.startswith(" ") or value.endswith(" "):
        texts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for text in texts[1:]:
        text.text = ""


def table_cells(row: etree._Element) -> list[etree._Element]:
    return row.xpath("./w:tc", namespaces=NS)


def row_values(row: etree._Element) -> list[str]:
    return [visible_text(cell) for cell in table_cells(row)]


def find_row(table: etree._Element, key: str) -> etree._Element:
    for row in table.xpath("./w:tr", namespaces=NS):
        values = row_values(row)
        if values and values[0] == key:
            return row
    raise AssertionError(f"row not found: {key}")


def set_row(row: etree._Element, values: list[str]) -> None:
    cells = table_cells(row)
    assert len(cells) == len(values), (len(cells), len(values))
    for cell, value in zip(cells, values, strict=True):
        replace_text(cell, value)


def keep_row_together(row: etree._Element) -> None:
    """Prevent Word/LibreOffice from splitting a table row across two pages."""
    properties = row.find("w:trPr", namespaces=NS)
    if properties is None:
        properties = etree.Element(W + "trPr")
        row.insert(0, properties)
    if properties.find("w:cantSplit", namespaces=NS) is None:
        etree.SubElement(properties, W + "cantSplit")


def insert_cloned_row_after(table: etree._Element, source_key: str, values: list[str]) -> None:
    source = find_row(table, source_key)
    cloned = deepcopy(source)
    set_row(cloned, values)
    source.addnext(cloned)


def replace_paragraph_start(root: etree._Element, start: str, value: str) -> None:
    for paragraph in root.xpath(".//w:body//w:p", namespaces=NS):
        if visible_text(paragraph).startswith(start):
            replace_text(paragraph, value)
            return
    raise AssertionError(f"paragraph not found: {start}")


def update_document_xml(source: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(source, parser)
    body = root.find(".//w:body", namespaces=NS)
    assert body is not None
    tables = body.xpath("./w:tbl", namespaces=NS)
    assert len(tables) == 47

    replace_paragraph_start(root, "Version 2.2", "Version 2.3")
    replace_paragraph_start(root, "24 October 2026", "7 November 2026")

    revision_table = tables[0]
    last_revision = revision_table.xpath("./w:tr", namespaces=NS)[-1]
    revision = deepcopy(last_revision)
    set_row(
        revision,
        [
            "SCEE Group 2 — as-built testing baseline approved by Ziru Gao",
            "7 Nov 2026",
            "Approved the as-built production Pilot as the Lab 4 testing baseline: documented near-match recovery and adopted the implemented journey-time, attendance, venue-shortlist and 15-minute timeslot-step constants.",
            "2.3",
        ],
    )
    last_revision.addnext(revision)

    replace_paragraph_start(
        root,
        "•Candidate Generation (Section 4.3)",
        "•Candidate Generation (Section 4.3) — enumerate every Candidate Timeslot in the Session’s date range, count Participant availability per Timeslot, apply the requested Minimum-Attendee Threshold when qualifying Timeslots exist, otherwise retain the best-attended Timeslots when at least the system default minimum can attend, filter the Venue catalogue to Venues supporting the activity type, and shortlist the Venues nearest the Participant centroid.",
    )
    replace_paragraph_start(
        root,
        "•Feasibility and Scoring (Section 4.4)",
        "•Feasibility and Scoring (Section 4.4) — exclude Combinations failing attendance, journey-time, Venue group-size or advance-booking constraints; when best-available recovery is active, disclose that the requested threshold was not met; retrieve routing-based travel durations; compute attendance and travel scores under the Organiser’s chosen Travel Objective and weighting, and produce a ranked Combined Score.",
    )
    replace_paragraph_start(
        root,
        "Alternative flow (at step 2): if no time slot meets the attendance requirement",
        "Alternative flow (at step 2): if no Candidate Timeslot meets the requested Minimum-Attendee Threshold, the System preserves that requested threshold and checks the highest actual attendance. If the best attendance is at least the system default minimum of 2, the System retains only the best-attended Timeslots, marks the recommendation result BEST_AVAILABLE_BELOW_THRESHOLD, and continues with steps 3 to 6 while warning that actual attendance is below the requested Minimum-Attendee Threshold. If the best attendance is below 2, the System returns NO_TIMESLOT_MEETS_THRESHOLD, performs no routing, and produces no candidate Combination. If at least one Timeslot meets the requested threshold, normal processing continues. Postcondition: a normal or clearly labelled recovered candidate set exists, or a no-result status explains why no set was produced.",
    )
    replace_paragraph_start(
        root,
        "Priority: High. This feature is the product’s differentiator",
        "Priority: High. This feature is the product’s differentiator, the joint optimisation of time against real travel time stated in Section 1.4. The production Pilot adopts a 60-minute maximum journey time, a default minimum attendance of 2, a venue shortlist of 10, and a 15-minute Candidate Timeslot step. The public-transport routing provider, optimal-group-size effect and tie-break rule remain unresolved (Appendix C, TBD-3, TBD-4 and TBD-9).",
    )
    replace_paragraph_start(
        root,
        "The interval between successive Candidate Timeslot start times is not stated",
        "The interval between successive Candidate Timeslot start times is 15 minutes (TBD-13 resolved).",
    )
    replace_paragraph_start(
        root,
        "Shortlist size N is TBD",
        "Shortlist size N is 10 (TBD-2 resolved). The shortlist is calculated each time the Organiser runs Generate Recommendations (UC-09); entries from earlier runs are marked INVALIDATED.",
    )

    fr_d = tables[13]
    fr_c = tables[12]
    fr_c4 = find_row(fr_c, "FR-C4")
    fr_c4_values = row_values(fr_c4)
    fr_c4_values[3] = "Filtered venue list (FR-C3); Participant coordinates (FR-B3); N = 10 (TBD-2 resolved)."
    set_row(fr_c4, fr_c4_values)

    set_row(
        find_row(fr_d, "FR-D1"),
        [
            "FR-D1",
            "When at least one Candidate Timeslot meets the Session’s requested Minimum-Attendee Threshold, the System must exclude every Timeslot-Venue Combination whose attendance count is below that threshold.",
            "System",
            "Attendance count (FR-C2); requested Minimum-Attendee Threshold (FR-A4).",
            "Below-threshold Combinations excluded from normal scoring.",
        ],
    )
    insert_cloned_row_after(
        fr_d,
        "FR-D1",
        [
            "FR-D1.1",
            "If no Candidate Timeslot meets the requested Minimum-Attendee Threshold, the System must preserve the requested threshold and select only Timeslots with the highest actual attendance when that attendance is at least the system default minimum of 2; it must label the result BEST_AVAILABLE_BELOW_THRESHOLD. If the highest actual attendance is below 2, it must return NO_TIMESLOT_MEETS_THRESHOLD and must not perform routing or produce candidate Combinations.",
            "System",
            "Attendance count per Candidate Timeslot (FR-C2); requested Minimum-Attendee Threshold (FR-A4); DefaultMinimumAttendeeThreshold.",
            "Recovered best-attended Timeslots with an explicit status, or a no-result status with no routing candidates.",
        ],
    )
    fr_d3 = find_row(fr_d, "FR-D3")
    fr_d3_values = row_values(fr_d3)
    fr_d3_values[3] = "Travel Estimates (FR-D2); maximum individual journey time = 60 minutes (TBD-1 resolved)."
    set_row(fr_d3, fr_d3_values)

    fr_e = tables[14]
    set_row(
        find_row(fr_e, "FR-E1"),
        [
            "FR-E1",
            "The System must display the top-ranked Combinations, including Venue name, address, map pin, date/time, Combined Score, actual attendance count, and total and maximum individual travel time.",
            "System, viewed by Organiser / Participant",
            "Ranked Combination list (FR-D10).",
            "Top-ranked normal or recovered Combinations rendered.",
        ],
    )
    insert_cloned_row_after(
        fr_e,
        "FR-E1",
        [
            "FR-E1.1",
            "For BEST_AVAILABLE_BELOW_THRESHOLD results, the System must display both the requested Minimum-Attendee Threshold and the actual attendance and must clearly warn that the requested threshold was not met. For NO_TIMESLOT_MEETS_THRESHOLD, the System must display that no Candidate Timeslot meets the minimum of 2.",
            "System, viewed by Organiser / Participant",
            "Recommendation status (FR-D1.1); requested threshold; actual attendance.",
            "Recovery status and requested-versus-actual attendance are visible and unambiguous.",
        ],
    )

    glossary = tables[25]
    set_row(
        find_row(glossary, "Minimum Attendee Threshold"),
        [
            "Minimum Attendee Threshold",
            "The smallest number of available Participants requested by the Organiser for a normal recommendation. The production Pilot default is 2. The requested value is preserved when best-available recovery is used.",
        ],
    )
    set_row(
        find_row(glossary, "Candidate Timeslot"),
        [
            "Candidate Timeslot",
            "A possible Session time generated inside the date range using the Session Duration. Successive possible start times are generated at 15-minute intervals.",
        ],
    )
    set_row(
        find_row(glossary, "Venue Shortlist"),
        [
            "Venue Shortlist",
            "The nearest eligible Venues retained for one Session. It is calculated each time the Organiser runs Generate Recommendations; the production Pilot retains 10 Venues.",
        ],
    )
    set_row(
        find_row(glossary, "Maximum Journey Time Threshold"),
        [
            "Maximum Journey Time Threshold",
            "The longest journey allowed for an attending Participant. The production Pilot limit is 60 minutes; a Combination is excluded when that limit is exceeded.",
        ],
    )
    set_row(
        find_row(glossary, "Combination Status"),
        [
            "Combination Status",
            "Shows whether a Timeslot-Venue Combination is still a candidate, has been excluded, or has become the confirmed choice.",
        ],
    )
    set_row(
        find_row(glossary, "Feasibility Status"),
        [
            "Feasibility Status",
            "Shows whether a Combination can be selected after feasibility checks. The permitted values are FEASIBLE, EXCLUDED, and DATA_UNAVAILABLE; Recommendation Run Status is separate.",
        ],
    )
    insert_cloned_row_after(
        glossary,
        "Combination Status",
        [
            "Recommendation Run Status",
            "Labels the recommendation run as normal, BEST_AVAILABLE_BELOW_THRESHOLD, or NO_TIMESLOT_MEETS_THRESHOLD. It is separate from each Combination's Feasibility Status.",
        ],
    )

    session_table = tables[28]
    set_row(
        find_row(session_table, "MinimumAttendeeThreshold"),
        [
            "MinimumAttendeeThreshold",
            "Integer",
            "Organiser-requested minimum attendance for normal feasibility; preserved during recovery.",
            "Positive; production Pilot default is 2.",
            "FR-A4, FR-D1, FR-D1.1",
        ],
    )

    combination_table = tables[38]
    set_row(
        find_row(combination_table, "AttendeeCount"),
        [
            "AttendeeCount",
            "Integer",
            "Actual number of available Participants for the Candidate Timeslot.",
            "Derived from TimeslotAttendance and displayed for normal and recovered results.",
            "FR-D1, FR-D1.1, FR-E1.1",
        ],
    )
    set_row(
        find_row(combination_table, "FeasibilityStatus"),
        [
            "FeasibilityStatus",
            "Enum",
            "Whether the Timeslot-Venue pair can be selected after feasibility checks.",
            "FEASIBLE, EXCLUDED, or DATA_UNAVAILABLE.",
            "FR-D1 to D5, NFR-3",
        ],
    )

    configuration = tables[42]
    for key, value, related in (
        ("MaximumJourneyTimeMinutes", "60", "FR-D3, TBD-1 resolved"),
        ("DefaultMinimumAttendeeThreshold", "2", "FR-A4, FR-D1.1, TBD-2 resolved"),
        ("VenueShortlistN", "10", "FR-C4, TBD-2 resolved"),
        ("CandidateTimeslotStepMinutes", "15", "FR-C1, TBD-13 resolved"),
    ):
        row = find_row(configuration, key)
        values = row_values(row)
        values[2] = value
        values[3] = related
        set_row(row, values)
        keep_row_together(row)

    derived = tables[43]
    set_row(
        find_row(derived, "FeasibilityStatus"),
        [
            "RecommendationRunStatus",
            "NORMAL when requested-threshold candidates exist; BEST_AVAILABLE_BELOW_THRESHOLD for the best-attended Timeslots when actual attendance is at least 2; or NO_TIMESLOT_MEETS_THRESHOLD with no candidates when it is below 2. Each produced Combination still receives its separate FeasibilityStatus.",
            "FR-D1, FR-D1.1, FR-E1.1",
        ],
    )

    conceptual = tables[45]
    conceptual_rows = {
        "Minimum Attendee Threshold": [
            "Minimum Attendee Threshold",
            "The smallest number of available Participants requested by the Organiser for a normal recommendation. The production Pilot default is 2, and the requested value is preserved during recovery.",
            "Minimum Participant count; default value = 2.",
            "Each Session has one Minimum Attendee Threshold. Normal recommendations meet the requested value; recovery is labelled separately when only the system minimum can attend.",
        ],
        "Candidate Timeslot": [
            "Candidate Timeslot",
            "A possible Session time generated inside the date range using the Session Duration. Successive possible starts use 15-minute intervals.",
            "Start date and time; end date and time; attendance count; step = 15 minutes.",
            "A Session can generate multiple Candidate Timeslots. Each timeslot can have multiple Timeslot Attendance records and can be paired with multiple Venues through Combinations.",
        ],
        "Venue Shortlist": [
            "Venue Shortlist",
            "The nearest eligible Venues retained for one Session. It is calculated each time the Organiser runs Generate Recommendations; its production Pilot size is 10.",
            "Eligible Venues; shortlist size = 10; calculation state.",
            "A Session may have one Venue Shortlist containing up to 10 Venues. It is recalculated each time the Organiser runs Generate Recommendations.",
        ],
        "Maximum Journey Time Threshold": [
            "Maximum Journey Time Threshold",
            "The longest journey allowed for an attending Participant. The production Pilot value is 60 minutes, and a Combination is excluded when that value is exceeded.",
            "Maximum duration; time unit; value = 60 minutes.",
            "The System applies the 60-minute Maximum Journey Time Threshold to Travel Estimates for each Combination.",
        ],
        "Feasibility Status": [
            "Feasibility Status",
            "Shows whether a Combination is feasible, excluded, or missing required external data. Recommendation-run recovery labels are represented separately.",
            "FEASIBLE; EXCLUDED; DATA_UNAVAILABLE.",
            "Each Combination has one Feasibility Status. Data unavailable is different from normal exclusion and from Recommendation Run Status.",
        ],
    }
    for key, values in conceptual_rows.items():
        set_row(find_row(conceptual, key), values)

    tbd = tables[44]
    set_row(
        find_row(tbd, "TBD-1"),
        [
            "TBD-1",
            "What is the maximum individual-journey-time threshold? — RESOLVED: the production Pilot uses 60 minutes.",
            "FR-D3",
            "Resolved",
        ],
    )
    set_row(
        find_row(tbd, "TBD-2"),
        [
            "TBD-2",
            "What default Minimum-Attendee Threshold and venue shortlist size N should the System use? — RESOLVED: the production Pilot uses a default threshold of 2 and N = 10.",
            "FR-A4, FR-C4, FR-D1.1",
            "Resolved",
        ],
    )
    set_row(
        find_row(tbd, "TBD-13"),
        [
            "TBD-13",
            "What interval separates successive Candidate Timeslot start times? — RESOLVED: the production Pilot uses 15 minutes.",
            "FR-C1",
            "Resolved",
        ],
    )

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def update_settings_xml(source: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(source, parser)
    update_fields = root.find("w:updateFields", namespaces=NS)
    if update_fields is None:
        update_fields = etree.SubElement(root, W + "updateFields")
    update_fields.set(W + "val", "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def create_v2_3(source_path: Path, output_path: Path) -> None:
    assert source_path.resolve() != output_path.resolve(), "output must differ from retained source"
    with ZipFile(source_path, "r") as source, ZipFile(output_path, "w") as output:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "word/document.xml":
                payload = update_document_xml(payload)
            elif info.filename == "word/settings.xml":
                payload = update_settings_xml(payload)
            output.writestr(info, payload, compress_type=info.compress_type or ZIP_DEFLATED)


def main(argv: list[str]) -> int:
    if len(argv) not in {2, 3}:
        print(f"usage: {Path(argv[0]).name} SOURCE_DOCX [OUTPUT_DOCX]", file=sys.stderr)
        return 2
    if len(argv) == 3:
        source_path = Path(argv[1])
        output_path = Path(argv[2])
        create_v2_3(source_path, output_path)
        target = output_path
    else:
        target = Path(argv[1])
    document = Document(target)
    assert_v2_3(document)
    print(f"verified Pilot-aligned SRS v2.3: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
