"""Build the deterministic Pilot-aligned SC2006 Lab 4 testing report."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from docx import Document
from pypdf import PdfReader
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/lab4/Lab4_Software_Testing_Report.pdf"
JUNIT = ROOT / ".superpowers/sdd/2026-11-07-pilot-aligned-srs-lab4-report/lab4-junit.xml"
SRS = ROOT / "docs/SRS Group Scheduling Application v2.3.docx"
PILOT_SHA = "26cb622a8724018f7582225c640d5ac93e9ac8a5"

GREEN = colors.HexColor("#174A3A")
MID_GREEN = colors.HexColor("#2F6650")
PALE_GREEN = colors.HexColor("#DCEBDF")
GOLD = colors.HexColor("#D19A3A")
PALE_GOLD = colors.HexColor("#FFF1CC")
INK = colors.HexColor("#26322C")
MUTED = colors.HexColor("#5B655E")
CREAM = colors.HexColor("#F7F4EC")
PALE_RED = colors.HexColor("#F7D8D5")
WHITE = colors.white
GRID = colors.HexColor("#C7CEC9")


class InvariantCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=26, leading=31, textColor=GREEN, alignment=TA_LEFT, spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="Subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=12,
    leading=17, textColor=MUTED, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=17, leading=21, textColor=GREEN, spaceBefore=3, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=11.5, leading=14.5, textColor=MID_GREEN, spaceBefore=7, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.1,
    leading=12.6, textColor=INK, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5,
    leading=9.7, textColor=INK,
))
styles.add(ParagraphStyle(
    name="Tiny", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.2,
    leading=7.7, textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=6.7, leading=8.1, textColor=WHITE, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="CodeBlock", fontName="Courier", fontSize=5.75, leading=6.75,
    textColor=INK, leftIndent=4, rightIndent=4, borderColor=GRID, borderWidth=0.5,
    borderPadding=4, backColor=colors.HexColor("#F3F5F3"), spaceBefore=3, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=8.7, leading=12, textColor=GREEN, leftIndent=8, rightIndent=8,
    borderColor=GOLD, borderWidth=1, borderPadding=7, backColor=PALE_GOLD,
    spaceBefore=5, spaceAfter=8,
))


def p(text: str, style: str = "Body") -> Paragraph:
    return Paragraph(text, styles[style])


def section(title: str, number: str) -> list:
    return [
        p(f"{number}  {title}", "Section"),
        HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=7),
    ]


def report_table(data, widths, *, font_size=6.4, leading=8.0, repeat=True, padding=3.3):
    converted = []
    for row_index, row in enumerate(data):
        converted.append([
            Paragraph(
                escape(str(value)).replace("\n", "<br/>"),
                styles["TableHeader"] if row_index == 0 else ParagraphStyle(
                    f"table-{row_index}-{column_index}-{font_size}",
                    parent=styles["Tiny"], fontSize=font_size, leading=leading,
                    alignment=TA_LEFT,
                ),
            )
            for column_index, value in enumerate(row)
        ])
    cls = LongTable if len(data) > 8 else Table
    result = cls(
        converted, colWidths=widths, repeatRows=1 if repeat else 0,
        hAlign="LEFT", splitByRow=1,
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    for row_index in range(1, len(data)):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), WHITE if row_index % 2 else CREAM))
    result.setStyle(TableStyle(commands))
    return result


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
            topMargin=18 * mm, bottomMargin=16 * mm,
            title="Lab 4 Software Testing Report", author="Group 1 - Software Testing",
            subject="SC2006 Lab 4 black-box and white-box testing",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(PageTemplate(id="content", frames=[frame], onPage=self._decorate))

    def _decorate(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(GRID)
            canvas.line(self.leftMargin, A4[1] - 12 * mm, A4[0] - self.rightMargin, A4[1] - 12 * mm)
            canvas.setFont("Helvetica", 7.3)
            canvas.setFillColor(MUTED)
            canvas.drawString(self.leftMargin, A4[1] - 9 * mm, "SC2006 Lab 4 | Software Testing")
            canvas.drawRightString(
                A4[0] - self.rightMargin, 9 * mm,
                f"Group 1 - Software Testing     |     Page {doc.page}",
            )
        canvas.restoreState()


def add_arrow(drawing: Drawing, x1, y1, x2, y2, label: str):
    drawing.add(Line(x1, y1, x2, y2, strokeColor=MUTED, strokeWidth=0.85))
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 4.3
    drawing.add(Polygon([
        x2, y2,
        x2 - ux * size + px * size * 0.5, y2 - uy * size + py * size * 0.5,
        x2 - ux * size - px * size * 0.5, y2 - uy * size - py * size * 0.5,
    ], fillColor=MUTED, strokeColor=MUTED))
    drawing.add(String(
        (x1 + x2) / 2 + 2, (y1 + y2) / 2 + 2, label,
        fontName="Helvetica", fontSize=5.6, fillColor=MUTED,
    ))


def add_node(drawing: Drawing, x, y, width, height, label, *, decision=False, terminal=False):
    fill = PALE_GOLD if decision else (PALE_GREEN if terminal else CREAM)
    if decision:
        drawing.add(Polygon([
            x, y + height / 2, x + width / 2, y,
            x, y - height / 2, x - width / 2, y,
        ], fillColor=fill, strokeColor=MID_GREEN, strokeWidth=0.9))
    else:
        drawing.add(Rect(
            x - width / 2, y - height / 2, width, height,
            rx=height / 3 if terminal else 4, ry=height / 3 if terminal else 4,
            fillColor=fill, strokeColor=MID_GREEN, strokeWidth=0.9,
        ))
    lines = label.split("\n")
    for index, line in enumerate(lines):
        drawing.add(String(
            x, y + (len(lines) - 1) * 3.6 - index * 7.2 - 2.4,
            line, fontName="Helvetica-Bold" if index == 0 else "Helvetica",
            fontSize=5.6, textAnchor="middle", fillColor=INK,
        ))


IV_NODES = {f"N{i}" for i in range(1, 11)}
IV_EDGES = [
    ("N1", "N2"), ("N2", "N3"), ("N3", "N4"), ("N3", "N7"),
    ("N4", "N6"), ("N4", "N5"), ("N5", "N6"), ("N5", "N3"),
    ("N6", "N10"), ("N7", "N8"), ("N7", "N10"), ("N8", "N9"),
    ("N8", "N7"), ("N9", "N10"),
]
IV_PATHS = [
    ["N1", "N2", "N3", "N7", "N10"],
    ["N1", "N2", "N3", "N4", "N6", "N10"],
    ["N1", "N2", "N3", "N4", "N5", "N6", "N10"],
    ["N1", "N2", "N3", "N4", "N5", "N3", "N7", "N10"],
    ["N1", "N2", "N3", "N4", "N5", "N3", "N4", "N5", "N3", "N7", "N8", "N9", "N10"],
    ["N1", "N2", "N3", "N4", "N5", "N3", "N4", "N5", "N3", "N7", "N8", "N7", "N10"],
]

PA_NODES = {f"N{i}" for i in range(1, 16)}
PA_EDGES = [
    ("N1", "N2"), ("N2", "N3"), ("N2", "N4"), ("N3", "N15"),
    ("N4", "N5"), ("N4", "N6"), ("N5", "N15"), ("N6", "N7"),
    ("N6", "N10"), ("N7", "N8"), ("N7", "N6"), ("N8", "N9"),
    ("N8", "N6"), ("N9", "N15"), ("N10", "N11"), ("N10", "N14"),
    ("N11", "N12"), ("N11", "N10"), ("N12", "N13"), ("N12", "N10"),
    ("N13", "N15"), ("N14", "N15"),
]
PA_PATHS = [
    ["N1", "N2", "N4", "N6", "N10", "N14", "N15"],
    ["N1", "N2", "N3", "N15"],
    ["N1", "N2", "N4", "N5", "N15"],
    ["N1", "N2", "N4", "N6", "N7", "N6", "N10", "N14", "N15"],
    ["N1", "N2", "N4", "N6", "N7", "N8", "N6", "N10", "N14", "N15"],
    ["N1", "N2", "N4", "N6", "N7", "N8", "N6", "N7", "N8", "N9", "N15"],
    ["N1", "N2", "N4", "N6", "N10", "N11", "N10", "N14", "N15"],
    ["N1", "N2", "N4", "N6", "N10", "N11", "N12", "N10", "N14", "N15"],
    ["N1", "N2", "N4", "N6", "N10", "N11", "N12", "N10", "N11", "N12", "N13", "N15"],
]


def _rational_rank(matrix: list[list[int]]) -> int:
    rows = [[Fraction(value) for value in row] for row in matrix]
    rank = 0
    for column in range(len(rows[0]) if rows else 0):
        pivot = next((index for index in range(rank, len(rows)) if rows[index][column]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        divisor = rows[rank][column]
        rows[rank] = [value / divisor for value in rows[rank]]
        for index in range(len(rows)):
            if index != rank and rows[index][column]:
                factor = rows[index][column]
                rows[index] = [a - factor * b for a, b in zip(rows[index], rows[rank], strict=True)]
        rank += 1
    return rank


def verify_basis_graph(nodes: set[str], edges: list[tuple[str, str]], paths: list[list[str]]) -> int:
    """Verify graph membership, edge coverage and independent path-vector rank."""
    assert len(edges) == len(set(edges)), "graph contains duplicate directed edges"
    assert {node for edge in edges for node in edge} <= nodes
    edge_index = {edge: index for index, edge in enumerate(edges)}
    vectors: list[list[int]] = []
    covered: set[tuple[str, str]] = set()
    for path in paths:
        assert path and set(path) <= nodes
        vector = [0] * len(edges)
        for edge in zip(path, path[1:], strict=False):
            assert edge in edge_index, f"path uses undeclared edge: {edge}"
            vector[edge_index[edge]] += 1
            covered.add(edge)
        vectors.append(vector)
    assert covered == set(edges), f"uncovered edges: {set(edges) - covered}"
    return _rational_rank(vectors)


def intervals_chart() -> Drawing:
    drawing = Drawing(500, 315)
    positions = {
        "N1": (70, 292, "N1 Entry"), "N2": (70, 252, "N2\nsort intervals"),
        "N3": (70, 205, "N3\nnext interval?"), "N4": (70, 155, "N4\nstart before range?"),
        "N5": (70, 105, "N5\nend after range?"), "N6": (255, 130, "N6\nraise range 422"),
        "N7": (70, 48, "N7\nnext pair?"), "N8": (245, 48, "N8\noverlap?"),
        "N9": (405, 48, "N9\nraise overlap 422"), "N10": (255, 10, "N10 Common exit"),
    }
    decisions = {"N3", "N4", "N5", "N7", "N8"}
    terminals = {"N1", "N10"}
    for node, (x, y, label) in positions.items():
        add_node(drawing, x, y, 106 if node not in {"N6", "N9"} else 120, 28, label,
                 decision=node in decisions, terminal=node in terminals)
    for index, (start, end) in enumerate(IV_EDGES, 1):
        if (start, end) == ("N5", "N3"):
            drawing.add(Line(70, 91, 14, 91, strokeColor=MUTED, strokeWidth=0.85))
            drawing.add(Line(14, 91, 14, 205, strokeColor=MUTED, strokeWidth=0.85))
            add_arrow(drawing, 14, 205, 70, 191, "E8")
            continue
        x1, y1, _ = positions[start]; x2, y2, _ = positions[end]
        add_arrow(drawing, x1, y1 - 14, x2, y2 + 14, f"E{index}")
    return drawing


def participant_chart() -> Drawing:
    drawing = Drawing(500, 305)
    positions = {
        "N1": (70, 287, "N1 Entry"), "N2": (70, 257, "N2\nno response?"),
        "N3": (420, 257, "N3\nNO_RESPONSE"), "N4": (70, 217, "N4\nwithdrawn?"),
        "N5": (420, 217, "N5\nWITHDRAWN"), "N6": (70, 172, "N6\nnext BUSY?"),
        "N7": (235, 172, "N7\nbusy.start < end?"), "N8": (365, 150, "N8\nstart < busy.end?"),
        "N9": (420, 115, "N9\nUNAVAILABLE"), "N10": (70, 102, "N10\nnext AVAILABLE?"),
        "N11": (235, 102, "N11\navail.start <= start?"), "N12": (365, 80, "N12\nend <= avail.end?"),
        "N13": (420, 45, "N13\nAVAILABLE"), "N14": (70, 45, "N14\nUNAVAILABLE"),
        "N15": (245, 10, "N15 Common exit"),
    }
    decisions = {"N2", "N4", "N6", "N7", "N8", "N10", "N11", "N12"}
    terminals = {"N1", "N15"}
    for node, (x, y, label) in positions.items():
        add_node(drawing, x, y, 108, 27, label, decision=node in decisions, terminal=node in terminals)
    for index, (start, end) in enumerate(PA_EDGES, 1):
        x1, y1, _ = positions[start]; x2, y2, _ = positions[end]
        add_arrow(drawing, x1, y1 - 13, x2, y2 + 13, f"E{index}")
    return drawing


def load_junit() -> set[str]:
    root = ET.parse(JUNIT).getroot()
    assert not root.findall(".//failure") and not root.findall(".//error")
    assert not root.findall(".//skipped"), "JUnit contains skipped test evidence"
    names = [case.attrib["name"] for case in root.findall(".//testcase")]
    assert len(names) == len(set(names)), "JUnit contains duplicate testcase names"
    return set(names)


def load_srs_text() -> str:
    document = Document(SRS)
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    text = "\n".join(chunks)
    for fragment in (
        "Version 2.3", "BEST_AVAILABLE_BELOW_THRESHOLD", "NO_TIMESLOT_MEETS_THRESHOLD",
        "requested Minimum-Attendee Threshold", "actual attendance",
    ):
        assert fragment in text, f"SRS v2.3 oracle missing: {fragment}"
    return text


def source_method(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    lines = source.splitlines()
                    return "\n".join(
                        f"{number:>4}  {lines[number - 1]}"
                        for number in range(child.lineno, child.end_lineno + 1)
                    )
    raise AssertionError(f"method not found: {class_name}.{method_name}")


black_cases = [
    ("BB-DUR-01", "FR-A1.1", "duration 14", "Reject below 15", "ValueError: duration must be 15 to 480 minutes", "test_bb_dur_01_rejects_duration_14_below_minimum"),
    ("BB-DUR-02", "FR-A1.1", "duration 15", "Accept lower boundary", "OK; ranked; slot duration 15", "test_bb_dur_02_accepts_duration_15_at_minimum"),
    ("BB-DUR-03", "FR-A1.1", "duration 480", "Accept upper boundary", "OK; ranked; slot duration 480", "test_bb_dur_03_accepts_duration_480_at_maximum"),
    ("BB-DUR-04", "FR-A1.1", "duration 481", "Reject above 480", "ValueError: duration must be 15 to 480 minutes", "test_bb_dur_04_rejects_duration_481_above_maximum"),
    ("BB-DUR-05", "FR-A1.1", "duration 16", "Accept valid neighbour", "OK; all generated slots are 16 minutes", "test_bb_dur_05_accepts_duration_16_just_above_minimum"),
    ("BB-DUR-06", "FR-A1.1", "duration 479", "Accept valid neighbour", "OK; all generated slots are 479 minutes", "test_bb_dur_06_accepts_duration_479_just_below_maximum"),
    ("BB-THR-01", "FR-D1", "2 available; requested 2", "Normal result", "OK; all ranked attendee_count=2", "test_bb_thr_01_returns_ok_when_threshold_is_met"),
    ("BB-THR-02", "FR-D1.1 / FR-E1.1", "best 2; requested 3", "Label near match; preserve 3", "BEST_AVAILABLE_BELOW_THRESHOLD; threshold 3; actual 2; warning names both", "test_bb_thr_02_returns_best_available_when_requested_threshold_is_narrowly_missed"),
    ("BB-THR-03", "FR-D1.1", "best 1; requested 2", "No group result; no routing", "NO_TIMESLOT_MEETS_THRESHOLD; 0 combinations; 0 route calls", "test_bb_thr_03_returns_no_timeslot_when_two_person_group_cannot_form"),
    ("BB-THR-04", "FR-A4", "threshold 0", "Reject non-positive value", "422-boundary ValueError with exact public message", "test_bb_thr_04_rejects_zero_threshold_as_non_positive"),
    ("BB-THR-05", "FR-A4 / FR-D1", "1 available; requested 1", "Accept explicit positive value", "OK; threshold 1; ranked attendee_count=1", "test_bb_thr_05_accepts_explicit_threshold_one_for_one_available_participant"),
    ("BB-VEN-01", "FR-C3", "badminton; football-only venue", "No supporting venue", "NO_SUPPORTING_VENUES; no ranked options", "test_bb_ven_01_returns_no_supporting_venues_for_wrong_activity_partition"),
    ("BB-VEN-02", "FR-C3 / FR-C4", "mixed supporting/non-supporting", "Filter before shortlist", "Only badminton-hall appears in shortlist and ranking", "test_bb_ven_02_filters_mixed_venues_before_shortlisting_and_ranking"),
    ("BB-LOC-01", "FR-C4 / NFR-3", "all origins invalid/unavailable", "No centroid; no routing", "NO_VALID_LOCATIONS; 0 route calls", "test_bb_loc_01_returns_no_valid_locations_when_centroid_cannot_be_computed"),
    ("BB-RTE-01", "NFR-3", "UNAVAILABLE; minutes None", "Never invent duration", "DATA_UNAVAILABLE; minutes None; no rank", "test_bb_rte_01_marks_unavailable_provider_data_without_fabricating_a_journey"),
    ("BB-RTE-02", "NFR-3", "router raises RuntimeError", "Contain provider error", "Travel ERROR; DATA_UNAVAILABLE; no rank", "test_bb_rte_02_contains_provider_exception_as_error_status"),
    ("BB-RTE-03", "NFR-3", "AVAILABLE but minutes None", "Treat malformed success as error", "Travel ERROR; minutes None; DATA_UNAVAILABLE", "test_bb_rte_03_treats_available_route_without_duration_as_unusable"),
    ("BB-JRN-01", "FR-D3", "journey 60; cap 60", "Keep exact boundary", "OK; ranked; exceeded flag False", "test_bb_jrn_01_keeps_journey_at_60_minute_limit"),
    ("BB-JRN-02", "FR-D3", "journey 61; cap 60", "Exclude above cap", "No rank; exclusion JOURNEY_LIMIT", "test_bb_jrn_02_excludes_journey_one_minute_above_limit"),
    ("BB-WGT-01", "FR-D9", "weight 0%", "Accept lower boundary", "OK; reported weight 0; ranked", "test_bb_wgt_01_accepts_zero_percent_attendance_weight"),
    ("BB-WGT-02", "FR-D9", "weight 100%", "Accept upper boundary", "OK; reported weight 100; ranked", "test_bb_wgt_02_accepts_100_percent_attendance_weight"),
    ("BB-WGT-03", "FR-D9", "weight -1%", "Reject below 0", "ValueError: weight must be between 0 and 100", "test_bb_wgt_03_rejects_weight_minus_one_below_minimum"),
    ("BB-WGT-04", "FR-D9", "weight 101%", "Reject above 100", "ValueError: weight must be between 0 and 100", "test_bb_wgt_04_rejects_weight_101_above_maximum"),
    ("BB-WGT-05", "FR-D9.1", "weight 10%", "Accept discrete neighbour", "OK; reported weight 10; ranked", "test_bb_wgt_05_accepts_ten_percent_valid_neighbour"),
    ("BB-WGT-06", "FR-D9.1", "weight 90%", "Accept discrete neighbour", "OK; reported weight 90; ranked", "test_bb_wgt_06_accepts_ninety_percent_valid_neighbour"),
]

iv_cases = [
    ("WB-IV-01", "N1-N2-N3(F)-N7(F)-N10", "no intervals", "[]", "[]", "test_wb_iv_01_path_empty_input_returns_empty_ordered_list"),
    ("WB-IV-02", "N1-N2-N3(T)-N4(T)-N6-N10", "start = range start - 1 min", "422 range detail", "422; exact range detail", "test_wb_iv_02_path_start_one_minute_before_session_is_rejected"),
    ("WB-IV-03", "N1-N2-N3(T)-N4(F)-N5(T)-N6-N10", "end = range end + 1 min", "422 range detail", "422; exact range detail", "test_wb_iv_03_path_end_one_minute_after_session_is_rejected"),
    ("WB-IV-04", "N1-N2-N3(T)-N4(F)-N5(F)-N3(F)-N7(F)-N10", "exact range endpoints", "one unchanged interval", "one unchanged interval", "test_wb_iv_04_path_exact_session_endpoints_are_accepted"),
    ("WB-IV-05", "loop valid intervals; N7(T)-N8(T)-N9-N10", "two intervals overlap 1 min", "422 overlap detail", "422; exact overlap detail", "test_wb_iv_05_path_one_minute_overlap_is_rejected"),
    ("WB-IV-06", "loop valid intervals; N7(T)-N8(F)-N7(F)-N10", "unsorted touching intervals", "sorted; touching accepted", "literal ascending endpoints", "test_wb_iv_06_path_unsorted_touching_intervals_are_sorted_and_accepted"),
]

pa_cases = [
    ("WB-PA-01", "N1-N2(F)-N4(F)-N6(F)-N10(F)-N14-N15", "active; no blocks", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_01_path_active_with_no_blocks_is_unavailable"),
    ("WB-PA-02", "N1-N2(T)-N3-N15", "record missing", "NO_RESPONSE", "NO_RESPONSE", "test_wb_pa_02_path_no_response_returns_no_response"),
    ("WB-PA-03", "N1-N2(F)-N4(T)-N5-N15", "withdrawn; AVAILABLE exists", "WITHDRAWN", "WITHDRAWN", "test_wb_pa_03_path_withdrawn_returns_withdrawn"),
    ("WB-PA-04", "N6(T)-N7(F)-N6(F)-N10(F)-N14-N15", "BUSY starts at slot end", "UNAVAILABLE; no overlap", "UNAVAILABLE", "test_wb_pa_04_path_busy_starting_at_slot_end_does_not_overlap"),
    ("WB-PA-05", "N6(T)-N7(T)-N8(F)-N6(F)-N10(F)-N14-N15", "BUSY ends at slot start", "UNAVAILABLE; no overlap", "UNAVAILABLE", "test_wb_pa_05_path_busy_ending_at_slot_start_does_not_overlap"),
    ("WB-PA-06", "N6(T)-N7(T)-N8(F)-N6(T)-N7(T)-N8(T)-N9-N15", "earlier nonmatch; later 1-min BUSY overlap", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_06_path_one_minute_busy_overlap_overrides_full_availability"),
    ("WB-PA-07", "N6(F)-N10(T)-N11(F)-N10(F)-N14-N15", "AVAILABLE starts 1 min late", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_07_path_available_block_starting_one_minute_late_is_unavailable"),
    ("WB-PA-08", "N6(F)-N10(T)-N11(T)-N12(F)-N10(F)-N14-N15", "AVAILABLE ends 1 min early", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_08_path_available_block_ending_one_minute_early_is_unavailable"),
    ("WB-PA-09", "N6(F)-N10(T)-N11(T)-N12(F)-N10(T)-N11(T)-N12(T)-N13-N15", "earlier nonmatch; later exact full coverage", "AVAILABLE", "AVAILABLE", "test_wb_pa_09_path_exact_full_available_coverage_is_available"),
]

pr_cases = [
    ("WB-PR-01", "below Session threshold", "BELOW_THRESHOLD", "test_wb_pr_01_path_below_session_threshold"),
    ("WB-PR-02", "park skips sports constraints", "None", "test_wb_pr_02_path_non_sports_skips_sports_constraints"),
    ("WB-PR-03", "sports group-size failure", "GROUP_SIZE", "test_wb_pr_03_path_sports_group_size_failure"),
    ("WB-PR-04", "sports: no group/lead constraints", "None", "test_wb_pr_04_path_sports_has_no_group_or_lead_constraint"),
    ("WB-PR-05", "sports: meets group; no lead", "None", "test_wb_pr_05_path_sports_meets_group_size_without_lead_constraint"),
    ("WB-PR-06", "booking lead fails by 1 hour", "BOOKING_LEAD_TIME", "test_wb_pr_06_path_sports_booking_lead_failure"),
    ("WB-PR-07", "exact booking-lead boundary", "None", "test_wb_pr_07_path_sports_exactly_meets_booking_lead_boundary"),
]


def case_page(rows, part: str, mutations: list[tuple[str, str]]) -> list:
    data = [["Case", "Req.", "Input / precondition", "Expected", "Actual", "Result"]]
    data += [[row[0], row[1], row[2], row[3], row[4], "PASS"] for row in rows]
    return section(f"Black-box Cases and Results ({part})", "3") + [
        report_table(
            data, [20 * mm, 20 * mm, 31 * mm, 36 * mm, 53 * mm, 13 * mm],
            font_size=7.0, leading=9.0, padding=5.0,
        ),
        Spacer(1, 4 * mm),
        p("Actual outputs above are literal conditions asserted by the named automated test; they are not copied from the expected-output column.", "Small"),
        p("Mutation check", "Subsection"),
        report_table(
            [["Representative defect", "Test that would fail"]] + [list(item) for item in mutations],
            [108 * mm, 65 * mm], font_size=7.3, leading=9.3,
        ),
    ]


def build_story() -> list:
    passed = load_junit()
    load_srs_text()
    assessed = black_cases + iv_cases + pa_cases
    assessed_names = {row[-1] for row in assessed}
    supplemental_names = {row[-1] for row in pr_cases}
    assert len(black_cases) == 25 and len(iv_cases) == 6 and len(pa_cases) == 9
    assert len(assessed) == 40 and len(pr_cases) == 7
    assert len(assessed_names) == 40 and len(supplemental_names) == 7
    assert passed == assessed_names | supplemental_names
    assert verify_basis_graph(IV_NODES, IV_EDGES, IV_PATHS) == 6
    assert verify_basis_graph(PA_NODES, PA_EDGES, PA_PATHS) == 9
    assert any(
        ["N8", "N6", "N7", "N8", "N9"] == path[index:index + 5]
        for path in PA_PATHS for index in range(len(path) - 4)
    )
    assert any(
        ["N12", "N10", "N11", "N12", "N13"] == path[index:index + 5]
        for path in PA_PATHS for index in range(len(path) - 4)
    )

    story: list = []
    story += [Spacer(1, 22 * mm), p("SC2006 LAB 4", "Subtitle"), Spacer(1, 4 * mm)]
    story += [p("Software Testing Report", "ReportTitle")]
    story += [p("Pilot-aligned black-box and white-box evidence", "Subtitle")]
    story += [Spacer(1, 9 * mm), HRFlowable(width="45%", thickness=3, color=GOLD, hAlign="LEFT"), Spacer(1, 10 * mm)]
    cover_data = [
        ["Work product", "Test cases, control-flow graphs and executed results"],
        ["Prepared by", "Group 1 - Software Testing"],
        ["System", "Group Scheduling Application"],
        ["Production baseline", f"feature/production-pilot @ {PILOT_SHA[:7]}"],
        ["SRS oracle", "SRS v2.3 - Pilot near-match recovery"],
        ["Execution date", "7 November 2026 (Asia/Singapore)"],
        ["Assessment result", "40/40 assessed tests passed"],
        ["Total Lab 4 evidence", "47/47 tests passed (includes 7 supplemental regressions)"],
    ]
    cover = Table([[p(a, "Small"), p(b, "Small")] for a, b in cover_data], colWidths=[40 * mm, 112 * mm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE_GREEN), ("TEXTCOLOR", (0, 0), (0, -1), GREEN),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [cover, Spacer(1, 10 * mm), p("Submission scope", "Subsection")]
    story += [p("This report satisfies Lab 4 Manual sections 3.2.1-3.2.4: one important control boundary is tested with equivalence classes and boundary values; two complex class methods are tested with basis paths; redundant cases are minimised; and every executed case records input, expected output, actual output and pass/fail status.")]
    story += [PageBreak()]

    story += section("Scope, Requirement Audit and Baseline", "1")
    audit = [
        ["Manual requirement", "Evidence", "Status"],
        ["3.2.1 one control class", "RecommendationEngine.generate() boundary; Sections 2-3", "Met"],
        ["3.2.1 equivalence classes", "Seven input characteristics; Section 2.1", "Met"],
        ["3.2.1 boundary values", "Duration, threshold, journey and weight neighbours", "Met"],
        ["3.2.2 two complex methods", "AvailabilityService._validate_intervals and _ParticipantAvailability.status_for", "Met"],
        ["3.2.2 basis-path testing", "Two CFGs; V(G)=6 and V(G)=9; 15 assessed paths", "Met"],
        ["3.2.3 minimise cases", "One representative per partition plus necessary boundary neighbours", "Met"],
        ["3.2.4 execute/document", "47-case JUnit; every assessment row has expected/actual/result", "Met"],
    ]
    story += [report_table(audit, [49 * mm, 104 * mm, 20 * mm], font_size=7.2, leading=9.2)]
    story += [p("1.1 Authoritative baseline", "Subsection")]
    story += [p(f"The tested product baseline is <b>feature/production-pilot</b> at commit <b>{PILOT_SHA}</b>. SRS v2.3 is the requirements oracle for implemented Pilot behaviour. The assessment does not treat an older SRS contradiction as a reason to change working production behaviour.")]
    baseline = [
        ["Evidence layer", "Version / result"],
        ["Production code", f"Pilot commit {PILOT_SHA[:7]}"],
        ["Requirements", "SRS v2.3: normal threshold, labelled recovery, explicit no-result"],
        ["Assessment tests", "25 black-box + 6 interval paths + 9 attendance paths = 40"],
        ["Supplemental regressions", "7 pre-routing feasibility paths"],
        ["Fresh Lab 4 run", "47 passed; 0 failed; 0 errors"],
    ]
    story += [report_table(baseline, [48 * mm, 125 * mm], font_size=7.5, leading=9.6)]
    story += [p("No production method was changed to make this report pass; only SRS documentation, tests, CFGs and this report were added or strengthened.", "Callout"), PageBreak()]

    story += section("Black-box Test Design", "2")
    story += [p("The recommendation engine is treated as a sealed control boundary. Tests construct complete RecommendationRequest values and assert only returned RecommendationResult data or public validation errors. The deterministic router replaces only the external network provider; candidate generation, feasibility, routing adaptation, scoring and ranking remain real production code.")]
    eq = [
        ["Characteristic", "Equivalence classes", "Cases"],
        ["Duration", "invalid <15; valid 15-480; invalid >480", "BB-DUR-01..06"],
        ["Requested attendance", "met; missed with best>=2; best<2; invalid 0; explicit 1", "BB-THR-01..05"],
        ["Venue support", "none; mixed catalogue with one supporting venue", "BB-VEN-01..02"],
        ["Starting locations", "valid centroid; no valid active origins", "BB-THR-01, BB-LOC-01"],
        ["Routing result", "available; unavailable; exception; malformed available-without-duration", "BB-JRN-01, BB-RTE-01..03"],
        ["Journey duration", "at cap; above cap", "BB-JRN-01..02"],
        ["Attendance weight", "invalid <0; valid 0-100 in 10% steps; invalid >100", "BB-WGT-01..06"],
    ]
    story += [p("2.1 Equivalence classes", "Subsection"), report_table(eq, [38 * mm, 99 * mm, 36 * mm], font_size=7.1, leading=9.1)]
    bva = [
        ["Boundary", "Selected values", "Expected relation", "Cases"],
        ["Duration minimum 15", "14, 15, 16", "reject / accept / accept", "BB-DUR-01,02,05"],
        ["Duration maximum 480", "479, 480, 481", "accept / accept / reject", "BB-DUR-06,03,04"],
        ["Threshold positivity", "0, 1", "reject / accept", "BB-THR-04,05"],
        ["Journey cap 60", "60, 61", "retain / exclude", "BB-JRN-01,02"],
        ["Weight minimum 0", "-1, 0, 10", "reject / accept / accept", "BB-WGT-03,01,05"],
        ["Weight maximum 100", "90, 100, 101", "accept / accept / reject", "BB-WGT-06,02,04"],
    ]
    story += [p("2.2 Boundary-value analysis", "Subsection"), report_table(bva, [40 * mm, 38 * mm, 55 * mm, 40 * mm], font_size=7.1, leading=9.1)]
    story += [p("2.3 Minimisation", "Subsection"), p("Each non-boundary partition has one representative. Numeric boundaries use invalid/endpoint/valid-neighbour values where they distinguish a realistic defect. Shared valid setup is reused rather than multiplying unrelated combinations. The 25 cases therefore improve fault detection without a Cartesian-product explosion."), PageBreak()]

    story += case_page(black_cases[:9], "1 of 3", [
        ("Accept a 14-minute Session or alter a generated 16-minute slot", "BB-DUR-01 / BB-DUR-05"),
        ("Replace the preserved requested threshold 3 with another value", "BB-THR-02"),
        ("Route even though no two-person group can form", "BB-THR-03"),
    ]) + [PageBreak()]
    story += case_page(black_cases[9:17], "2 of 3", [
        ("Let an unsupported football venue enter a badminton shortlist", "BB-VEN-02"),
        ("Convert a missing route duration into a fabricated zero", "BB-RTE-01 / BB-RTE-03"),
        ("Propagate a provider exception instead of containing it", "BB-RTE-02"),
    ]) + [PageBreak()]
    story += case_page(black_cases[17:], "3 of 3", [
        ("Exclude the exact 60-minute journey boundary", "BB-JRN-01"),
        ("Accept an attendance weight outside 0-100", "BB-WGT-03 / BB-WGT-04"),
        ("Snap the valid 10% or 90% neighbour to another value", "BB-WGT-05 / BB-WGT-06"),
    ])
    story += [p("Near-match trace", "Subsection"), p("BB-THR-02 specifically proves the SRS v2.3 recovery contract: the result status is BEST_AVAILABLE_BELOW_THRESHOLD, the requested Minimum-Attendee Threshold remains 3, every ranked option has actual attendance 2, and the warning communicates requested 3 versus actual 2. BB-THR-03 proves that a best attendance below 2 returns NO_TIMESLOT_MEETS_THRESHOLD and performs no routing."), PageBreak()]

    story += section("White-box Method 1: Interval Validation", "4")
    story += [p("Selected method: <b>AvailabilityService._validate_intervals()</b>. It sorts submissions, enforces the Session date range, rejects overlap, and returns a deterministic order. These branches protect availability data before persistence and recommendation generation.")]
    story += [p("4.1 Production source excerpt", "Subsection"), Preformatted(source_method(ROOT / "backend/app/services/application_services.py", "AvailabilityService", "_validate_intervals"), styles["CodeBlock"])]
    story += [p("4.2 Control-flow graph", "Subsection"), intervals_chart(), p("Figure 1. Fixed CFG convention: loop conditions and both range comparisons are decisions; exceptions converge at a common graph exit.", "Small")]
    complexity_iv = [
        ["Measure", "Value"], ["Nodes", "N = 10"], ["Edges", "E = 14"],
        ["Graph formula", "14 - 10 + 2 = 6"], ["Predicate formula", "5 decisions + 1 = 6"],
        ["Verified path-vector rank", "6 over the rational numbers"],
    ]
    story += [p("4.3 Cyclomatic complexity", "Subsection"), report_table(complexity_iv, [55 * mm, 118 * mm], font_size=7.7, leading=9.7), PageBreak()]

    story += section("Interval-validation Basis Paths", "4.4")
    iv_table = [["Case", "Independent node path", "Input", "Expected", "Actual", "Result"]]
    iv_table += [[r[0], r[1], r[2], r[3], r[4], "PASS"] for r in iv_cases]
    story += [report_table(iv_table, [17 * mm, 53 * mm, 34 * mm, 28 * mm, 29 * mm, 13 * mm], font_size=6.4, leading=8.0)]
    story += [p("The six paths cover all 14 directed CFG edges. Their edge-incidence vectors have rational rank 6, so the path set is independent under the stated graph convention. IV-04 and IV-06 distinguish inclusive range endpoints and non-overlapping touching intervals from the two error paths.", "Callout")]
    story += [p("Faults detected by this set", "Subsection")]
    story += [p("A missing range check fails IV-02 or IV-03; changing inclusive endpoints to strict ones fails IV-04; changing the overlap comparison from < to <= fails IV-06; omitting sorting fails the literal ordering assertion in IV-06; and returning an incorrect public status/detail fails IV-02, IV-03 or IV-05."), PageBreak()]

    story += section("White-box Method 2: Participant Attendance", "5")
    story += [p("Selected method: <b>_ParticipantAvailability.status_for()</b>. It preserves NO_RESPONSE and WITHDRAWN, gives BUSY precedence over AVAILABLE, and requires full slot coverage. For CFG purposes each any(...) generator is expanded into iterator-next plus its two short-circuit comparisons; this convention is used consistently in graph, formulas and paths.")]
    story += [p("5.1 Production source excerpt", "Subsection"), Preformatted(source_method(ROOT / "backend/app/recommender/candidate_generation.py", "_ParticipantAvailability", "status_for"), styles["CodeBlock"])]
    story += [p("5.2 Control-flow graph", "Subsection"), participant_chart(), p("Figure 2. Expanded short-circuit CFG. Boundary paths show that intervals touching—but not crossing—the slot boundary do not overlap.", "Small")]
    complexity_pa = [
        ["Measure", "Value"], ["Nodes", "N = 15"], ["Edges", "E = 22"],
        ["Graph formula", "22 - 15 + 2 = 9"], ["Predicate formula", "8 decisions + 1 = 9"],
        ["Verified path-vector rank", "9 over the rational numbers"],
    ]
    story += [p("5.3 Cyclomatic complexity", "Subsection"), report_table(complexity_pa, [55 * mm, 118 * mm], font_size=7.7, leading=9.7), PageBreak()]

    story += section("Participant-attendance Basis Paths", "5.4")
    pa_table = [["Case", "Independent node path", "Input", "Expected", "Actual", "Result"]]
    pa_table += [[r[0], r[1], r[2], r[3], r[4], "PASS"] for r in pa_cases]
    story += [report_table(pa_table, [17 * mm, 58 * mm, 35 * mm, 25 * mm, 25 * mm, 13 * mm], font_size=6.15, leading=7.7)]
    story += [p("The nine paths cover all 22 directed edges and have rational rank 9. PA-04 and PA-05 exercise opposite short-circuit boundary outcomes; PA-06 skips an earlier nonmatching BUSY block before a later overlap; PA-07 and PA-08 isolate the two full-containment comparisons; PA-09 skips an earlier nonmatching AVAILABLE block before a later full-cover match.", "Callout")]
    story += [PageBreak()]

    story += section("Supplemental Pre-routing Regressions", "6")
    story += [p("Seven existing pre_routing_exclusion() paths remain executable regression evidence, but they are not counted as either of the two assessed white-box methods. This prevents the report from discarding useful tests while keeping the Manual 3.2.2 scope precise.")]
    pr_table = [["Case", "Regression condition", "Observed", "Result"]]
    pr_table += [[r[0], r[1], r[2], "PASS"] for r in pr_cases]
    story += [report_table(pr_table, [23 * mm, 92 * mm, 42 * mm, 16 * mm], font_size=7.2, leading=9.2)]
    story += [p("6.1 Why supplemental", "Subsection"), p("The assessed complexity and independent-path claims apply only to _validate_intervals() and status_for(). The seven WB-PR cases are reported separately so their presence cannot inflate the 15 assessed white-box count.")]
    totals = [
        ["Evidence group", "Count", "Pass", "Assessment role"],
        ["Black-box (BB)", "25", "25", "Assessed"],
        ["Interval paths (WB-IV)", "6", "6", "Assessed method 1"],
        ["Attendance paths (WB-PA)", "9", "9", "Assessed method 2"],
        ["Pre-routing regressions (WB-PR)", "7", "7", "Supplemental"],
        ["Total", "47", "47", "40 assessed + 7 supplemental"],
    ]
    story += [report_table(totals, [64 * mm, 22 * mm, 22 * mm, 65 * mm], font_size=7.4, leading=9.4), PageBreak()]

    story += section("Execution Evidence and Cross-check", "7")
    result_data = [
        ["Verification", "Observed result", "Status"],
        ["Black-box test file", "25 passed", "PASS"],
        ["Assessed white-box file", "15 passed", "PASS"],
        ["Supplemental pre-routing file", "7 passed", "PASS"],
        ["Fresh Lab 4 JUnit", "47 passed; 0 failed; 0 errors", "PASS"],
        ["Full backend regression", "311 passed; one third-party deprecation warning", "PASS"],
        ["Frontend Node + UI tests", "21 passed", "PASS"],
        ["Frontend lint", "exit code 0", "PASS"],
        ["Frontend production build", "152 modules transformed; exit code 0", "PASS"],
    ]
    story += [report_table(result_data, [58 * mm, 90 * mm, 25 * mm], font_size=7.4, leading=9.4)]
    story += [p("7.1 One-to-one evidence mapping", "Subsection"), p("The generator refuses to build unless the JUnit names are exactly the 40 assessment mappings plus the seven supplemental mappings. Duplicate assessment IDs, missing cases, extra cases, failures and errors are structural failures—not prose warnings.")]
    checks = [
        ["Cross-check", "Verified value"],
        ["Assessment IDs", "40 unique: 25 BB + 6 WB-IV + 9 WB-PA"],
        ["Supplemental IDs", "7 unique WB-PR"],
        ["JUnit total", "47 unique passing test names"],
        ["Interval graph", "N=10, E=14, full edge coverage, path rank 6"],
        ["Attendance graph", "N=15, E=22, full edge coverage, path rank 9"],
        ["SRS oracle", "v2.3 contains both recovery statuses and requested-versus-actual disclosure"],
        ["Secrets/placeholders", "Rejected by final extracted-text assertions"],
    ]
    story += [report_table(checks, [55 * mm, 118 * mm], font_size=7.4, leading=9.4), PageBreak()]

    story += section("SRS v2.3 Traceability and Consistency", "8")
    trace = [
        ["Requirement / rule", "Executed evidence", "Consistency result"],
        ["FR-A1.1 duration 15-480", "BB-DUR-01..06", "Invalid neighbours rejected; endpoints and valid neighbours accepted"],
        ["FR-A4 positive threshold", "BB-THR-04..05", "0 rejected; explicit 1 accepted"],
        ["FR-D1 normal threshold", "BB-THR-01", "Threshold-met recommendations remain normal"],
        ["FR-D1.1 recovery", "BB-THR-02..03", "Near match labelled; below system minimum returns no candidates/routing"],
        ["FR-E1.1 disclosure", "BB-THR-02", "Requested 3 preserved; actual 2; warning contains both values"],
        ["FR-C3 activity support", "BB-VEN-01..02", "Unsupported venues excluded before shortlist/ranking"],
        ["FR-D3 60-minute cap", "BB-JRN-01..02", "60 retained; 61 excluded"],
        ["NFR-3 missing data", "BB-RTE-01..03", "No zero duration fabricated; unavailable/error remains explicit"],
        ["Availability interval integrity", "WB-IV-01..06", "Range, overlap, sorting and touching boundaries verified"],
        ["Attendance-state semantics", "WB-PA-01..09", "Four states, BUSY precedence and full coverage verified"],
    ]
    story += [report_table(trace, [45 * mm, 42 * mm, 86 * mm], font_size=6.9, leading=8.8)]
    story += [p("8.1 Pilot near-match decision", "Subsection")]
    story += [p("The production Pilot intentionally avoids a dead end when the requested threshold is narrowly missed. If the best actual attendance is at least the default minimum of 2, it returns only the best-attended slots as <b>BEST_AVAILABLE_BELOW_THRESHOLD</b>, keeps the requested value unchanged, and warns with requested versus actual attendance. If best attendance is below 2, it returns <b>NO_TIMESLOT_MEETS_THRESHOLD</b> before routing. This is now stated in SRS v2.3 and tested without changing production code.", "Callout")]
    story += [p("8.2 Internal consistency", "Subsection"), p("The same fixed graph convention, node labels, edge sets, path IDs and complexity values are used by the DOT files, automated test names, generator data and this PDF. The report therefore has no conflict between diagrams, formulas and executed evidence."), PageBreak()]

    story += section("Limitations, Conclusion and Reproduction", "9")
    story += [p("9.1 Limitations", "Subsection")]
    story += [p("The black-box control tests use a deterministic router at the external provider port so results do not depend on OneMap availability. They validate the application's handling of provider success, absence, malformed success and exceptions, but do not replace deployed integration smoke tests for Google OAuth, OneMap, PostgreSQL or Render. Basis-path coverage proves the selected control-flow paths, not every possible data combination or system-level concurrency condition.")]
    story += [p("9.2 Conclusion", "Subsection")]
    story += [p("The deliverable meets Lab 4 Manual sections 3.2.1-3.2.4 with current Pilot evidence: 25 black-box equivalence/boundary cases, 15 assessed basis paths for two class methods, and seven clearly separated supplemental regressions. All 47 tests passed, the two CFG calculations and path-vector ranks agree, and the SRS v2.3 near-match behavior is fully traceable.", "Callout")]
    story += [p("9.3 Reproduction", "Subsection")]
    commands = (
        "cd backend\n"
        "python -m pytest tests/lab4 -q --junitxml=../.superpowers/sdd/2026-11-07-pilot-aligned-srs-lab4-report/lab4-junit.xml\n"
        "cd ..\n"
        "python docs/lab4/generate_report.py\n"
        "python docs/srs/update_v2_3.py 'docs/SRS Group Scheduling Application v2.3.docx'"
    )
    story += [Preformatted(commands, styles["CodeBlock"])]
    story += [p("Artifacts: docs/SRS Group Scheduling Application v2.3.docx/.pdf and docs/lab4/Lab4_Software_Testing_Report.pdf. Test and CFG sources are committed on branch lab4/software-testing-report.", "Small")]
    story += [Spacer(1, 4 * mm), p("Reference: SC2006 Lab 4 Manual, sections 3.2.1-3.2.4.", "Small")]
    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ReportDocTemplate(str(OUTPUT)).build(build_story(), canvasmaker=InvariantCanvas)
    reader = PdfReader(str(OUTPUT))
    page_count = len(reader.pages)
    assert 12 <= page_count <= 15, f"report must be 12-15 pages, got {page_count}"
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    report_ids = {row[0] for row in black_cases + iv_cases + pa_cases}
    assert len(report_ids) == 40
    assert len(black_cases) == 25 and len(iv_cases) + len(pa_cases) == 15 and len(pr_cases) == 7
    assert len(load_junit()) == 47
    for token in (
        "40/40 assessed tests passed", "47/47 tests passed", "25 black-box",
        "14 - 10 + 2 = 6", "22 - 15 + 2 = 9",
        "3.2.1", "3.2.2", "3.2.3", "3.2.4",
        "BEST_AVAILABLE_BELOW_THRESHOLD", "NO_TIMESLOT_MEETS_THRESHOLD",
        "requested 3", "actual 2", PILOT_SHA[:7],
        "WB-IV-06", "WB-PA-09", "WB-PR-07",
    ):
        assert token in extracted, f"missing report token: {token}"
    lowered = extracted.lower()
    for forbidden in (
        "lorem ipsum", "todo:", "[placeholder]", "eyjhb gcioi".replace(" ", ""),
        "authorization: bearer", "client_secret=", "api_key=",
    ):
        assert forbidden not in lowered, f"forbidden secret/placeholder marker: {forbidden}"
    print(f"created {OUTPUT} ({page_count} pages; 40 assessed + 7 supplemental = 47 passed)")


if __name__ == "__main__":
    main()
