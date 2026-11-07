from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
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
JUNIT = ROOT / ".superpowers/sdd/2026-11-07-lab4-software-testing-report/lab4-junit.xml"

GREEN = colors.HexColor("#174A3A")
MID_GREEN = colors.HexColor("#2F6650")
PALE_GREEN = colors.HexColor("#DCEBDF")
GOLD = colors.HexColor("#D19A3A")
PALE_GOLD = colors.HexColor("#FFF1CC")
INK = colors.HexColor("#26322C")
MUTED = colors.HexColor("#5B655E")
CREAM = colors.HexColor("#F7F4EC")
RED = colors.HexColor("#8E3731")
PALE_RED = colors.HexColor("#F7D8D5")
WHITE = colors.white
GRID = colors.HexColor("#C7CEC9")


class InvariantCanvas(pdfcanvas.Canvas):
    """Create byte-for-byte stable PDFs for unchanged report content."""

    def __init__(self, *args, **kwargs):
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=26,
    leading=31,
    textColor=GREEN,
    alignment=TA_LEFT,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="Subtitle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=12,
    leading=17,
    textColor=MUTED,
    spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="Section",
    parent=styles["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    textColor=GREEN,
    spaceBefore=4,
    spaceAfter=9,
))
styles.add(ParagraphStyle(
    name="Subsection",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=12.5,
    leading=16,
    textColor=MID_GREEN,
    spaceBefore=8,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Body",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=9.4,
    leading=13.2,
    textColor=INK,
    spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="Small",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=7.5,
    leading=10,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="Tiny",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=6.4,
    leading=8.2,
    textColor=INK,
))
styles.add(ParagraphStyle(
    name="TableHeader",
    parent=styles["BodyText"],
    fontName="Helvetica-Bold",
    fontSize=7,
    leading=8.5,
    textColor=WHITE,
    alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="CodeBlock",
    fontName="Courier",
    fontSize=6.1,
    leading=7.1,
    textColor=INK,
    leftIndent=5,
    rightIndent=5,
    borderColor=GRID,
    borderWidth=0.5,
    borderPadding=4,
    backColor=colors.HexColor("#F3F5F3"),
    spaceBefore=3,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Callout",
    parent=styles["BodyText"],
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=12.5,
    textColor=GREEN,
    leftIndent=8,
    rightIndent=8,
    borderColor=GOLD,
    borderWidth=1,
    borderPadding=8,
    backColor=PALE_GOLD,
    spaceBefore=5,
    spaceAfter=9,
))


def p(text: str, style: str = "Body") -> Paragraph:
    return Paragraph(text, styles[style])


def cell(text: str, style: str = "Tiny") -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])


def section(title: str, number: str) -> list:
    return [p(f"{number}  {title}", "Section"), HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=8)]


def table(data, widths, *, header=True, font_size=6.4, leading=8.2, h_align="LEFT"):
    converted = []
    for r, row in enumerate(data):
        converted.append([
            Paragraph(
                escape(str(value)).replace("\n", "<br/>"),
                styles["TableHeader"] if header and r == 0 else ParagraphStyle(
                    f"table-{r}-{c}-{font_size}",
                    parent=styles["Tiny"],
                    fontSize=font_size,
                    leading=leading,
                    alignment=TA_LEFT,
                ),
            )
            for c, value in enumerate(row)
        ])
    cls = LongTable if len(data) > 8 else Table
    result = cls(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign=h_align, splitByRow=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in range(1, len(data)):
        commands.append(("BACKGROUND", (0, r), (-1, r), WHITE if r % 2 else CREAM))
    result.setStyle(TableStyle(commands))
    return result


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=17 * mm,
            rightMargin=17 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title="Lab 4 Software Testing Report",
            author="Group 1 - Software Testing",
            subject="SC2006 Lab 4 black-box and white-box testing",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(PageTemplate(id="content", frames=[frame], onPage=self._decorate))

    def _decorate(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(GRID)
            canvas.line(self.leftMargin, A4[1] - 12 * mm, A4[0] - self.rightMargin, A4[1] - 12 * mm)
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(self.leftMargin, A4[1] - 9 * mm, "SC2006 Lab 4 | Software Testing")
            footer = f"Group 1 - Software Testing     |     Page {doc.page}"
            canvas.drawRightString(A4[0] - self.rightMargin, 9 * mm, footer)
        canvas.restoreState()


def add_arrow(d: Drawing, x1, y1, x2, y2, label: str | None = None, dashed=False):
    line = Line(x1, y1, x2, y2)
    line.strokeColor = MUTED
    line.strokeWidth = 1
    if dashed:
        line.strokeDashArray = [3, 2]
    d.add(line)
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 5
    tip = (x2, y2)
    left = (x2 - ux * size + px * size * 0.55, y2 - uy * size + py * size * 0.55)
    right = (x2 - ux * size - px * size * 0.55, y2 - uy * size - py * size * 0.55)
    d.add(Polygon([tip[0], tip[1], left[0], left[1], right[0], right[1]], fillColor=MUTED, strokeColor=MUTED))
    if label:
        d.add(String((x1 + x2) / 2 + 3, (y1 + y2) / 2 + 3, label, fontName="Helvetica-Bold", fontSize=8, fillColor=MUTED))


def add_node(d: Drawing, cx, cy, width, height, label, kind="box", fill=CREAM):
    if kind == "diamond":
        points = [cx, cy + height / 2, cx + width / 2, cy, cx, cy - height / 2, cx - width / 2, cy]
        d.add(Polygon(points, fillColor=fill, strokeColor=MID_GREEN, strokeWidth=1))
    elif kind == "oval":
        d.add(Rect(cx - width / 2, cy - height / 2, width, height, rx=height / 2, ry=height / 2, fillColor=fill, strokeColor=MID_GREEN, strokeWidth=1))
    else:
        d.add(Rect(cx - width / 2, cy - height / 2, width, height, rx=5, ry=5, fillColor=fill, strokeColor=MID_GREEN, strokeWidth=1))
    lines = label.split("\n")
    for i, line in enumerate(lines):
        d.add(String(cx, cy + (len(lines) - 1) * 4.5 - i * 9 - 3, line, fontName="Helvetica-Bold" if i == 0 else "Helvetica", fontSize=6.8, textAnchor="middle", fillColor=INK))


def pre_routing_chart() -> Drawing:
    d = Drawing(480, 360)
    main, side = 190, 390
    nodes = {
        "N1": (main, 346, 125, 24, "N1  Entry\nread count and venue", "oval", PALE_GREEN),
        "N2": (main, 310, 145, 30, "N2\ncount < session threshold?", "diamond", PALE_GOLD),
        "N3": (side, 310, 145, 28, "N3  return\nBELOW_THRESHOLD", "box", PALE_RED),
        "N4": (main, 265, 140, 30, "N4\nsports facility?", "diamond", PALE_GOLD),
        "N5": (main, 220, 150, 30, "N5\nminimum group size set?", "diamond", PALE_GOLD),
        "N6": (main, 175, 145, 30, "N6\ncount < venue minimum?", "diamond", PALE_GOLD),
        "N7": (side, 175, 140, 28, "N7  return\nGROUP_SIZE", "box", PALE_RED),
        "N8": (main, 130, 155, 30, "N8\nbooking lead time set?", "diamond", PALE_GOLD),
        "N9": (main, 95, 145, 24, "N9  calculate earliest bookable", "box", CREAM),
        "N10": (main, 60, 145, 30, "N10\nslot starts before earliest?", "diamond", PALE_GOLD),
        "N11": (side, 60, 155, 28, "N11  return\nBOOKING_LEAD_TIME", "box", PALE_RED),
        "N12": (side, 110, 120, 24, "N12  return None", "box", PALE_GREEN),
        "N13": (main, 18, 90, 22, "N13  Exit", "oval", PALE_GREEN),
    }
    for values in nodes.values():
        add_node(d, *values)
    add_arrow(d, main, 334, main, 325)
    add_arrow(d, main + 72, 310, side - 73, 310, "T")
    add_arrow(d, main, 295, main, 280, "F")
    add_arrow(d, main, 250, main, 235, "T")
    add_arrow(d, main + 70, 265, side - 60, 122, "F")
    add_arrow(d, main, 205, main, 190, "T")
    add_arrow(d, main + 75, 220, main + 75, 130, "F")
    add_arrow(d, main + 72, 175, side - 70, 175, "T")
    add_arrow(d, main, 160, main, 145, "F")
    add_arrow(d, main, 115, main, 107, "T")
    add_arrow(d, main + 77, 130, side - 60, 110, "F")
    add_arrow(d, main, 83, main, 75)
    add_arrow(d, main + 72, 60, side - 78, 60, "T")
    add_arrow(d, main + 70, 60, side - 60, 98, "F")
    for x, y in [(side, 296), (side, 161), (side, 46), (side, 98)]:
        add_arrow(d, x, y, main + 45, 18, dashed=True)
    return d


def availability_chart() -> Drawing:
    d = Drawing(480, 285)
    main, side = 190, 390
    nodes = {
        "N1": (main, 271, 105, 24, "N1  Entry", "oval", PALE_GREEN),
        "N2": (main, 235, 145, 28, "N2\nresponse record missing?", "diamond", PALE_GOLD),
        "N3": (side, 235, 135, 26, "N3  return\nNO_RESPONSE", "box", PALE_RED),
        "N4": (main, 190, 140, 28, "N4\nrecord withdrawn?", "diamond", PALE_GOLD),
        "N5": (side, 190, 135, 26, "N5  return\nWITHDRAWN", "box", PALE_RED),
        "N6": (main, 145, 140, 28, "N6\nany BUSY overlap?", "diamond", PALE_GOLD),
        "N7": (side, 145, 135, 26, "N7  return\nUNAVAILABLE", "box", PALE_RED),
        "N8": (main, 100, 155, 28, "N8\nslot fully inside AVAILABLE?", "diamond", PALE_GOLD),
        "N9": (side, 100, 135, 26, "N9  return\nAVAILABLE", "box", PALE_GREEN),
        "N10": (main, 55, 135, 28, "N10  return\nUNAVAILABLE", "box", PALE_RED),
        "N11": (main, 16, 90, 22, "N11  Exit", "oval", PALE_GREEN),
    }
    for values in nodes.values():
        add_node(d, *values)
    add_arrow(d, main, 259, main, 249)
    add_arrow(d, main + 72, 235, side - 68, 235, "T")
    add_arrow(d, main, 221, main, 204, "F")
    add_arrow(d, main + 70, 190, side - 68, 190, "T")
    add_arrow(d, main, 176, main, 159, "F")
    add_arrow(d, main + 70, 145, side - 68, 145, "T")
    add_arrow(d, main, 131, main, 114, "F")
    add_arrow(d, main + 77, 100, side - 68, 100, "T")
    add_arrow(d, main, 86, main, 69, "F")
    add_arrow(d, main, 41, main, 28)
    for x, y in [(side, 222), (side, 177), (side, 132), (side, 87)]:
        add_arrow(d, x, y, main + 45, 16, dashed=True)
    return d


def load_results() -> set[str]:
    root = ET.parse(JUNIT).getroot()
    failures = root.findall(".//failure")
    errors = root.findall(".//error")
    assert not failures and not errors, "JUnit evidence contains a failing or errored case"
    return {case.attrib["name"] for case in root.findall(".//testcase")}


black_cases = [
    ("BB-DUR-01", "FR-A1.1", "duration=14 min", "Reject below 15", "ValueError: duration must be 15 to 480 minutes (FR-A1.1)", "test_bb_dur_01_rejects_duration_14_below_minimum"),
    ("BB-DUR-02", "FR-A1.1", "duration=15 min", "Accept minimum", "RunStatus.OK; ranked options returned", "test_bb_dur_02_accepts_duration_15_at_minimum"),
    ("BB-DUR-03", "FR-A1.1", "duration=480 min", "Accept maximum", "RunStatus.OK; ranked options returned", "test_bb_dur_03_accepts_duration_480_at_maximum"),
    ("BB-DUR-04", "FR-A1.1", "duration=481 min", "Reject above 480", "ValueError: duration must be 15 to 480 minutes (FR-A1.1)", "test_bb_dur_04_rejects_duration_481_above_maximum"),
    ("BB-THR-01", "FR-D1 / UC-09", "2 overlap; threshold=2", "OK with two attendees", "RunStatus.OK; all ranked options have attendee_count=2", "test_bb_thr_01_returns_ok_when_threshold_is_met"),
    ("BB-THR-02", "UC-09 recovery", "best=2; requested=3", "Label best-available fallback", "BEST_AVAILABLE_BELOW_THRESHOLD; two-attendee options; warning names 3", "test_bb_thr_02_returns_best_available_when_requested_threshold_is_narrowly_missed"),
    ("BB-THR-03", "FR-D1 / UC-09", "no overlap of 2; threshold=2", "No eligible timeslot; no routing", "NO_TIMESLOT_MEETS_THRESHOLD; 0 combinations; 0 routing calls", "test_bb_thr_03_returns_no_timeslot_when_two_person_group_cannot_form"),
    ("BB-VEN-01", "FR-C3", "activity=badminton; venue=football", "No supporting venue", "NO_SUPPORTING_VENUES; no ranked options", "test_bb_ven_01_returns_no_supporting_venues_for_wrong_activity_partition"),
    ("BB-LOC-01", "FR-C4 / NFR-3", "all locations invalid/unavailable", "No centroid; no routing", "NO_VALID_LOCATIONS; no ranked options; 0 routing calls", "test_bb_loc_01_returns_no_valid_locations_when_centroid_cannot_be_computed"),
    ("BB-RTE-01", "NFR-3 / NFR-8", "provider UNAVAILABLE; minutes=None", "Keep data unavailable; never invent 0", "All combinations DATA_UNAVAILABLE; all minutes=None; no ranking", "test_bb_rte_01_marks_unavailable_provider_data_without_fabricating_a_journey"),
    ("BB-RTE-02", "NFR-3", "provider raises RuntimeError", "Contain error and continue safely", "All travel statuses ERROR; all combinations DATA_UNAVAILABLE", "test_bb_rte_02_contains_provider_exception_as_error_status"),
    ("BB-JRN-01", "FR-D3", "journey=60 min; cap=60", "Keep boundary value", "RunStatus.OK; ranked options; limit flags False", "test_bb_jrn_01_keeps_journey_at_60_minute_limit"),
    ("BB-JRN-02", "FR-D3", "journey=61 min; cap=60", "Exclude above cap", "No ranked options; every reason JOURNEY_LIMIT", "test_bb_jrn_02_excludes_journey_one_minute_above_limit"),
    ("BB-WGT-01", "FR-D9", "attendance weight=0%", "Accept minimum", "RunStatus.OK; reported weight=0; ranked options returned", "test_bb_wgt_01_accepts_zero_percent_attendance_weight"),
    ("BB-WGT-02", "FR-D9", "attendance weight=100%", "Accept maximum", "RunStatus.OK; reported weight=100; ranked options returned", "test_bb_wgt_02_accepts_100_percent_attendance_weight"),
    ("BB-WGT-03", "FR-D9", "attendance weight=-1%", "Reject below 0", "ValueError: attendance weight must be between 0 and 100", "test_bb_wgt_03_rejects_weight_minus_one_below_minimum"),
    ("BB-WGT-04", "FR-D9", "attendance weight=101%", "Reject above 100", "ValueError: attendance weight must be between 0 and 100", "test_bb_wgt_04_rejects_weight_101_above_maximum"),
]

pr_paths = [
    ("WB-PR-01", "N1-N2(T)-N3-N13", "count=2, threshold=3", "BELOW_THRESHOLD", "BELOW_THRESHOLD", "test_wb_pr_01_path_below_session_threshold"),
    ("WB-PR-02", "N1-N2(F)-N4(F)-N12-N13", "park; count=threshold=3", "None", "None", "test_wb_pr_02_path_non_sports_skips_sports_constraints"),
    ("WB-PR-03", "N1-N2(F)-N4(T)-N5(T)-N6(T)-N7-N13", "sports; count=3; venue min=4", "GROUP_SIZE", "GROUP_SIZE", "test_wb_pr_03_path_sports_group_size_failure"),
    ("WB-PR-04", "N1-N2(F)-N4(T)-N5(F)-N8(F)-N12-N13", "sports; no min; no lead", "None", "None", "test_wb_pr_04_path_sports_has_no_group_or_lead_constraint"),
    ("WB-PR-05", "N1-N2(F)-N4(T)-N5(T)-N6(F)-N8(F)-N12-N13", "sports; count=min=4; no lead", "None", "None", "test_wb_pr_05_path_sports_meets_group_size_without_lead_constraint"),
    ("WB-PR-06", "N1-N2(F)-N4(T)-N5(T)-N6(F)-N8(T)-N9-N10(T)-N11-N13", "24h lead; start only 23h away", "BOOKING_LEAD_TIME", "BOOKING_LEAD_TIME", "test_wb_pr_06_path_sports_booking_lead_failure"),
    ("WB-PR-07", "N1-N2(F)-N4(T)-N5(T)-N6(F)-N8(T)-N9-N10(F)-N12-N13", "24h lead; start exactly 24h away", "None", "None", "test_wb_pr_07_path_sports_exactly_meets_booking_lead_boundary"),
]

pa_paths = [
    ("WB-PA-01", "N1-N2(T)-N3-N11", "record_status=None", "NO_RESPONSE", "NO_RESPONSE", "test_wb_pa_01_path_no_response"),
    ("WB-PA-02", "N1-N2(F)-N4(T)-N5-N11", "record_status=WITHDRAWN", "WITHDRAWN", "WITHDRAWN", "test_wb_pa_02_path_withdrawn"),
    ("WB-PA-03", "N1-N2(F)-N4(F)-N6(T)-N7-N11", "available covers slot; BUSY overlaps", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_03_path_busy_overlap_overrides_available_time"),
    ("WB-PA-04", "N1-N2(F)-N4(F)-N6(F)-N8(T)-N9-N11", "slot fully inside AVAILABLE", "AVAILABLE", "AVAILABLE", "test_wb_pa_04_path_slot_is_fully_covered_by_available_time"),
    ("WB-PA-05", "N1-N2(F)-N4(F)-N6(F)-N8(F)-N10-N11", "AVAILABLE ends 1 min early", "UNAVAILABLE", "UNAVAILABLE", "test_wb_pa_05_path_partial_coverage_is_unavailable"),
]


def source_excerpt(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{number:>4}  {lines[number - 1]}" for number in range(start, end + 1))


def build_story():
    passed_names = load_results()
    expected_names = {row[-1] for row in black_cases + pr_paths + pa_paths}
    assert passed_names == expected_names, f"Case mismatch: missing={expected_names-passed_names}; extra={passed_names-expected_names}"
    assert 18 - 13 + 2 == 7
    assert 14 - 11 + 2 == 5

    story = []
    story += [Spacer(1, 22 * mm), p("SC2006 LAB 4", "Subtitle"), Spacer(1, 4 * mm)]
    story += [p("Software Testing Report", "ReportTitle")]
    story += [p("Black-box equivalence-class and boundary-value testing, plus white-box basis-path testing", "Subtitle")]
    story += [Spacer(1, 10 * mm), HRFlowable(width="45%", thickness=3, color=GOLD, hAlign="LEFT"), Spacer(1, 10 * mm)]
    cover_data = [
        ["Work product", "Test Cases and Testing Results"],
        ["Prepared by", "Group 1 - Software Testing"],
        ["System", "Group Scheduling Application"],
        ["Target code", "feature/production-pilot tree at 26cb622"],
        ["Execution date", "7 November 2026 (Asia/Singapore)"],
        ["Result", "29/29 assessment tests passed"],
    ]
    cover = Table([[p(a, "Small"), p(b, "Small")] for a, b in cover_data], colWidths=[36 * mm, 105 * mm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), PALE_GREEN),
        ("TEXTCOLOR", (0, 0), (0, -1), GREEN),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [cover, Spacer(1, 14 * mm), p("Submission scope", "Subsection")]
    story += [p("This report satisfies Lab 4 Manual sections 3.2.1-3.2.4. It tests one important control boundary using equivalence classes and boundary values, tests two complex methods using basis paths, minimises redundant inputs, and records input, expected output, actual output, and pass/fail results.")]
    story += [PageBreak()]

    story += section("Executive Summary", "1")
    story += [p("Black-box testing treats the recommendation control boundary as a sealed unit: tests provide complete recommendation requests and inspect only public results or validation errors. White-box testing reads the method structure, draws its control-flow graph, calculates cyclomatic complexity, and executes a basis set of independent paths.")]
    story += [p("All 29 assessment-focused automated tests passed. The complete backend regression suite passed 293 tests; all 21 frontend tests, lint, and the production build also passed. No production behaviour was changed for this work product.", "Callout")]
    story += [p("Selected test subjects", "Subsection")]
    subject_data = [
        ["Technique", "Selected unit", "Reason for selection"],
        ["Black-box", "RecommendationEngine.generate()", "Core UC-09/UC-10 control boundary; validates the request and coordinates timeslots, venues, routing, feasibility, scoring, and ranking."],
        ["White-box 1", "pre_routing_exclusion()", "Implements FR-D1, FR-D4, and FR-D5 with ordered feasibility decisions before external routing."],
        ["White-box 2", "_ParticipantAvailability.status_for()", "Implements four distinct attendance states and the BUSY-overrides-AVAILABLE rule."],
    ]
    story += [table(subject_data, [24 * mm, 59 * mm, 90 * mm], font_size=7.4, leading=9.5), Spacer(1, 4 * mm)]
    story += [p("Environment and evidence", "Subsection")]
    env_data = [
        ["Item", "Value"],
        ["Language/runtime", "Python 3.13.5"],
        ["Test framework", "pytest 8.3.5"],
        ["Assessment run", "29 passed, 0 failed, 0 errors"],
        ["Full backend regression", "293 passed; one dependency deprecation warning"],
        ["Frontend verification", "21 tests passed; lint passed; production build passed"],
        ["External routing", "Deterministic test double at provider port; all application logic remains real"],
    ]
    story += [table(env_data, [44 * mm, 129 * mm], font_size=7.4, leading=9.5), PageBreak()]

    story += section("Black-box Test Design", "2")
    story += [p("The control boundary is tested without using its internal branch structure. Inputs were partitioned by externally observable behaviour. Boundary values use the nearest invalid value and each valid endpoint where numeric limits exist.")]
    story += [p("2.1 Equivalence classes", "Subsection")]
    eq_data = [
        ["Input characteristic", "Equivalence classes", "Representative cases"],
        ["Session duration", "Invalid low: <15; valid: 15-480; invalid high: >480", "BB-DUR-01..04"],
        ["Attendance outcome", "Threshold met; requested threshold missed but best>=2; no two-person group", "BB-THR-01..03"],
        ["Venue compatibility", "At least one supporting venue; no supporting venue", "BB-THR-01, BB-VEN-01"],
        ["Participant locations", "At least one active valid origin; no valid origin", "BB-THR-01, BB-LOC-01"],
        ["Routing provider", "Available duration; explicitly unavailable; exception/error", "BB-JRN-01, BB-RTE-01..02"],
        ["Individual journey", "At or below 60-minute cap; above cap", "BB-JRN-01..02"],
        ["Attendance weight", "Invalid low: <0; valid: 0-100; invalid high: >100", "BB-WGT-01..04"],
    ]
    story += [table(eq_data, [42 * mm, 88 * mm, 43 * mm], font_size=7.2, leading=9.2)]
    story += [p("2.2 Boundary-value analysis", "Subsection")]
    bva_data = [
        ["Boundary", "Values selected", "Expected behaviour", "Cases"],
        ["Duration minimum 15", "14, 15", "14 rejected; 15 accepted", "BB-DUR-01..02"],
        ["Duration maximum 480", "480, 481", "480 accepted; 481 rejected", "BB-DUR-03..04"],
        ["Weight minimum 0", "-1, 0", "-1 rejected; 0 accepted", "BB-WGT-03, BB-WGT-01"],
        ["Weight maximum 100", "100, 101", "100 accepted; 101 rejected", "BB-WGT-02, BB-WGT-04"],
        ["Journey cap 60", "60, 61", "60 retained; 61 excluded", "BB-JRN-01..02"],
    ]
    story += [table(bva_data, [43 * mm, 34 * mm, 62 * mm, 34 * mm], font_size=7.2, leading=9.2)]
    story += [p("2.3 Minimisation rationale", "Subsection")]
    story += [p("The test set uses one representative for each non-boundary partition and the adjacent values around every numeric boundary. Cases deliberately cover several compatible conditions at once. For example, BB-THR-01 also supplies a valid venue, valid locations, successful routing, and a valid mid-range weight. Additional combinations that would repeat the same observable class were omitted.")]
    story += [PageBreak()]

    story += section("Black-box Test Cases and Results", "3")
    black_table = [["Case", "Req.", "Test input / precondition", "Expected output", "Actual output", "Result"]]
    black_table += [[row[0], row[1], row[2], row[3], row[4], "PASS"] for row in black_cases]
    story += [table(black_table, [20 * mm, 20 * mm, 42 * mm, 36 * mm, 48 * mm, 14 * mm], font_size=6.15, leading=7.7)]
    story += [Spacer(1, 5 * mm), p("Evidence: every row above corresponds to one passing pytest function with the same case ID. The JUnit result contained 17 black-box cases, 0 failures, and 0 errors.", "Callout"), Spacer(1, 3 * mm)]
    story += [KeepTogether(section("White-box Method 1: Pre-routing Exclusion", "4") + [p("This method applies feasibility rules in priority order before any routing request: the session threshold (FR-D1), sports-facility minimum group size (FR-D4), and sports-facility booking lead time (FR-D5). The compound minimum-group expression is split into two short-circuit decisions in the control-flow graph.")]), PageBreak()]

    story += [p("4.1 Source excerpt", "Subsection")]
    story += [Preformatted(source_excerpt(ROOT / "backend/app/recommender/feasibility.py", 20, 44), styles["CodeBlock"])]
    story += [p("4.2 Control-flow graph", "Subsection"), pre_routing_chart()]
    story += [p("Figure 1. Control-flow graph for pre_routing_exclusion(). Node numbering is identical to the DOT source committed with the tests.", "Small"), PageBreak()]
    story += [p("4.3 Cyclomatic complexity", "Subsection")]
    complexity1 = [
        ["Calculation", "Value"],
        ["Predicate method", "6 decision nodes + 1 = 7"],
        ["Graph method", "E - N + 2 = 18 - 13 + 2 = 7"],
        ["Required independent paths", "7"],
    ]
    story += [table(complexity1, [55 * mm, 118 * mm], font_size=8, leading=10)]
    story += [p("4.4 Independent paths and executed results", "Subsection")]
    pr_table = [["Case", "Independent node path", "Input", "Expected", "Actual", "Result"]]
    pr_table += [[r[0], r[1], r[2], r[3], r[4], "PASS"] for r in pr_paths]
    story += [table(pr_table, [19 * mm, 58 * mm, 42 * mm, 25 * mm, 25 * mm, 14 * mm], font_size=6.9, leading=8.7)]
    story += [Spacer(1, 5 * mm)]

    story += section("White-box Method 2: Participant Attendance Status", "5")
    story += [p("This method preserves four distinct participant states. A missing response and a withdrawn response are returned before interval processing. For an active response, any BUSY overlap overrides AVAILABLE time; otherwise the slot must be fully contained in an AVAILABLE block.")]
    story += [p("5.1 Source excerpt", "Subsection")]
    story += [Preformatted(source_excerpt(ROOT / "backend/app/recommender/candidate_generation.py", 111, 124), styles["CodeBlock"])]
    story += [KeepTogether([
        p("5.2 Control-flow graph", "Subsection"),
        availability_chart(),
        p("Figure 2. Application-level CFG for _ParticipantAvailability.status_for(). Each any(...) result is one boolean decision; Python iterator internals are outside this graph's abstraction boundary.", "Small"),
    ])]
    story += [p("5.3 Cyclomatic complexity", "Subsection")]
    complexity2 = [
        ["Calculation", "Value"],
        ["Predicate method", "4 decision nodes + 1 = 5"],
        ["Graph method", "E - N + 2 = 14 - 11 + 2 = 5"],
        ["Required independent paths", "5"],
    ]
    story += [table(complexity2, [55 * mm, 118 * mm], font_size=8, leading=10)]
    story += [p("5.4 Independent paths and executed results", "Subsection")]
    pa_table = [["Case", "Independent node path", "Input", "Expected", "Actual", "Result"]]
    pa_table += [[r[0], r[1], r[2], r[3], r[4], "PASS"] for r in pa_paths]
    story += [table(pa_table, [19 * mm, 55 * mm, 48 * mm, 23 * mm, 23 * mm, 14 * mm], font_size=6.9, leading=8.7)]
    story += [PageBreak()]

    result_data = [
        ["Verification", "Observed result", "Status"],
        ["Lab 4 black-box tests", "17 passed, 0 failed, 0 errors", "PASS"],
        ["Lab 4 white-box tests", "12 passed, 0 failed, 0 errors", "PASS"],
        ["Combined Lab 4 JUnit run", "29 passed, 0 failed, 0 errors", "PASS"],
        ["Full backend regression", "293 passed; 1 third-party deprecation warning", "PASS"],
        ["Frontend unit/UI tests", "21 passed", "PASS"],
        ["Frontend lint", "oxlint exit code 0", "PASS"],
        ["Frontend production build", "152 modules transformed; build exit code 0", "PASS"],
    ]
    story += [KeepTogether(section("Execution Evidence and Cross-check", "6") + [table(result_data, [58 * mm, 89 * mm, 26 * mm], font_size=7.7, leading=9.8)])]
    compliance = [
        ["Manual requirement", "Evidence in this report", "Status"],
        ["3.2.1: one important control class", "RecommendationEngine.generate(); Sections 2-3", "Met"],
        ["3.2.1: equivalence classes", "Section 2.1 and BB test rows", "Met"],
        ["3.2.1: boundary values", "Section 2.2; 14/15, 480/481, -1/0, 100/101, 60/61", "Met"],
        ["3.2.2: two complex methods", "Sections 4 and 5", "Met"],
        ["3.2.2: basis-path testing", "Two CFGs, two complexity calculations, 12 path cases", "Met"],
        ["3.2.3: minimise cases", "One representative per partition plus boundary neighbours; Section 2.3", "Met"],
        ["3.2.4: execute and document", "Every row has input, expected, actual, and result; Section 6", "Met"],
    ]
    story += [KeepTogether([p("6.1 Manual compliance matrix", "Subsection"), table(compliance, [51 * mm, 96 * mm, 26 * mm], font_size=7.3, leading=9.4)])]
    story += [p("6.2 Consistency checks", "Subsection")]
    checks = [
        "All 29 report case IDs exactly match the 29 JUnit test names.",
        "Every equivalence class and boundary in Section 2 maps to at least one executed case.",
        "The first CFG has N=13 and E=18; both formulas give V(G)=7; seven independent paths were executed.",
        "The second CFG has N=11 and E=14; both formulas give V(G)=5; five independent paths were executed.",
        "Actual outputs are literal observations asserted by the final passing tests, not restatements of expected output.",
        "No secrets, access tokens, credentials, or personal availability data appear in this report.",
    ]
    story += [Table([[p(f"{i + 1}.", "Small"), p(item, "Small")] for i, item in enumerate(checks)], colWidths=[8 * mm, 165 * mm], style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 3)])), Spacer(1, 3 * mm)]

    story += section("Limitations and Conclusion", "7")
    story += [p("7.1 Limitations", "Subsection")]
    story += [p("The black-box control tests use a deterministic router at the external provider port so that boundary outcomes are reproducible and do not depend on OneMap availability. This is appropriate for unit-level control-class testing but does not replace the separate deployed smoke test of Google authentication, OneMap, PostgreSQL, and Render. The report also uses an application-level CFG: the internal iteration performed by Python's any(...) is treated as part of expression evaluation rather than as a separate business-logic decision.")]
    story += [p("7.2 Conclusion", "Subsection")]
    story += [p("The selected tests provide systematic evidence for the recommendation control logic and two complex decision methods. Equivalence partitioning, boundary-value analysis, and basis-path testing were applied consistently; redundant combinations were avoided; all expected and actual results are traceable to automated test IDs; and the full regression checks found no introduced failures.", "Callout")]
    story += [p("<b>Reference.</b> SC2006 Lab 4 Manual: Implementation, Testing, and Preparation for Demo, sections 3.2.1-3.2.4. Source code and automated tests are available on branch lab4/software-testing-report.", "Small")]
    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = ReportDocTemplate(str(OUTPUT))
    doc.build(build_story(), canvasmaker=InvariantCanvas)
    reader = PdfReader(str(OUTPUT))
    assert 8 <= len(reader.pages) <= 10, f"Compact report must be 8-10 pages, got {len(reader.pages)}"
    report_ids = {row[0] for row in black_cases + pr_paths + pa_paths}
    assert len(report_ids) == 29, f"Expected 29 unique report IDs, got {len(report_ids)}"
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    for token in [
        "29/29 assessment tests passed",
        "BB-DUR-01",
        "WB-PR-07",
        "WB-PA-05",
        "E - N + 2 = 18 - 13 + 2 = 7",
        "E - N + 2 = 14 - 11 + 2 = 5",
        "3.2.1",
        "3.2.2",
        "3.2.3",
        "3.2.4: execute and document",
    ]:
        assert token in extracted, f"Missing required report text: {token}"
    print(f"created {OUTPUT} ({len(reader.pages)} pages)")


if __name__ == "__main__":
    main()
