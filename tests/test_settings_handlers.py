"""Settings tap UI: presets and callback_data length."""

from __future__ import annotations

from model_presets import MODEL_PRESETS, ROLE_LABELS
from settings_handlers import _role_preset_keyboard, settings_keyboard


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
    assert "deepseek-v4-pro" in labels
    assert "← Back" in labels
    assert "Type custom slug…" in labels
