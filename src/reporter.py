"""
Test run reporter.

Outputs both:
  - report.json: machine-readable, for CI / Slack / Jira integration.
  - report.html: a clean dashboard a human can read in 30 seconds.

The HTML is intentionally single-file (no external CSS/JS) so it can be
emailed, dropped in Slack, or saved as an artifact in GitLab/Jenkins.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.agent import TestResult


def write_json(results: list[TestResult], path: Path) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": _summary(results),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_html(results: list[TestResult], path: Path, *, run_meta: dict) -> None:
    summary = _summary(results)
    rows = "\n".join(_render_row(r) for r in results)
    html = _TEMPLATE.format(
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        provider=run_meta.get("provider", "—"),
        model=run_meta.get("model", "—"),
        base_url=run_meta.get("base_url", "—"),
        dry_run="ON" if run_meta.get("dry_run") else "OFF",
        total=summary["total"],
        passed=summary["pass"],
        failed=summary["fail"],
        blocked=summary["blocked"],
        inconclusive=summary["inconclusive"],
        pass_rate=f"{summary['pass_rate']:.1f}",
        rows=rows,
    )
    path.write_text(html, encoding="utf-8")


def _summary(results: list[TestResult]) -> dict:
    counts = {"pass": 0, "fail": 0, "blocked": 0, "inconclusive": 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    total = len(results)
    return {
        "total": total,
        **counts,
        "pass_rate": (counts["pass"] / total * 100) if total else 0.0,
    }


def _render_row(r: TestResult) -> str:
    color = {
        "pass": "#16a34a",
        "fail": "#dc2626",
        "blocked": "#ea580c",
        "inconclusive": "#6b7280",
    }[r.verdict]

    steps_html = ""
    for s in r.steps:
        icon = {"ok": "✓", "skipped": "⊘", "error": "✗"}.get(s.status, "?")
        steps_html += (
            f"<li><code>{icon} {s.action}</code> "
            f"<span class='target'>{_esc(s.target)}</span>"
            f"{(' — ' + _esc(s.detail)) if s.detail else ''}</li>"
        )

    return f"""
    <tr>
      <td><code>{_esc(r.case_id)}</code></td>
      <td>{_esc(r.section)}</td>
      <td>{_esc(r.description)}</td>
      <td><span class="badge" style="background:{color}">{r.verdict.upper()}</span></td>
      <td class="reasoning">{_esc(r.reasoning)}</td>
      <td>{r.duration_seconds}s</td>
    </tr>
    <tr class="detail">
      <td colspan="6">
        <details>
          <summary>Execution trace ({len(r.steps)} steps)</summary>
          <ul>{steps_html}</ul>
          {f'<div class="trace-link">Playwright trace: <code>{_esc(r.trace_path)}</code></div>' if r.trace_path else ''}
        </details>
      </td>
    </tr>
    """


def _esc(s: str | None) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Digitain QA Agent — Run Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0; padding: 0; background: #f8fafc; color: #0f172a; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ font-size: 28px; margin: 0 0 4px; }}
    .subtitle {{ color: #64748b; margin: 0 0 24px; font-size: 14px; }}
    .meta {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px;
             padding: 16px 20px; margin-bottom: 16px; font-size: 13px;
             display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }}
    .meta div span {{ display: block; color: #64748b; font-size: 11px;
                      text-transform: uppercase; letter-spacing: 0.05em; }}
    .meta div strong {{ font-size: 14px; }}
    .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;
              margin-bottom: 24px; }}
    .stat {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px;
             padding: 16px; text-align: center; }}
    .stat .num {{ font-size: 32px; font-weight: 700; line-height: 1; }}
    .stat .label {{ font-size: 12px; color: #64748b; text-transform: uppercase;
                    letter-spacing: 0.05em; margin-top: 4px; }}
    .stat.pass .num {{ color: #16a34a; }}
    .stat.fail .num {{ color: #dc2626; }}
    .stat.blocked .num {{ color: #ea580c; }}
    .stat.incon .num {{ color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; background: white;
             border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0;
              font-size: 13px; vertical-align: top; }}
    th {{ background: #f1f5f9; font-weight: 600; font-size: 12px;
          text-transform: uppercase; letter-spacing: 0.05em; color: #475569; }}
    tr.detail td {{ background: #f8fafc; padding: 0 12px 12px 12px; border-bottom: 2px solid #e2e8f0; }}
    .badge {{ color: white; padding: 4px 10px; border-radius: 4px;
              font-size: 11px; font-weight: 600; letter-spacing: 0.03em; }}
    .reasoning {{ max-width: 320px; color: #334155; }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 3px;
            font-size: 12px; }}
    .target {{ color: #64748b; font-size: 12px; }}
    details summary {{ cursor: pointer; color: #2563eb; font-size: 12px;
                       padding: 8px 0; }}
    details ul {{ margin: 4px 0 0 0; padding-left: 20px; font-size: 12px; }}
    details li {{ margin: 4px 0; color: #475569; }}
    .trace-link {{ font-size: 11px; color: #64748b; margin-top: 6px; }}
    footer {{ text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Digitain QA Agent — Run Report</h1>
    <p class="subtitle">Automated test run against TotoGaming.ro. Generated by AI-driven Playwright agent.</p>

    <div class="meta">
      <div><span>Generated</span><strong>{generated_at}</strong></div>
      <div><span>LLM Provider</span><strong>{provider}</strong></div>
      <div><span>Model</span><strong>{model}</strong></div>
      <div><span>Target</span><strong>{base_url}</strong></div>
      <div><span>Dry Run</span><strong>{dry_run}</strong></div>
    </div>

    <div class="stats">
      <div class="stat"><div class="num">{total}</div><div class="label">Total</div></div>
      <div class="stat pass"><div class="num">{passed}</div><div class="label">Passed</div></div>
      <div class="stat fail"><div class="num">{failed}</div><div class="label">Failed</div></div>
      <div class="stat blocked"><div class="num">{blocked}</div><div class="label">Blocked</div></div>
      <div class="stat incon"><div class="num">{inconclusive}</div><div class="label">Inconclusive</div></div>
    </div>

    <p style="margin-bottom: 12px;"><strong>Pass rate:</strong> {pass_rate}%</p>

    <table>
      <thead>
        <tr>
          <th>ID</th><th>Section</th><th>Description</th>
          <th>Verdict</th><th>Reasoning</th><th>Time</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>

    <footer>Built for the Digitain AI Automation Specialist task — Edgar, 2026.</footer>
  </div>
</body>
</html>
"""
