"""Telegram interface for running the Digitain QA agent.

Run locally:
    uv run python -m src.bot
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    Message,
)

from src.bot_auth import AccessStore, AuthService, BotAuthConfig
from src.bot_jobs import BotJob, JobManager, RunRequest
from src.bot_keyboards import (
    admin_menu,
    category_menu,
    confirm_run_menu,
    main_menu,
    reports_menu,
    run_menu,
    running_job_menu,
)
from src.bot_reports import format_report_list, format_summary, read_report_summary, report_files
from src.main import load_dotenv
from src.test_loader import load_test_cases


router = Router()
auth: AuthService
jobs: JobManager
settings: "BotSettings"
available_tags: list[str]


@dataclass(frozen=True)
class BotSettings:
    token: str
    provider: str
    model: str
    xlsx: str
    base_url: str
    headless: bool
    report_root: Path

    @classmethod
    def from_env(cls) -> "BotSettings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

        return cls(
            token=token,
            provider=os.getenv("TELEGRAM_DEFAULT_PROVIDER", "openai"),
            model=os.getenv("TELEGRAM_DEFAULT_MODEL", "gpt-4o"),
            xlsx=os.getenv("TELEGRAM_XLSX", "test_cases.xlsx"),
            base_url=os.getenv("TELEGRAM_BASE_URL", "https://totogaming.ro"),
            headless=os.getenv("TELEGRAM_DEFAULT_HEADLESS", "false").lower()
            in {"1", "true", "yes"},
            report_root=Path(os.getenv("TELEGRAM_REPORT_ROOT", "reports/bot_runs")),
        )


def _user_id(message_or_callback: Message | CallbackQuery) -> int | None:
    return message_or_callback.from_user.id if message_or_callback.from_user else None


def _is_allowed(message_or_callback: Message | CallbackQuery) -> bool:
    return auth.is_allowed(_user_id(message_or_callback))


def _is_admin(message_or_callback: Message | CallbackQuery) -> bool:
    return auth.is_admin(_user_id(message_or_callback))


async def _deny_message(message: Message) -> None:
    await message.answer(
        "Access denied.\n\n"
        "Ask the admin to add your Telegram numeric ID, or use:\n"
        "/login YOUR_INVITE_CODE\n\n"
        f"Your ID: {message.from_user.id if message.from_user else 'unknown'}"
    )


async def _deny_callback(callback: CallbackQuery) -> None:
    await callback.answer("Access denied.", show_alert=True)


async def _send_menu(message: Message) -> None:
    user_id = _user_id(message)
    await message.answer(
        "Digitain QA bot\n\n"
        f"Role: {auth.role_for(user_id)}\n"
        "Dry-run safety is always ON from Telegram.",
        reply_markup=main_menu(is_admin=auth.is_admin(user_id)),
    )


async def _edit_or_answer(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if callback.message and hasattr(callback.message, "edit_text"):
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            raise
    elif callback.message and hasattr(callback.message, "answer"):
        await callback.message.answer(text, reply_markup=reply_markup)


@router.message(CommandStart())
async def start(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    await _send_menu(message)


@router.message(Command("login"))
async def login(message: Message) -> None:
    user_id = _user_id(message)
    if not user_id:
        await message.answer("Could not identify your Telegram user.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /login INVITE_CODE")
        return

    ok, detail = auth.login_with_code(user_id, parts[1])
    await message.answer(f"{detail}\nRole: {auth.role_for(user_id)}")
    if ok:
        await _send_menu(message)


@router.message(Command("admin_login"))
async def admin_login(message: Message) -> None:
    user_id = _user_id(message)
    if not user_id:
        await message.answer("Could not identify your Telegram user.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /admin_login ADMIN_BOOTSTRAP_CODE")
        return

    ok, detail = auth.login_admin_with_code(user_id, parts[1])
    await message.answer(f"{detail}\nRole: {auth.role_for(user_id)}")
    if ok:
        await _send_menu(message)


@router.message(Command("menu"))
async def menu(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    await _send_menu(message)


@router.message(Command("whoami"))
async def whoami(message: Message) -> None:
    user_id = _user_id(message)
    await message.answer(
        f"ID: {user_id}\n"
        f"Role: {auth.role_for(user_id)}\n"
        f"Allowed: {'yes' if auth.is_allowed(user_id) else 'no'}"
    )


@router.message(Command("run_all"))
async def run_all(message: Message) -> None:
    await _start_from_message(message, "all")


@router.message(Command("run_simple"))
async def run_simple(message: Message) -> None:
    await _start_from_message(message, "simple")


@router.message(Command("run_complex"))
async def run_complex(message: Message) -> None:
    await _start_from_message(message, "complex")


@router.message(Command("run_tag"))
async def run_tag(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /run_tag betting")
        return
    await _launch_job(message.bot, message.chat.id, _make_request(message, "tag", tag=parts[1]))


@router.message(Command("run_id", "run_ids"))
async def run_ids(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /run_id simple-1 or /run_ids simple-1,complex-3")
        return

    ids = tuple(x.strip() for x in parts[1].replace(" ", ",").split(",") if x.strip())
    if not ids:
        await message.answer("No test IDs found.")
        return
    await _launch_job(message.bot, message.chat.id, _make_request(message, "ids", ids=ids))


@router.message(Command("status"))
async def status(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    await message.answer(_format_status())


@router.message(Command("cancel"))
async def cancel(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Only admin can cancel a running test job.")
        return
    job = await jobs.cancel_active()
    await message.answer(f"Cancelled run {job.id}." if job else "No active run.")


@router.message(Command("reports", "latest"))
async def reports(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    report_dir = jobs.latest_report_dir()
    if not report_dir:
        await message.answer("No bot reports yet.")
        return
    await _send_report_files(message.bot, message.chat.id, report_dir)


@router.message(Command("users"))
async def users(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Only admin can list users.")
        return
    await message.answer(_format_users())


@router.message(Command("add_user"))
async def add_user(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Only admin can add users.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer("Usage: /add_user 123456789")
        return
    ok, detail = auth.add_regular_user(int(parts[1].strip()))
    await message.answer(detail if ok else f"Could not add user: {detail}")


@router.message(Command("remove_user"))
async def remove_user(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Only admin can remove users.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer("Usage: /remove_user 123456789")
        return
    ok, detail = auth.remove_regular_user(int(parts[1].strip()))
    await message.answer(detail if ok else f"Could not remove user: {detail}")


@router.message(Command("setcommands"))
async def setcommands(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Only admin can install bot commands.")
        return
    await _install_commands(message.bot)
    await message.answer("Bot command menu updated.")


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    await message.answer(_help_text(is_admin=_is_admin(message)))


@router.callback_query(F.data == "menu:main")
async def cb_main(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(
        callback,
        "Digitain QA bot\n\nDry-run safety is always ON from Telegram.",
        reply_markup=main_menu(is_admin=_is_admin(callback)),
    )


@router.callback_query(F.data == "menu:run")
async def cb_run_menu(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, "Choose a safe dry-run test scope:", reply_markup=run_menu())


@router.callback_query(F.data.in_({"run:all", "run:simple", "run:complex"}))
async def cb_run_confirm(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    kind = (callback.data or "").split(":", 1)[1]
    await callback.answer()
    await _edit_or_answer(
        callback,
        "This may take several minutes.\n\n"
        f"Scope: {kind}\n"
        "Headed browser: yes\n"
        "Safety: dry-run ON, no real deposit/bet submit.\n\n"
        "Start now?",
        reply_markup=confirm_run_menu(kind),
    )


@router.callback_query(F.data.startswith("confirm:"))
async def cb_run_start(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    kind = (callback.data or "").split(":", 1)[1]
    await callback.answer("Starting")
    await _launch_job(callback.bot, callback.message.chat.id, _make_request(callback, kind))


@router.callback_query(F.data == "menu:categories")
async def cb_categories(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(
        callback,
        "Choose a category/tag:",
        reply_markup=category_menu(available_tags),
    )


@router.callback_query(F.data.startswith("run_tag:"))
async def cb_run_tag(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    tag = (callback.data or "").split(":", 1)[1]
    await callback.answer("Starting")
    await _launch_job(callback.bot, callback.message.chat.id, _make_request(callback, "tag", tag=tag))


@router.callback_query(F.data == "menu:specific")
async def cb_specific(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(
        callback,
        "Send one of these:\n\n"
        "/run_id simple-1\n"
        "/run_ids simple-1,complex-3\n\n"
        "The bot will run only those IDs and send the report.",
        reply_markup=run_menu(),
    )


@router.callback_query(F.data == "menu:reports")
async def cb_reports(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, "Reports:", reply_markup=reports_menu())


@router.callback_query(F.data == "reports:list")
async def cb_reports_list(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, format_report_list(jobs.list_report_dirs()))


@router.callback_query(F.data == "reports:latest")
async def cb_reports_latest(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer("Sending latest report")
    report_dir = jobs.latest_report_dir()
    if not report_dir:
        await _edit_or_answer(callback, "No bot reports yet.", reply_markup=reports_menu())
        return
    await _send_report_files(callback.bot, callback.message.chat.id, report_dir)


@router.callback_query(F.data == "job:status")
async def cb_status(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, _format_status(), reply_markup=running_job_menu())


@router.callback_query(F.data == "job:cancel")
async def cb_cancel(callback: CallbackQuery) -> None:
    if not _is_admin(callback):
        await _deny_callback(callback)
        return
    job = await jobs.cancel_active()
    await callback.answer("Cancelled" if job else "No active run", show_alert=True)
    await _edit_or_answer(callback, f"Cancelled run {job.id}." if job else "No active run.")


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    if not _is_allowed(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, _help_text(is_admin=_is_admin(callback)))


@router.callback_query(F.data == "menu:admin")
async def cb_admin(callback: CallbackQuery) -> None:
    if not _is_admin(callback):
        await _deny_callback(callback)
        return
    await callback.answer()
    await _edit_or_answer(callback, _format_users(), reply_markup=admin_menu())


async def _start_from_message(message: Message, kind: str) -> None:
    if not _is_allowed(message):
        await _deny_message(message)
        return
    await _launch_job(message.bot, message.chat.id, _make_request(message, kind))


def _make_request(
    source: Message | CallbackQuery,
    kind: str,
    *,
    tag: str | None = None,
    ids: tuple[str, ...] = (),
) -> RunRequest:
    return RunRequest(
        kind=kind,  # type: ignore[arg-type]
        requested_by=_user_id(source) or 0,
        chat_id=source.message.chat.id if isinstance(source, CallbackQuery) else source.chat.id,
        provider=settings.provider,
        model=settings.model,
        xlsx=settings.xlsx,
        base_url=settings.base_url,
        headless=settings.headless,
        tag=tag,
        ids=ids,
    )


async def _launch_job(bot: Bot, chat_id: int, request: RunRequest) -> None:
    try:
        job = await jobs.start(request)
    except RuntimeError as exc:
        await bot.send_message(chat_id, str(exc), reply_markup=running_job_menu())
        return

    await bot.send_message(
        chat_id,
        f"Started run {job.id}\n"
        f"Scope: {request.label}\n"
        f"Provider: {request.provider} / {request.model}\n"
        f"Headless: {'true' if request.headless else 'false'}\n"
        "Safety: dry-run ON",
        reply_markup=running_job_menu(),
    )
    asyncio.create_task(_notify_when_done(bot, chat_id, job))


async def _notify_when_done(bot: Bot, chat_id: int, job: BotJob) -> None:
    if job.task:
        try:
            await job.task
        except asyncio.CancelledError:
            pass

    await bot.send_message(
        chat_id,
        f"Run {job.id} {job.status.upper()}\n\n"
        f"{format_summary(job.summary)}\n\n"
        f"Report dir: {job.report_dir}",
    )

    if job.status == "completed":
        await _send_report_files(bot, chat_id, job.report_dir)
    elif job.log_path and job.log_path.exists():
        await bot.send_document(chat_id, FSInputFile(job.log_path), caption="Run log")


async def _send_report_files(bot: Bot, chat_id: int, report_dir: Path) -> None:
    summary = read_report_summary(report_dir)
    await bot.send_message(chat_id, f"Report: {report_dir.name}\n\n{format_summary(summary)}")
    files = report_files(report_dir)
    if not files:
        await bot.send_message(chat_id, "Report files were not found.")
        return
    for path in files:
        await bot.send_document(chat_id, FSInputFile(path), caption=path.name)


def _format_status() -> str:
    job = jobs.active_job
    if not job:
        return "No active test run."

    tail = "\n".join(list(job.output_tail)[-8:])
    if tail:
        tail = "\n\nLatest output:\n" + tail[-1500:]
    return (
        f"Active run: {job.id}\n"
        f"Status: {job.status}\n"
        f"Scope: {job.request.label}\n"
        f"Started: {job.started_at or 'queued'}"
        f"{tail}"
    )


def _format_users() -> str:
    return (
        "Bot access\n\n"
        f"Admins: {', '.join(map(str, sorted(auth.admin_ids()))) or 'none'}\n"
        f"Users: {', '.join(map(str, sorted(auth.regular_user_ids()))) or 'none'}\n"
        f"Max regular users: {auth.config.max_regular_users}\n\n"
        "Admin commands:\n"
        "/add_user 123456789\n"
        "/remove_user 123456789"
    )


def _help_text(*, is_admin: bool) -> str:
    text = (
        "Commands\n\n"
        "/menu - open buttons\n"
        "/login CODE - join as a regular user\n"
        "/admin_login CODE - one-time admin bootstrap\n"
        "/run_all - run all tests\n"
        "/run_simple - run simple tests\n"
        "/run_complex - run complex tests\n"
        "/run_tag betting - run one category\n"
        "/run_id simple-1 - run one test\n"
        "/run_ids simple-1,complex-3 - run selected tests\n"
        "/status - current run\n"
        "/reports - send latest report\n"
        "/whoami - show your Telegram ID\n\n"
        "Telegram runs are always dry-run safe. No real deposit or real bet is submitted."
    )
    if is_admin:
        text += (
            "\n\nAdmin\n"
            "/cancel - stop active run\n"
            "/users - list access\n"
            "/add_user 123456789\n"
            "/remove_user 123456789\n"
            "/setcommands - refresh Telegram command menu"
        )
    return text


async def _install_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="menu", description="Open QA bot menu"),
            BotCommand(command="login", description="Join with invite code"),
            BotCommand(command="admin_login", description="Create first admin"),
            BotCommand(command="run_all", description="Run all tests"),
            BotCommand(command="run_simple", description="Run simple tests"),
            BotCommand(command="run_complex", description="Run complex tests"),
            BotCommand(command="run_tag", description="Run tests by category"),
            BotCommand(command="run_id", description="Run a specific test ID"),
            BotCommand(command="status", description="Show current run"),
            BotCommand(command="reports", description="Send latest report"),
            BotCommand(command="whoami", description="Show your Telegram ID"),
            BotCommand(command="help", description="Show help"),
        ]
    )


def _load_available_tags(xlsx: str) -> list[str]:
    try:
        tags = sorted({tag for case in load_test_cases(xlsx) for tag in case.tags})
    except Exception:
        tags = []
    return tags or [
        "auth",
        "responsible-gambling",
        "registration",
        "betting",
        "casino",
        "virtual-sports",
        "ui",
    ]


async def main() -> None:
    global auth, jobs, settings, available_tags

    load_dotenv()
    settings = BotSettings.from_env()
    auth_config = BotAuthConfig.from_env()
    auth = AuthService(auth_config, AccessStore(auth_config.state_path))
    jobs = JobManager(settings.report_root, workspace=Path(__file__).resolve().parents[1])
    available_tags = _load_available_tags(settings.xlsx)

    bot = Bot(token=settings.token)
    dp = Dispatcher()
    dp.include_router(router)
    await _install_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
