"""Report formatting and delivery helpers for the Telegram bot."""

from __future__ import annotations

import json
from pathlib import Path


def read_report_summary(report_dir: Path) -> dict | None:
    path = report_dir / "report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("summary")
    except (json.JSONDecodeError, OSError):
        return None


def format_summary(summary: dict | None) -> str:
    if not summary:
        return "No report summary was produced."
    return (
        f"Total: {summary.get('total', 0)}\n"
        f"PASS: {summary.get('pass', 0)}\n"
        f"FAIL: {summary.get('fail', 0)}\n"
        f"BLOCKED: {summary.get('blocked', 0)}\n"
        f"INCONCLUSIVE: {summary.get('inconclusive', 0)}\n"
        f"Pass rate: {summary.get('pass_rate', 0):.1f}%"
    )


def format_report_list(report_dirs: list[Path]) -> str:
    if not report_dirs:
        return "No bot reports yet."

    lines = ["Latest bot reports:"]
    for idx, report_dir in enumerate(report_dirs, 1):
        summary = read_report_summary(report_dir)
        suffix = ""
        if summary:
            suffix = (
                f" — pass {summary.get('pass', 0)}, "
                f"fail {summary.get('fail', 0)}, blocked {summary.get('blocked', 0)}"
            )
        lines.append(f"{idx}. {report_dir.name}{suffix}")
    return "\n".join(lines)


def report_files(report_dir: Path) -> list[Path]:
    paths = [report_dir / "report.html", report_dir / "report.json"]
    return [p for p in paths if p.exists()]
