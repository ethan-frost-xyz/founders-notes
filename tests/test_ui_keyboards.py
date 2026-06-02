"""Shared Telegram inline navigation helpers."""

from __future__ import annotations

from ui_keyboards import (
    BACK_LABEL,
    CALLBACK_JANITOR_EXIT,
    CALLBACK_SETTINGS_MENU,
    back_to_settings_markup,
    janitor_back_markup,
)


def test_back_to_settings_markup():
    kb = back_to_settings_markup()
    assert len(kb.inline_keyboard) == 1
    btn = kb.inline_keyboard[0][0]
    assert btn.text == BACK_LABEL
    assert btn.callback_data == CALLBACK_SETTINGS_MENU


def test_janitor_back_markup():
    kb = janitor_back_markup()
    btn = kb.inline_keyboard[0][0]
    assert btn.text == BACK_LABEL
    assert btn.callback_data == CALLBACK_JANITOR_EXIT
