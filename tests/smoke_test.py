"""
Smoke test — proves the pipeline works end-to-end without API keys or VPN.

Uses:
  - A FakeLLM that returns hard-coded plans (no API call).
  - A local HTML page served via file:// (no network).

Run:
    python -m tests.smoke_test
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from src.agent import QAAgent
from src.llm_client import LLMClient
from src.reporter import write_html, write_json
from src.test_loader import TestCase


# A tiny standalone HTML page that mimics a login form.
LOCAL_PAGE = """
<!doctype html>
<html><head><title>Mock Login</title></head>
<body>
  <h1>Mock Login Page</h1>
  <form id="login">
    <label for="u">Username</label>
    <input id="u" type="text" aria-label="Username">
    <label for="p">Password</label>
    <input id="p" type="password" aria-label="Password">
    <button type="button" id="submit"
            onclick="document.getElementById('msg').textContent='Invalid username or password'">
      Log in
    </button>
    <div id="msg" role="alert"></div>
  </form>
</body></html>
"""


class FakeLLM(LLMClient):
    """Returns canned responses so we can test without any API."""
    name = "fake"

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        if "JUDGE" in system or "verdict" in system.lower():
            return json.dumps({
                "verdict": "pass",
                "reasoning": "Saw 'Invalid username or password' on page after submit.",
                "bug_severity": None,
                "suggested_jira_title": None,
            })
        # Planner: return a plan that fills bad creds and clicks Log in
        return json.dumps({
            "plan": [
                {"action": "fill", "args": {"role": "textbox", "name": "Username", "text": "baduser"}},
                {"action": "fill", "args": {"role": "textbox", "name": "Password", "text": "wrongpass"}},
                {"action": "click", "args": {"role": "button", "name": "Log in"}},
                {"action": "wait", "args": {"seconds": 1}},
                {"action": "assert_text_contains", "args": {"text": "Invalid"}},
                {"action": "screenshot", "args": {"label": "after-submit"}},
                {"action": "done", "args": {}},
            ]
        })


async def main() -> int:
    print("▶ Smoke test: AI QA agent pipeline")
    print()

    # 1. Spin up a local HTML file
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(LOCAL_PAGE)
        local_url = "file://" + f.name

    # 2. A representative test case
    case = TestCase(
        id="smoke-1",
        difficulty="simple",
        section="Login fields",
        description="Verify invalid credentials show an error.",
        steps="Open login page, enter wrong username/password, click Log in.",
        expected="Error message is displayed.",
        tags=["auth"],
    )

    # 3. Run the agent
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    agent = QAAgent(
        llm=FakeLLM(),
        base_url=local_url,
        dry_run=True,
        headless=True,
        artifact_dir=report_dir,
    )
    result = await agent.run_case(case)

    # 4. Print + write reports
    print(f"Verdict:   {result.verdict.upper()}")
    print(f"Duration:  {result.duration_seconds}s")
    print(f"Reasoning: {result.reasoning}")
    print(f"Steps run: {len(result.steps)}")
    for s in result.steps:
        icon = {"ok": "✓", "skipped": "⊘", "error": "✗"}.get(s.status, "?")
        print(f"  {icon} step {s.step}: {s.action} {s.target} {s.detail}")

    write_json([result], report_dir / "smoke_report.json")
    write_html([result], report_dir / "smoke_report.html",
               run_meta={"provider": "fake", "model": "FakeLLM",
                         "base_url": local_url, "dry_run": True})
    print()
    print(f"✓ Wrote reports/smoke_report.{{json,html}}")
    return 0 if result.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
