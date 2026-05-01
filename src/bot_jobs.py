"""Long-running QA job orchestration for the Telegram bot."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


RunKind = Literal["all", "simple", "complex", "tag", "ids"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class RunRequest:
    kind: RunKind
    requested_by: int
    chat_id: int
    provider: str
    model: str
    xlsx: str
    base_url: str
    headless: bool
    tag: str | None = None
    ids: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.kind == "tag":
            return f"tag:{self.tag}"
        if self.kind == "ids":
            return ",".join(self.ids)
        return self.kind


@dataclass
class BotJob:
    id: str
    request: RunRequest
    report_dir: Path
    command: list[str]
    status: JobStatus = "queued"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    returncode: int | None = None
    summary: dict | None = None
    error: str | None = None
    log_path: Path | None = None
    process: asyncio.subprocess.Process | None = field(default=None, repr=False)
    task: asyncio.Task | None = field(default=None, repr=False)
    output_tail: deque[str] = field(default_factory=lambda: deque(maxlen=30), repr=False)

    @property
    def is_active(self) -> bool:
        return self.status in {"queued", "running"}


class JobManager:
    """Runs one browser test job at a time."""

    def __init__(
        self,
        report_root: Path = Path("reports/bot_runs"),
        *,
        workspace: Path | None = None,
    ) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self.report_root = report_root
        if not self.report_root.is_absolute():
            self.report_root = self.workspace / self.report_root
        self.report_root.mkdir(parents=True, exist_ok=True)
        self._active: BotJob | None = None
        self._history: list[BotJob] = []
        self._lock = asyncio.Lock()

    @property
    def active_job(self) -> BotJob | None:
        return self._active if self._active and self._active.is_active else None

    @property
    def history(self) -> list[BotJob]:
        return list(self._history)

    async def start(self, request: RunRequest) -> BotJob:
        async with self._lock:
            if self.active_job:
                raise RuntimeError(f"Run {self.active_job.id} is already active.")

            job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = self.report_root / f"{job_id}_{_slug(request.label)}"
            command = _build_command(request, report_dir)
            job = BotJob(
                id=job_id,
                request=request,
                report_dir=report_dir,
                command=command,
                log_path=report_dir / "bot_run.log",
            )
            self._active = job
            self._history.append(job)
            job.task = asyncio.create_task(self._run(job))
            return job

    async def cancel_active(self) -> BotJob | None:
        job = self.active_job
        if not job:
            return None
        job.status = "cancelled"
        if job.process and job.process.returncode is None:
            job.process.terminate()
            try:
                await asyncio.wait_for(job.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                job.process.kill()
                await job.process.wait()
        if job.task:
            job.task.cancel()
        job.completed_at = datetime.now()
        return job

    def latest_report_dir(self) -> Path | None:
        dirs = [p for p in self.report_root.glob("*") if (p / "report.json").exists()]
        return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None

    def list_report_dirs(self, limit: int = 5) -> list[Path]:
        dirs = [p for p in self.report_root.glob("*") if (p / "report.json").exists()]
        return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    async def _run(self, job: BotJob) -> None:
        job.status = "running"
        job.started_at = datetime.now()
        job.report_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.pop("ALLOW_REAL_ACCOUNT_TESTS", None)

        with job.log_path.open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(job.command) + "\n\n")
            try:
                job.process = await asyncio.create_subprocess_exec(
                    *job.command,
                    cwd=self.workspace,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env,
                )

                assert job.process.stdout is not None
                async for raw_line in job.process.stdout:
                    line = raw_line.decode("utf-8", errors="replace")
                    log.write(line)
                    log.flush()
                    clean = line.strip()
                    if clean:
                        job.output_tail.append(clean)

                job.returncode = await job.process.wait()
                if job.status == "cancelled":
                    return

                job.summary = _read_summary(job.report_dir / "report.json")
                job.status = "completed" if job.returncode == 0 else "failed"
            except asyncio.CancelledError:
                if job.status != "cancelled":
                    job.status = "cancelled"
                raise
            except Exception as exc:  # pragma: no cover - defensive guard for bot runtime
                job.status = "failed"
                job.error = str(exc)
                log.write(f"\nBOT JOB ERROR: {exc}\n")
            finally:
                job.completed_at = datetime.now()
                if self._active is job:
                    self._active = None


def _build_command(request: RunRequest, report_dir: Path) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--xlsx",
        request.xlsx,
        "--base-url",
        request.base_url,
        "--provider",
        request.provider,
        "--model",
        request.model,
        "--headless",
        "true" if request.headless else "false",
        "--report-dir",
        str(report_dir),
    ]

    if request.kind in {"simple", "complex"}:
        cmd.extend(["--difficulty", request.kind])
    elif request.kind == "tag" and request.tag:
        cmd.extend(["--tag", request.tag])
    elif request.kind == "ids" and request.ids:
        cmd.extend(["--ids", ",".join(request.ids)])

    return cmd


def _read_summary(report_json: Path) -> dict | None:
    if not report_json.exists():
        return None
    try:
        payload = json.loads(report_json.read_text(encoding="utf-8"))
        return payload.get("summary")
    except (json.JSONDecodeError, OSError):
        return None


def _slug(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return safe.strip("_")[:80] or "run"
