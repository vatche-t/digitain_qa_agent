"""Inline keyboards for the Telegram QA bot."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(*, is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Run tests", callback_data="menu:run"),
            InlineKeyboardButton(text="Reports", callback_data="menu:reports"),
        ],
        [
            InlineKeyboardButton(text="Status", callback_data="job:status"),
            InlineKeyboardButton(text="Help", callback_data="menu:help"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="Admin", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def run_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="All", callback_data="run:all"),
                InlineKeyboardButton(text="Simple", callback_data="run:simple"),
                InlineKeyboardButton(text="Complex", callback_data="run:complex"),
            ],
            [
                InlineKeyboardButton(text="By category", callback_data="menu:categories"),
                InlineKeyboardButton(text="Specific ID", callback_data="menu:specific"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="menu:main")],
        ]
    )


def category_menu(tags: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(tags), 2):
        rows.append(
            [
                InlineKeyboardButton(text=tag, callback_data=f"run_tag:{tag}")
                for tag in tags[i : i + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text="Back", callback_data="menu:run")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reports_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Latest report", callback_data="reports:latest"),
                InlineKeyboardButton(text="List reports", callback_data="reports:list"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="menu:main")],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Users", callback_data="admin:users"),
                InlineKeyboardButton(text="Cancel run", callback_data="job:cancel"),
            ],
            [InlineKeyboardButton(text="Back", callback_data="menu:main")],
        ]
    )


def running_job_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Status", callback_data="job:status"),
                InlineKeyboardButton(text="Cancel", callback_data="job:cancel"),
            ]
        ]
    )


def confirm_run_menu(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Start", callback_data=f"confirm:{kind}"),
                InlineKeyboardButton(text="Cancel", callback_data="menu:run"),
            ]
        ]
    )
