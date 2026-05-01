"""Role and login helpers for the Telegram QA bot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def parse_id_set(value: str | None) -> set[int]:
    """Parse comma/space separated Telegram numeric IDs."""
    if not value:
        return set()

    ids: set[int] = set()
    for raw in value.replace(";", ",").replace(" ", ",").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.add(int(raw))
        except ValueError:
            continue
    return ids


@dataclass(frozen=True)
class BotAuthConfig:
    admin_ids: set[int]
    allowed_user_ids: set[int]
    admin_invite_code: str | None
    invite_code: str | None
    max_regular_users: int
    state_path: Path

    @classmethod
    def from_env(cls) -> "BotAuthConfig":
        return cls(
            admin_ids=parse_id_set(os.getenv("TELEGRAM_ADMIN_IDS")),
            allowed_user_ids=parse_id_set(os.getenv("TELEGRAM_ALLOWED_USER_IDS")),
            admin_invite_code=(os.getenv("TELEGRAM_ADMIN_INVITE_CODE") or "").strip() or None,
            invite_code=(os.getenv("TELEGRAM_INVITE_CODE") or "").strip() or None,
            max_regular_users=int(os.getenv("TELEGRAM_MAX_USERS", "2")),
            state_path=Path(os.getenv("TELEGRAM_STATE_PATH", ".bot-state/users.json")),
        )


class AccessStore:
    """Tiny JSON store for users invited through /login or /add_user."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._admin_ids: set[int] = set()
        self._user_ids: set[int] = set()
        self.load()

    @property
    def admin_ids(self) -> set[int]:
        return set(self._admin_ids)

    @property
    def user_ids(self) -> set[int]:
        return set(self._user_ids)

    def load(self) -> None:
        if not self.path.exists():
            self._admin_ids = set()
            self._user_ids = set()
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._admin_ids = {int(x) for x in payload.get("admin_ids", [])}
            self._user_ids = {int(x) for x in payload.get("user_ids", [])}
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            self._admin_ids = set()
            self._user_ids = set()

    def save(self) -> None:
        payload = {
            "admin_ids": sorted(self._admin_ids),
            "user_ids": sorted(self._user_ids),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_admin(self, user_id: int) -> None:
        self._admin_ids.add(int(user_id))
        self._user_ids.discard(int(user_id))
        self.save()

    def add(self, user_id: int) -> None:
        self._user_ids.add(int(user_id))
        self.save()

    def remove(self, user_id: int) -> None:
        self._user_ids.discard(int(user_id))
        self.save()


class AuthService:
    """Combines env-defined roles with the runtime invite store."""

    def __init__(self, config: BotAuthConfig, store: AccessStore) -> None:
        self.config = config
        self.store = store

    def is_admin(self, user_id: int | None) -> bool:
        return bool(user_id and user_id in self.admin_ids())

    def admin_ids(self) -> set[int]:
        return self.config.admin_ids | self.store.admin_ids

    def is_allowed(self, user_id: int | None) -> bool:
        if not user_id:
            return False
        return (
            user_id in self.config.admin_ids
            or user_id in self.config.allowed_user_ids
            or user_id in self.store.user_ids
        )

    def role_for(self, user_id: int | None) -> str:
        if self.is_admin(user_id):
            return "admin"
        if self.is_allowed(user_id):
            return "user"
        return "guest"

    def regular_user_ids(self) -> set[int]:
        return (
            self.config.allowed_user_ids
            | self.store.user_ids
        ) - self.admin_ids()

    def can_add_regular_user(self, user_id: int) -> bool:
        if user_id in self.config.admin_ids:
            return True
        return user_id in self.regular_user_ids() or (
            len(self.regular_user_ids()) < self.config.max_regular_users
        )

    def add_regular_user(self, user_id: int) -> tuple[bool, str]:
        if user_id in self.config.admin_ids:
            return True, "That ID is already an admin."
        if not self.can_add_regular_user(user_id):
            return (
                False,
                f"User limit reached: {self.config.max_regular_users} regular users.",
            )
        self.store.add(user_id)
        return True, "User allowed."

    def remove_regular_user(self, user_id: int) -> tuple[bool, str]:
        if user_id in self.config.allowed_user_ids:
            return False, "This user is configured in TELEGRAM_ALLOWED_USER_IDS."
        self.store.remove(user_id)
        return True, "User removed."

    def login_with_code(self, user_id: int, code: str) -> tuple[bool, str]:
        if not self.config.invite_code:
            return False, "Invite-code login is disabled."
        if code.strip() != self.config.invite_code:
            return False, "Invalid invite code."
        return self.add_regular_user(user_id)

    def login_admin_with_code(self, user_id: int, code: str) -> tuple[bool, str]:
        if self.admin_ids():
            return False, "Admin bootstrap is disabled because an admin already exists."
        if not self.config.admin_invite_code:
            return False, "Admin bootstrap code is not configured."
        if code.strip() != self.config.admin_invite_code:
            return False, "Invalid admin bootstrap code."
        self.store.add_admin(user_id)
        return True, "Admin created."
