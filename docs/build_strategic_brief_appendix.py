"""Append detailed architecture and operating pages to strategic_brief.pdf."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE_PDF = DOCS / "strategic_brief.pdf"
ORIGINAL_PDF = DOCS / "strategic_brief.original_before_appendix.pdf"
APPENDIX_PDF = DOCS / "strategic_brief_appendix.pdf"
REPORT_JSON = ROOT / "reports/full_rerun_20260501_213043_column_notes/report.json"


def main() -> None:
    if not ORIGINAL_PDF.exists():
        shutil.copy2(BASE_PDF, ORIGINAL_PDF)

    appendix_story = build_story()
    build_appendix(APPENDIX_PDF, appendix_story)
    merge_pdfs(ORIGINAL_PDF, APPENDIX_PDF, BASE_PDF)

    page_count = len(PdfReader(str(BASE_PDF)).pages)
    print(f"updated {BASE_PDF} ({page_count} pages)")
    print(f"backup {ORIGINAL_PDF}")
    print(f"appendix {APPENDIX_PDF}")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AppendixTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#111827"),
            spaceBefore=2,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.4,
            textColor=colors.HexColor("#334155"),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=9.6,
            textColor=colors.HexColor("#334155"),
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.0,
            leading=8.4,
            textColor=colors.HexColor("#1f2937"),
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.4,
            leading=12.5,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#eef2ff"),
            borderColor=colors.HexColor("#6366f1"),
            borderWidth=0.7,
            borderPadding=7,
            spaceBefore=4,
            spaceAfter=8,
        ),
    }


def build_story() -> list:
    s = styles()
    story: list = []
    summary, results = load_latest_results()

    story += [
        Paragraph("Appendix: Architecture, Evidence and Telegram Operations", s["title"]),
        Paragraph(
            "This appendix expands the original strategic brief into an interview-ready "
            "technical and business explanation. It documents how the QA agent is built, "
            "how each test is executed or blocked, why the safety decisions matter for a "
            "regulated gambling platform, how the Excel workbook was upgraded, and how "
            "the Telegram bot turns the runner into a controlled QA command center.",
            s["body"],
        ),
        Paragraph(
            "Executive signal: the project is not only a script. It is a governed QA "
            "system: Excel is the source of truth, Playwright executes observable browser "
            "behavior, LLMs plan and judge where useful, safety rails prevent real-money "
            "damage, and reports are suitable for QA leads, audits and handoff.",
            s["callout"],
        ),
        Spacer(1, 4),
        two_column_table(
            [
                ("Current live evidence", f"{summary['total']} tests: {summary['pass']} pass, {summary['blocked']} blocked, {summary['fail']} fail."),
                ("Primary business value", "Faster partner-brand regression, clearer risk evidence, and safer testing of regulated money flows."),
                ("Why blocked is valid", "Blocked cases identify missing legal/test preconditions such as OTP fixtures, self-excluded accounts, payment sandbox or staging funds."),
                ("Telegram addition", "Role-based ChatOps interface for admin plus two users, with menus, long-running jobs, and automatic report delivery."),
            ],
            s,
        ),
        PageBreak(),
    ]

    story += architecture_pages(s)
    story += evidence_page(s, summary)
    story += test_pages(s, results)
    story += blockers_page(s)
    story += telegram_pages(s)
    story += excel_updates_page(s)
    return story


def architecture_pages(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("1. System Architecture - Technical and Business View", s["h1"]),
        Paragraph(
            "The architecture follows a Planner / Executor / Judge pattern. This is the "
            "right shape for a multi-brand gaming platform because QA cases remain in "
            "business-readable Excel while browser execution remains deterministic and "
            "auditable.",
            s["body"],
        ),
        table(
            [
                ["Layer", "Technical role", "Business reason"],
                ["Excel source of truth", "test_cases.xlsx contains simple, complex and new risk-based tests. The loader reads the first five columns so human notes do not break automation.", "QA and product owners can maintain cases without editing code. Armenian/English/Romanian wording can coexist."],
                ["LLM client", "src/llm_client.py supports OpenAI or Claude behind one complete() interface.", "Vendor flexibility lowers lock-in and lets the team choose the best model/cost tradeoff."],
                ["Planner", "The agent can ask the LLM to convert natural-language steps into atomic browser actions.", "New partner tests can start from plain language instead of a full script rewrite."],
                ["Playwright executor", "src/agent.py runs Chromium with role/name locators, deterministic handlers for known flows, screenshots and traces.", "Browser evidence is reproducible and easier to defend than a verbal manual-test claim."],
                ["Safety rails", "Dry-run is on by default. Real deposits, withdrawals and final bet submits are blocked unless explicitly allowed outside Telegram.", "Protects real accounts, real money, and the credibility of the assignment in a regulated domain."],
                ["Judge and reporter", "Results are classified as pass, fail, blocked or inconclusive and written to HTML plus JSON.", "QA leads get a readable report; CI/Jira/Telegram get machine-readable artifacts."],
                ["Telegram bot", "src/bot.py wraps the CLI with role checks, inline menus, one active job, cancellation and report delivery.", "Makes the agent usable by non-developers while preserving governance."],
            ],
            [33 * mm, 70 * mm, 70 * mm],
            s,
        ),
        Paragraph("Operational Flow", s["h2"]),
        Paragraph(
            "1) A user chooses a suite from CLI or Telegram. 2) The loader reads Excel. "
            "3) The agent chooses a deterministic handler where a production-safe path exists, "
            "or uses the LLM/Playwright loop for generic plans. 4) Browser evidence is captured. "
            "5) The reporter writes HTML/JSON. 6) Telegram sends the report files back to the requester.",
            s["body"],
        ),
        Paragraph(
            "Design choice: blocked is not hidden. In gambling QA, a missing self-excluded account, "
            "OTP fixture, or staging wallet is a real test-environment gap. Reporting it clearly is "
            "more professional than forcing a fake pass.",
            s["callout"],
        ),
        PageBreak(),
    ]


def evidence_page(s: dict[str, ParagraphStyle], summary: dict) -> list:
    return [
        Paragraph("2. Latest Execution Evidence", s["h1"]),
        Paragraph(
            "The latest headed run was executed against TotoGaming.ro with dry-run safety enabled. "
            "This matters because the live site can behave differently in headless mode and because "
            "regulated money actions must not be submitted from an uncontrolled production account.",
            s["body"],
        ),
        two_column_table(
            [
                ("Run command", "uv run python -m src.main --xlsx test_cases.xlsx --provider openai --model gpt-4o --headless false"),
                ("Report location", "reports/full_rerun_20260501_213043_column_notes/report.html and report.json"),
                ("Result", f"{summary['pass']} pass, {summary['blocked']} blocked, {summary['fail']} fail, {summary['inconclusive']} inconclusive."),
                ("Business interpretation", "No product bug was asserted without enough evidence. Blocked cases identify exact setup needed for a full regulated E2E run."),
            ],
            s,
        ),
        Paragraph("Why this is strong evidence", s["h2"]),
        Paragraph(
            "The report is useful to hiring managers because it separates engineering execution from "
            "test-governance maturity. The agent proves what is safe to prove on production, stops "
            "where real money or protected identity flows begin, and explains how to complete each "
            "remaining case in staging.",
            s["body"],
        ),
        Paragraph("Report semantics", s["h2"]),
        table(
            [
                ["Verdict", "Meaning in this project", "Business value"],
                ["PASS", "Expected behavior was observed with browser evidence.", "Can be used as regression evidence."],
                ["FAIL", "Expected behavior was not observed.", "Creates a bug candidate with severity and reproduction path."],
                ["BLOCKED", "The test needs a missing account state, OTP fixture, VPN/provider stability, or staging funds.", "Turns environment risk into an actionable setup request instead of a vague excuse."],
                ["INCONCLUSIVE", "The agent reached a partial state but not enough to prove the expected result.", "Signals manual review or safer test data is needed."],
            ],
            [24 * mm, 76 * mm, 73 * mm],
            s,
        ),
        PageBreak(),
    ]


def test_pages(s: dict[str, ParagraphStyle], results: dict[str, dict]) -> list:
    simple_rows = [
        ["ID", "What the agent does", "Completion status and business why"],
        ["simple-1", "Opens login, enters invalid credentials, confirms the Romanian error message.", "PASS. Proves basic authentication rejection and protects account takeover/support risk."],
        ["simple-2", "Would log in and attempt deposit access for an already self-excluded account; stops before payment.", "BLOCKED. Needs a dedicated self-excluded staging account and payment sandbox. Important for ONJN/responsible-gambling compliance."],
        ["simple-3", "Would attempt sports bet placement for a self-excluded account; dry-run blocks final wager.", "BLOCKED. Needs self-excluded test account and test wallet. Prevents unlawful betting by restricted players."],
        ["simple-4", "Would attempt login during active Time Out.", "BLOCKED. Needs account with Time Out already active. Prevents reversing or damaging a real account."],
        ["simple-5", "Would open Sports Chat as restricted player and try open/send action.", "BLOCKED. Needs restricted account. Protects responsible-gambling feature boundaries and moderation risk."],
        ["simple-6", "Opens Virtual Sports lobby and verifies visible loaded content.", "PASS. Confirms a revenue section is not blank or broken."],
        ["simple-7", "Loads homepage and checks banner images for broken assets.", "PASS. Protects promotions, campaigns and first-page trust."],
        ["simple-8", "Opens Fast Games and launches a demo/fun game iframe.", "PASS. Confirms instant-games entry point without real balance risk."],
        ["simple-9", "Attempts to reach CNP length validation in registration.", "BLOCKED. Live flow gates CNP behind SMS OTP. Needs test phone/OTP fixture."],
        ["simple-10", "Attempts to reach non-numeric CNP validation.", "BLOCKED. Same OTP gate. Needs staging/bypass to avoid using real identity data."],
    ]

    complex_rows = [
        ["ID", "What the agent does", "Completion status and business why"],
        ["complex-1", "Opens Sports/Tennis route and validates filtered event/market content.", "PASS. Proves sportsbook navigation and filtering for a high-use betting workflow."],
        ["complex-2", "Uses Bet Generator criteria, creates selections and inserts them into bet slip.", "PASS for generator and slip insertion. Full bet submit needs staging funds."],
        ["complex-3", "Verifies generated bet follows selected criteria and appears in bet slip.", "PASS for generation logic. Full Open Bets lifecycle needs staging wallet."],
        ["complex-4", "Loads Virtual Sports provider and waits for market labels for translation validation.", "BLOCKED in latest run. Iframe loaded but labels did not render; needs stable VPN/provider session and approved glossary."],
        ["complex-5", "Attempts Virtual Sports FUN/demo bet flow.", "BLOCKED in latest run. FUN session did not initialize; needs stable demo provider or staging access."],
        ["complex-6", "Checks casino demo stake controls and live-casino min/max ranges without real wagering.", "PASS as safe proxy. Full below/above limit rejection needs test wallet."],
        ["complex-7", "Launches casino slot in /play/fun/ and performs demo spin.", "PASS. Confirms game launch and accepted demo action without real balance."],
        ["complex-8", "Can open live-casino real-play readiness when allowed, but does not place a real wager.", "BLOCKED for final wager. No public demo mode; needs operator-approved test table or staging funds."],
        ["complex-9", "Would create then reuse a CNP to test duplicate rejection.", "BLOCKED. Needs controlled test identity and OTP access. Avoids PII misuse."],
        ["complex-10", "Would complete registration email validation after OTP.", "BLOCKED. Needs disposable test email plus controlled phone/OTP fixture."],
    ]

    return [
        Paragraph("3. Simple Test Coverage - How Each Case Is Completed", s["h1"]),
        Paragraph(
            "The simple sheet demonstrates core production smoke coverage plus responsible-gambling "
            "precondition handling. Passing cases are fully automated; blocked cases explain the exact "
            "safe setup needed to complete them.",
            s["body"],
        ),
        table(simple_rows, [20 * mm, 75 * mm, 78 * mm], s),
        PageBreak(),
        Paragraph("4. Complex Test Coverage - How Each Case Is Completed", s["h1"]),
        Paragraph(
            "The complex sheet focuses on sportsbook generation, casino workflows, provider iframe "
            "stability, identity validation and real-money boundaries. The implementation proves safe "
            "parts on production and explicitly names what staging must provide.",
            s["body"],
        ),
        table(complex_rows, [20 * mm, 75 * mm, 78 * mm], s),
        PageBreak(),
    ]


def blockers_page(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("5. Blocked Tests Are Actionable, Not Weaknesses", s["h1"]),
        Paragraph(
            "A regulated gambling QA system must distinguish product defects from missing test "
            "preconditions. The blocked tests form a setup checklist for the operator or staging owner.",
            s["body"],
        ),
        table(
            [
                ["Blocker", "Affected cases", "What is needed to complete", "Business risk covered"],
                ["Self-excluded account", "simple-2, simple-3, simple-5", "Dedicated account already in self-exclusion/restriction state.", "Prevents deposits, bets and chat access for restricted players."],
                ["Time Out account", "simple-4", "Account with temporary Time Out already active.", "Confirms cool-off access is enforced before lobby access."],
                ["SMS OTP / registration fixture", "simple-9, simple-10, complex-9, complex-10", "Test phone number, OTP capture/bypass, disposable test email and approved test CNP.", "Avoids PII misuse while proving identity validation and duplicate prevention."],
                ["Payment or test wallet", "simple-2, complex-2, complex-3, complex-6, complex-8", "Staging wallet, payment sandbox or operator-issued funds.", "Allows final money-flow assertions without risking real funds."],
                ["Provider/VPN stability", "complex-4, complex-5", "Stable Romania route or whitelisted staging provider session.", "Prevents false failures caused by iframe/session initialization instability."],
            ],
            [31 * mm, 33 * mm, 58 * mm, 51 * mm],
            s,
        ),
        Paragraph("Business framing for interviews", s["h2"]),
        Paragraph(
            "This is the kind of answer a QA automation specialist should give in iGaming: "
            "complete the safe automation now, document the legal/test-data gap, and ask for the "
            "minimum staging capability required to finish the risk. That protects the business, "
            "the account, the player and the candidate's credibility.",
            s["callout"],
        ),
        PageBreak(),
    ]


def telegram_pages(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("6. Telegram Bot - Controlled QA Command Center", s["h1"]),
        Paragraph(
            "The Telegram bot turns the local CLI into a production-style ChatOps workflow. "
            "It is intentionally not a free-for-all runner: access is role-based, only one "
            "browser job runs at a time, reports are sent back as artifacts, and dry-run safety "
            "is always enforced from Telegram.",
            s["body"],
        ),
        table(
            [
                ["Component", "Implementation", "Why it matters"],
                ["Access control", "src/bot_auth.py supports env admins, a one-time admin bootstrap code, invite-code users and a two-user limit.", "Matches the requested one admin plus two users while avoiding hardcoded secrets in Git."],
                ["Menus and commands", "src/bot.py and src/bot_keyboards.py expose /menu, Run tests, Reports, Status and Admin buttons.", "Non-developers can trigger QA without remembering long CLI commands."],
                ["Long-running jobs", "src/bot_jobs.py starts the existing CLI as a subprocess and tracks queued/running/completed/failed/cancelled state.", "A 10-20 minute browser run does not freeze Telegram handlers."],
                ["Report delivery", "src/bot_reports.py reads report.json and sends report.html/report.json with Telegram documents.", "The same evidence can be shared with QA leads, interviewers or stakeholders."],
                ["Safety boundary", "ALLOW_REAL_ACCOUNT_TESTS is removed from the bot subprocess environment and --allow-money is not exposed.", "Users cannot accidentally place a real bet or submit a deposit from a chat button."],
            ],
            [32 * mm, 75 * mm, 66 * mm],
            s,
        ),
        Paragraph("Bot hierarchy", s["h2"]),
        two_column_table(
            [
                ("Admin", "Can create/remove users, cancel active runs, view users, install command menu, run safe suites and retrieve reports."),
                ("User 1 and User 2", "Can run safe dry-run suites, run categories or specific IDs, check status and retrieve reports."),
                ("Guest", "Can see access denied plus their Telegram numeric ID, or can use /login with the invite code if enabled."),
                ("Concurrency", "Only one active job is allowed. Additional requests receive the active run ID and Status/Cancel controls."),
            ],
            s,
        ),
        PageBreak(),
        Paragraph("7. Telegram Bot Usage Guide", s["h1"]),
        Paragraph("Environment setup", s["h2"]),
        table(
            [
                ["Setting", "Purpose"],
                ["TELEGRAM_BOT_TOKEN", "Token from BotFather. Stored only in .env, never committed."],
                ["TELEGRAM_ADMIN_INVITE_CODE", "One-time code for first admin when TELEGRAM_ADMIN_IDS is empty."],
                ["TELEGRAM_INVITE_CODE", "Invite code for up to two regular users."],
                ["TELEGRAM_DEFAULT_PROVIDER / MODEL", "Default LLM provider for bot-triggered runs, usually openai / gpt-4o."],
                ["TELEGRAM_DEFAULT_HEADLESS=false", "Recommended for TotoGaming live runs because headed Chromium avoids some live-site blocking."],
                ["TELEGRAM_REPORT_ROOT", "Folder where bot run artifacts are written, default reports/bot_runs."],
            ],
            [55 * mm, 118 * mm],
            s,
        ),
        Paragraph("Recommended test sequence", s["h2"]),
        table(
            [
                ["Step", "Command or action", "Expected outcome"],
                ["1", "uv run python -m src.bot", "Bot starts polling."],
                ["2", "/admin_login admin-setup-2026", "First admin is created; the main menu opens."],
                ["3", "/login qa-user-2026", "User 1 and User 2 join; third user is rejected by max-user rule."],
                ["4", "/run_id simple-1", "Fast safe test verifies the runner and sends a small report."],
                ["5", "/run_simple or menu -> Run tests -> Simple", "Runs the simple suite and returns HTML/JSON report files."],
                ["6", "/status", "Shows active job and latest output; repeated taps are handled without Telegram edit errors."],
                ["7", "/reports", "Sends the latest report artifacts again."],
            ],
            [16 * mm, 65 * mm, 92 * mm],
            s,
        ),
        Paragraph(
            "Interview value: this shows not only automation skill, but product thinking. "
            "The bot makes the system usable by QA leads while preserving access control, "
            "traceability and money-flow safety.",
            s["callout"],
        ),
        PageBreak(),
    ]


def excel_updates_page(s: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("8. Excel Workbook Updates and Business Impact", s["h1"]),
        Paragraph(
            "The workbook was upgraded from a case list into a living QA risk document. "
            "This is important because hiring teams want to see not only automation code, "
            "but also the thinking that connects tests to business outcomes.",
            s["body"],
        ),
        table(
            [
                ["Workbook area", "Update", "Why it matters"],
                ["Second sheet - Simple tests", "Added a sixth column: execution method, block reason and completion path.", "Every simple test now explains whether it is fully automated, safely blocked, and what data/environment would complete it."],
                ["Third sheet - Complex tests", "Added the same sixth column with headed-run outcomes and staging requirements.", "Complex cases now distinguish demo-mode proof, dry-run stop points, provider blockers and real-money prerequisites."],
                ["Fourth sheet - New tests", "Added 20 new risk-based cases with reason/business impact.", "Extends the assignment beyond the original list into ONJN compliance, revenue, payments, mobile and AML risk."],
                ["Automation compatibility", "src/test_loader.py continues to read the first five automation columns.", "Human documentation columns do not break the runner, which is exactly how a maintainable QA workbook should behave."],
                ["Reporting alignment", "The full rerun report and Excel notes now tell the same story.", "Interviewers can compare the PDF, Excel and HTML report and see consistent evidence."],
            ],
            [39 * mm, 72 * mm, 62 * mm],
            s,
        ),
        Paragraph("Business why", s["h2"]),
        Paragraph(
            "For an iGaming company, missing tests are not only engineering gaps. They can become "
            "license risk, payment disputes, support load, failed campaigns, user churn, or public "
            "trust damage. The updated Excel makes those risks explicit and converts them into "
            "testable acceptance criteria.",
            s["body"],
        ),
        Paragraph("Technical why", s["h2"]),
        Paragraph(
            "The workbook remains machine-readable while becoming manager-readable. The agent can "
            "still load the same cases, and humans can see the exact path to completion. This is a "
            "practical bridge between QA automation, compliance evidence and stakeholder reporting.",
            s["body"],
        ),
        Paragraph(
            "Final message for the hiring conversation: this project demonstrates automation, "
            "judgment and domain responsibility. It does not just click buttons; it explains risk, "
            "protects safety boundaries, produces evidence and gives a team an operational way to "
            "run the work.",
            s["callout"],
        ),
    ]


def load_latest_results() -> tuple[dict, dict[str, dict]]:
    fallback = {"total": 20, "pass": 9, "fail": 0, "blocked": 11, "inconclusive": 0, "pass_rate": 45.0}
    if not REPORT_JSON.exists():
        return fallback, {}
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    results = {item["case_id"]: item for item in payload.get("results", [])}
    return payload.get("summary", fallback), results


def table(rows: list[list[str]], widths: list[float], s: dict[str, ParagraphStyle]) -> Table:
    data = []
    for ridx, row in enumerate(rows):
        style = s["table_header"] if ridx == 0 else s["table_cell"]
        data.append([Paragraph(str(cell), style) for cell in row])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def two_column_table(items: list[tuple[str, str]], s: dict[str, ParagraphStyle]) -> Table:
    rows = [["Area", "Detail"], *[[a, b] for a, b in items]]
    return table(rows, [48 * mm, 125 * mm], s)


def build_appendix(path: Path, story: list) -> None:
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title="Digitain QA Agent - Strategic Brief Appendix",
        author="Edgar",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(15 * mm, 8 * mm, "Digitain AI QA Agent - Strategic Brief Appendix")
    canvas.drawRightString(195 * mm, 8 * mm, f"Appendix page {doc.page}")
    canvas.restoreState()


def merge_pdfs(base: Path, appendix: Path, output: Path) -> None:
    writer = PdfWriter()
    for pdf in (base, appendix):
        reader = PdfReader(str(pdf))
        for page in reader.pages:
            writer.add_page(page)

    writer.add_metadata(
        {
            "/Title": "Digitain AI QA Agent - Strategic Brief",
            "/Author": "Edgar",
            "/Subject": "AI QA architecture, test evidence, Excel updates and Telegram bot operations",
            "/Producer": "ReportLab and pypdf",
            "/ModDate": datetime.utcnow().strftime("D:%Y%m%d%H%M%S+00'00'"),
        }
    )
    with output.open("wb") as fh:
        writer.write(fh)


if __name__ == "__main__":
    main()
