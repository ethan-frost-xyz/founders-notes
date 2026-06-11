"""Telegram inline callback prefixes and action tokens."""

from __future__ import annotations

SET_PREFIX = "set:"
JANITOR_PREFIX = "janitor:"

CALLBACK_SET_STREAM = "set:stream"
CALLBACK_SET_OPS = "set:ops"
CALLBACK_SET_TEMP = "set:temp"

CALLBACK_JANITOR_RETRY = "janitor:retry"
CALLBACK_JANITOR_APPROVE = "janitor:approve"
CALLBACK_JANITOR_CONFIRM_OVERWRITE = "janitor:confirm_overwrite"
CALLBACK_JANITOR_PROMOTE = "janitor:promote"
CALLBACK_JANITOR_RETRY_EXPAND = "janitor:retry_expand"
CALLBACK_JANITOR_PUSH = "janitor:push"
CALLBACK_JANITOR_PUSH_SKIP = "janitor:push_skip"
CALLBACK_JANITOR_CANCEL = "janitor:cancel"

MODEL_ROLES = ("librarian", "retrieval", "janitor", "expand", "embed")
