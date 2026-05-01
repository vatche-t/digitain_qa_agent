"""
CLI entry point.

Usage:
    python -m src.main --xlsx test_cases.xlsx
    python -m src.main --xlsx test_cases.xlsx --provider openai --model gpt-4o
    python -m src.main --xlsx test_cases.xlsx --difficulty simple
    python -m src.main --xlsx test_cases.xlsx --tag responsible-gambling
    python -m src.main --xlsx test_cases.xlsx --ids simple-1,simple-2 --headless=false

Environment:
    ANTHROPIC_API_KEY  required if --provider claude
    OPENAI_API_KEY     required if --provider openai
    PROXY_URL          optional, e.g. for Romania-routed VPN
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from src.agent import QAAgent, TestResult
from src.llm_client import get_client
from src.reporter import write_html, write_json
from src.test_loader import filter_cases, load_test_cases


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AI-powered QA agent for TotoGaming.ro (Digitain assignment).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--xlsx", default="test_cases.xlsx", help="Path to test case workbook.")
    p.add_argument("--base-url", default="https://totogaming.ro",
                   help="Site under test.")
    p.add_argument("--provider", choices=["claude", "openai"], default="claude",
                   help="LLM provider.")
    p.add_argument("--model", default=None,
                   help="Override default model (e.g. gpt-4o, claude-sonnet-4-5).")
    p.add_argument("--difficulty", choices=["simple", "complex"], default=None,
                   help="Run only simple or complex tests.")
    p.add_argument("--tag", default=None,
                   help="Run only tests with this tag (e.g. responsible-gambling).")
    p.add_argument("--ids", default=None,
                   help="Comma-separated case IDs to run (e.g. simple-1,complex-3).")
    p.add_argument("--headless", default="true",
                   help="Run browser headless (true/false).")
    p.add_argument("--allow-money", action="store_true",
                   help="DISABLE safety rails. Required to test real deposits/bets.")
    p.add_argument("--report-dir", default="reports",
                   help="Where to write HTML + JSON reports.")
    return p.parse_args()


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency."""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


async def main() -> int:
    load_dotenv()
    args = parse_args()
    headless = args.headless.lower() in {"true", "1", "yes"}
    dry_run = not args.allow_money

    # 1. Load test cases
    all_cases = load_test_cases(args.xlsx)
    ids = args.ids.split(",") if args.ids else None
    cases = filter_cases(all_cases, difficulty=args.difficulty, tag=args.tag, ids=ids)

    if not cases:
        print(f"No test cases match the filters. Loaded {len(all_cases)} total.")
        return 1

    print(f"▶ Running {len(cases)} test case(s) against {args.base_url}")
    print(f"  LLM: {args.provider}" + (f" ({args.model})" if args.model else ""))
    print(f"  Dry-run (safety): {'ON' if dry_run else 'OFF — real money actions allowed'}")
    print(f"  Proxy: {'configured' if os.getenv('PROXY_URL') else 'none'}")
    print()

    # 2. Wire up agent
    llm = get_client(args.provider, args.model)
    agent = QAAgent(
        llm=llm,
        base_url=args.base_url,
        dry_run=dry_run,
        headless=headless,
        artifact_dir=Path(args.report_dir),
        proxy_url=os.getenv("PROXY_URL"),
    )

    # 3. Run sequentially. (Easy parallelism win later: asyncio.gather with a semaphore.)
    results: list[TestResult] = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case.id}: {case.description[:80]}...")
        result = await agent.run_case(case)
        verdict_icon = {"pass": "✓", "fail": "✗", "blocked": "⊘", "inconclusive": "?"}
        print(f"   → {verdict_icon.get(result.verdict, '?')} {result.verdict.upper()} "
              f"({result.duration_seconds}s) — {result.reasoning[:120]}")
        results.append(result)

    # 4. Write reports
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "report.json"
    html_path = report_dir / "report.html"
    write_json(results, json_path)
    write_html(
        results, html_path,
        run_meta={
            "provider": args.provider,
            "model": args.model or "default",
            "base_url": args.base_url,
            "dry_run": dry_run,
        },
    )
    print()
    print(f"✓ JSON report: {json_path}")
    print(f"✓ HTML report: {html_path}")

    # Exit code: non-zero if any failures (CI-friendly)
    failed = sum(1 for r in results if r.verdict == "fail")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
