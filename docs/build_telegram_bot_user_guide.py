"""Generate a reviewer-facing Telegram bot user guide PDF."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "telegram_bot_user_guide.pdf"


def main() -> None:
    s = styles()
    story = [
        Paragraph("Telegram QA Bot User Guide", s["title"]),
        Paragraph(
            "Bot URL: <b>@QA_TOTO_bot</b><br/>"
            "Reviewer user login code: <b>qa-user-2026</b>",
            s["callout"],
        ),
        Paragraph(
            "This bot is a ChatOps interface for the Digitain AI QA Agent. It lets a reviewer "
            "run the same Excel-driven QA automation from Telegram, watch status, and receive "
            "HTML/JSON reports after the run.",
            s["body"],
        ),
        Paragraph("Safety Rule", s["h1"]),
        Paragraph(
            "Telegram-triggered runs are always dry-run safe. The bot does not expose "
            "real-money deposit, withdrawal, or final bet-submit actions. This matters because "
            "TotoGaming.ro is a regulated real-money gambling platform.",
            s["body"],
        ),
        Paragraph("How To Join As A Reviewer", s["h1"]),
        table(
            [
                ["Step", "Action", "Expected result"],
                ["1", "Open Telegram and search for @QA_TOTO_bot.", "The bot chat opens."],
                ["2", "Send /start.", "If not authorized yet, the bot shows access guidance and your Telegram numeric ID."],
                ["3", "Send /login qa-user-2026.", "You are added as a regular user, up to the configured two-user limit."],
                ["4", "Send /menu.", "The main menu opens with Run Tests, Reports, Status and Help."],
            ],
            s,
            [17 * mm, 68 * mm, 88 * mm],
        ),
        Paragraph("Recommended Review Flow", s["h1"]),
        table(
            [
                ["Command", "Purpose", "Why use it"],
                ["/whoami", "Shows your Telegram ID and role.", "Confirms access is configured correctly."],
                ["/run_id simple-1", "Runs one fast invalid-login test.", "Best first smoke check."],
                ["/status", "Shows the active job and latest output.", "Useful during longer browser runs."],
                ["/reports", "Sends the latest HTML and JSON reports.", "Lets the reviewer inspect evidence."],
                ["/run_simple", "Runs the simple test suite.", "Good demo of safe production checks and blocked-precondition reasoning."],
                ["/run_complex", "Runs the complex suite.", "Good demo of sportsbook, casino, provider, and staging-boundary logic."],
            ],
            s,
            [34 * mm, 65 * mm, 74 * mm],
        ),
        Paragraph("Button Hierarchy", s["h1"]),
        table(
            [
                ["Menu area", "What it contains"],
                ["Run Tests", "Run All, Run Simple, Run Complex, By Category, Specific ID."],
                ["Reports", "Latest report and report list."],
                ["Status", "Current job status plus recent CLI output."],
                ["Help", "Command reference and safety note."],
            ],
            s,
            [36 * mm, 137 * mm],
        ),
        Paragraph("Business Value", s["h1"]),
        Paragraph(
            "The bot makes the QA system usable by non-developers while preserving governance. "
            "A QA lead can trigger a suite from Telegram, receive the report, and see which "
            "cases passed, which are blocked, and exactly what staging data is needed for full "
            "completion. That is the difference between a script and an operational QA tool.",
            s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "Note: the shared reviewer code is a regular user code, not an admin code. "
            "It can be rotated after evaluation.",
            s["small"],
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Telegram QA Bot User Guide",
        author="Vatche",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {OUTPUT}")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=12.6,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#eef2ff"),
            borderColor=colors.HexColor("#6366f1"),
            borderWidth=0.7,
            borderPadding=8,
            spaceAfter=10,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=9.6,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.7,
            leading=9.5,
            textColor=colors.HexColor("#1f2937"),
        ),
    }


def table(rows: list[list[str]], s: dict[str, ParagraphStyle], widths: list[float]) -> Table:
    data = []
    for ridx, row in enumerate(rows):
        style = s["table_header"] if ridx == 0 else s["table_cell"]
        data.append([Paragraph(cell, style) for cell in row])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(16 * mm, 8 * mm, "Digitain AI QA Agent - Telegram Bot User Guide")
    canvas.drawRightString(194 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    main()
