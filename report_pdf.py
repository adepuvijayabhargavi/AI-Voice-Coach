"""Professional PDF report generation (ReportLab) for completed AI Voice Coach
sessions. Pure data-driven: every value rendered comes from the interview row
fetched by the route (no placeholder or hardcoded report data is used)."""

import io
import os
from datetime import datetime

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PRIMARY = colors.HexColor("#2563eb")
DARK = colors.HexColor("#1e3a8a")
LIGHT_FILL = colors.HexColor("#f3f4f6")
BAND_FILL = colors.HexColor("#e8eefc")
BORDER = colors.HexColor("#d1d5db")
TEXT = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
WHITE = colors.white

# Unicode-capable TTF fonts so long answers, quotes and dashes render cleanly.
# Falls back to Helvetica (Latin-1) on systems without these fonts.
_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeib.ttf"),
    ("C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
]

_FONTS = {"normal": None, "bold": None}


def _register_fonts():
    for normal_path, bold_path in _FONT_CANDIDATES:
        if os.path.exists(normal_path):
            pdfmetrics.registerFont(TTFont("AppFont", normal_path))
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("AppFont-Bold", bold_path))
                return "AppFont", "AppFont-Bold"
            return "AppFont", "AppFont"
    return "Helvetica", "Helvetica-Bold"


def _get_fonts():
    if _FONTS["normal"] is None:
        _FONTS["normal"], _FONTS["bold"] = _register_fonts()
    return _FONTS["normal"], _FONTS["bold"]


def _build_styles(normal, bold):
    return {
        "title": ParagraphStyle("title", fontName=normal, fontSize=25, leading=30,
                                textColor=DARK, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", fontName=normal, fontSize=12.5, leading=16,
                                   textColor=MUTED, spaceAfter=6),
        "brand": ParagraphStyle("brand", fontName=bold, fontSize=9, leading=12,
                                textColor=MUTED, spaceAfter=0),
        "section_title": ParagraphStyle("section_title", fontName=bold, fontSize=12.5,
                                        leading=16, textColor=WHITE),
        "label": ParagraphStyle("label", fontName=bold, fontSize=10, leading=14,
                                textColor=TEXT),
        "value": ParagraphStyle("value", fontName=normal, fontSize=10, leading=15,
                                textColor=TEXT),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=11.5, leading=15,
                             textColor=PRIMARY, spaceBefore=4, spaceAfter=3),
        "body": ParagraphStyle("body", fontName=normal, fontSize=10, leading=14.5,
                               textColor=TEXT, spaceAfter=3),
        "smallmuted": ParagraphStyle("smallmuted", fontName=normal, fontSize=8.5,
                                     leading=11, textColor=MUTED),
        "bullet": ParagraphStyle("bullet", fontName=normal, fontSize=10, leading=14,
                                 textColor=TEXT, leftIndent=14, bulletIndent=2,
                                 bulletFontName=normal, spaceAfter=2),
        "bigscore": ParagraphStyle("bigscore", fontName=bold, fontSize=20, leading=24,
                                   textColor=DARK),
        "table_head": ParagraphStyle("table_head", fontName=bold, fontSize=10.5,
                                     leading=13, textColor=WHITE),
    }


def _P(text, style):
    return Paragraph(escape("" if text is None else str(text)), style)


def _title(value, fallback):
    if not value or not str(value).strip():
        return fallback
    return str(value).replace("_", " ").title()


def _fmt_date(value, fallback):
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y at %H:%M")
    if value:
        return str(value)
    return fallback


CATEGORY_ROWS = [
    ("Communication", "communication"),
    ("Confidence", "confidence"),
    ("Clarity", "clarity"),
    ("Grammar", "grammar"),
    ("Answer Structure", "structure"),
    ("Technical Knowledge", "relevance"),
]


def _skill_summary(interview):
    scored = [(label, interview.get(key)) for label, key in CATEGORY_ROWS
              if interview.get(key) is not None]
    if not scored:
        return (None, None), (None, None)
    return max(scored, key=lambda kv: kv[1]), min(scored, key=lambda kv: kv[1])


def _personalized_suggestions(interview, strongest, weakest):
    suggestions = []
    weak_label, weak_score = weakest
    strong_label, strong_score = strongest
    if weak_label and weak_score is not None:
        suggestions.append(
            "Your weakest skill is %s (%d/100). Prioritize practice questions that "
            "target %s to lift your overall performance." % (weak_label, weak_score, weak_label.lower())
        )
    if strong_label and strong_score is not None:
        suggestions.append(
            "Your strongest skill is %s (%d/100). Apply the techniques you use there to "
            "your weaker categories." % (strong_label, strong_score)
        )
    if interview.get("improvements"):
        suggestions.append(
            "Work through the 'Areas for Improvement' listed below, then retake a similar "
            "session to measure your progress."
        )
    if not suggestions:
        suggestions.append(
            "No category scores are available yet. Complete a practice or mock interview "
            "session to receive personalized suggestions."
        )
    return suggestions


class _NumberedCanvas(canvas.Canvas):
    """Canvas that knows the final page count so the footer can print
    'Page X of Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        self.saveState()
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.5)
        self.line(1.8 * cm, 1.15 * cm, A4[0] - 1.8 * cm, 1.15 * cm)
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED)
        self.drawCentredString(A4[0] / 2.0, 0.78 * cm,
                               "AI Voice Coach - Page %d of %d" % (self._pageNumber, total))
        self.restoreState()


def _draw_header(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(MUTED)
    canvas_obj.drawString(doc.leftMargin, A4[1] - 0.85 * cm, "AI Voice Coach")
    canvas_obj.drawRightString(A4[0] - doc.rightMargin, A4[1] - 0.85 * cm,
                               "Practice Performance Report")
    canvas_obj.setStrokeColor(BORDER)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(doc.leftMargin, A4[1] - 1.05 * cm,
                    A4[0] - doc.rightMargin, A4[1] - 1.05 * cm)
    canvas_obj.restoreState()
    return ""


def _section_header(doc, text, styles):
    header = Table(
        [[Paragraph(escape(text), styles["section_title"])]],
        colWidths=[doc.width],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return header


def _info_table(doc, rows, styles):
    table_data = [[_P(label, styles["label"]), _P(value, styles["value"])] for label, value in rows]
    table = Table(table_data, colWidths=[4.8 * cm, doc.width - 4.8 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_FILL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _category_table(doc, interview, styles):
    data = [[_P("Category", styles["table_head"]),
             _P("Score / 100", styles["table_head"]),
             _P("Percentage", styles["table_head"])]]
    for label, key in CATEGORY_ROWS:
        score = interview.get(key)
        if score is None:
            data.append([_P(label, styles["value"]),
                         _P("--", styles["value"]),
                         _P("--", styles["value"])])
        else:
            data.append([_P(label, styles["value"]),
                         _P(str(score), styles["value"]),
                         _P(str(score) + "%", styles["value"])])
    table = Table(data, colWidths=[8 * cm, 4.5 * cm, 4.5 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BAND_FILL]),
    ]))
    return table


def _question_block(index, item, styles):
    block = []
    category = (item.get("category") or "").strip()
    heading = "Question " + str(index)
    if category and category != "General":
        heading += "  [" + category + "]"
    block.append(Paragraph(escape(heading), styles["h3"]))
    block.append(_P(item.get("question") or "No question recorded.", styles["body"]))
    block.append(_P("Your Answer", styles["label"]))
    block.append(_P(item.get("answer") or "No answer recorded.", styles["body"]))
    score = item.get("score")
    if score is None:
        block.append(_P("Score: Not scored", styles["label"]))
    else:
        block.append(_P("Score: %s / 100 (%s%%)" % (score, score), styles["label"]))
    block.append(_P("AI Feedback", styles["label"]))
    block.append(_P(item.get("feedback") or "No AI feedback recorded.", styles["body"]))
    block.append(_P("Improved Answer", styles["label"]))
    block.append(_P(item.get("better_answer") or "No improved answer provided.", styles["body"]))
    return block


def _build_story(interview, user, styles, doc):
    story = []

    # ---- Title / header -----------------------------------------------------
    story.append(_P("AI Voice Coach", styles["title"]))
    story.append(_P("Practice Performance Report", styles["subtitle"]))
    story.append(_P("Prepared for: " + (user.get("full_name") or "User"), styles["body"]))
    story.append(_P("Generated on " + datetime.now().strftime("%d %b %Y at %H:%M"), styles["smallmuted"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.2, color=PRIMARY, spaceAfter=12))

    # ---- Session information ------------------------------------------------
    story.append(_section_header(doc, "Session Information", styles))
    story.append(Spacer(1, 8))
    session_rows = [
        ("Interview Type", _title(interview.get("interview_type"), "Practice")),
        ("Target Role", _title(interview.get("role"), "General")),
        ("Experience Level", _title(interview.get("experience"), "Not specified")),
        ("Difficulty", _title(interview.get("difficulty"), "Not specified")),
        ("Session Date", _fmt_date(interview.get("created_at"), "Not specified")),
        ("Number of Questions", str(interview.get("questions_count") or 0)),
    ]
    story.append(_info_table(doc, session_rows, styles))
    story.append(Spacer(1, 14))

    # ---- Performance summary ------------------------------------------------
    story.append(_section_header(doc, "Performance Summary", styles))
    story.append(Spacer(1, 8))

    overall = interview.get("overall_score")
    if overall is None:
        overall_display = "N/A"
    else:
        overall_display = "%d / 100  (%d%%)" % (overall, overall)
    story.append(Table(
        [[_P("Overall Score", styles["label"]), _P(overall_display, styles["bigscore"])]],
        colWidths=[3.6 * cm, 8 * cm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]),
    ))
    story.append(Spacer(1, 8))
    story.append(_category_table(doc, interview, styles))
    story.append(Spacer(1, 8))

    strongest, weakest = _skill_summary(interview)
    if strongest[0] and weakest[0]:
        story.append(_P(
            "Strongest Skill: %s (%s/100)" % (strongest[0], strongest[1]),
            styles["body"]))
        story.append(_P(
            "Weakest Skill: %s (%s/100)" % (weakest[0], weakest[1]),
            styles["body"]))
    else:
        story.append(_P("Strongest / weakest skill: Not available yet.", styles["body"]))
    story.append(Spacer(1, 14))

    # ---- Detailed question analysis -----------------------------------------
    story.append(_section_header(doc, "Detailed Question Analysis", styles))
    story.append(Spacer(1, 8))

    details = interview.get("details") or []
    if not details:
        story.append(_P("No per-question details were recorded for this session.",
                        styles["body"]))
    for i, item in enumerate(details):
        if not isinstance(item, dict):
            continue
        story.extend(_question_block(i + 1, item, styles))
        if i < len(details) - 1:
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER,
                                    spaceBefore=2, spaceAfter=8))
    story.append(Spacer(1, 14))

    # ---- Final summary ------------------------------------------------------
    story.append(_section_header(doc, "Final Summary", styles))
    story.append(Spacer(1, 8))

    story.append(_P("Strengths", styles["h3"]))
    strengths = interview.get("strengths") or []
    if strengths:
        for s in strengths:
            story.append(Paragraph(escape(str(s)), styles["bullet"], bulletText="\u2022  "))
    else:
        story.append(_P("No strengths were recorded for this session.", styles["body"]))

    story.append(_P("Areas for Improvement", styles["h3"]))
    improvements = interview.get("improvements") or []
    if improvements:
        for s in improvements:
            story.append(Paragraph(escape(str(s)), styles["bullet"], bulletText="\u2022  "))
    else:
        story.append(_P("No improvement areas were recorded for this session.", styles["body"]))

    story.append(_P("Overall AI Feedback", styles["h3"]))
    story.append(_P(interview.get("overall_feedback") or "No overall AI feedback was recorded.",
                    styles["body"]))

    story.append(_P("Personalized Improvement Suggestions", styles["h3"]))
    for suggestion in _personalized_suggestions(interview, strongest, weakest):
        story.append(Paragraph(escape(suggestion), styles["bullet"], bulletText="\u2022  "))

    return story


def generate_interview_pdf(interview, user):
    """Build a professional PDF report from one interview row and its owner.

    Returns a BytesIO buffer positioned at the start of the PDF data.
    Raises on any generation failure so the route can handle the error.
    """
    normal, bold = _get_fonts()
    styles = _build_styles(normal, bold)

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title="AI Voice Coach - Practice Performance Report",
        author="AI Voice Coach",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([
        PageTemplate(id="page", frames=[frame], onPage=_draw_header),
    ])

    story = _build_story(interview, user, styles, doc)
    doc.build(story, canvasmaker=_NumberedCanvas)
    buffer.seek(0)
    return buffer