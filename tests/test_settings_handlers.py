"""Settings tap UI: presets and callback_data length."""

from __future__ import annotations

from model_presets import MODEL_PRESETS, ROLE_LABELS
from settings_handlers import (
    _ops_keyboard,
    _role_preset_keyboard,
    _steps_keyboard,
    settings_keyboard,
)
from ui_keyboards import BACK_LABEL, CALLBACK_SETTINGS_MENU, back_to_settings_markup


def test_callback_data_under_telegram_limit():
    for role in ROLE_LABELS:
        for idx in range(len(MODEL_PRESETS.get(role, []))):
            data = f"set:p:{role}:{idx}"
            assert len(data.encode("utf-8")) <= 64, data
    kb = settings_keyboard()
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64, btn.callback_data


def test_role_keyboard_has_presets_and_back():
    kb = _role_preset_keyboard("librarian")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "mimo-v2.5-pro" in labels
    assert BACK_LABEL in labels
    assert "Type custom slug…" in labels


def test_ops_back_uses_shared_label():
    kb = back_to_settings_markup()
    btn = kb.inline_keyboard[0][0]
    assert btn.text == BACK_LABEL
    assert btn.callback_data == CALLBACK_SETTINGS_MENU


def test_all_settings_submenus_have_back():
    for kb in (_ops_keyboard(), _role_preset_keyboard("librarian"), _steps_keyboard()):
        labels = [btn.text for row in kb.inline_keyboard for btn in row]
        assert BACK_LABEL in labels
