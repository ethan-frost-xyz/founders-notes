"""Shared inline navigation controls for Telegram Settings, Ops, and Janitor."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CALLBACK_SETTINGS_MENU = "set:menu"
CALLBACK_JANITOR_EXIT = "janitor:exit"
BACK_LABEL = "← Back"


def back_to_settings_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(BACK_LABEL, callback_data=CALLBACK_SETTINGS_MENU)


def back_to_settings_row() -> list[InlineKeyboardButton]:
    return [back_to_settings_button()]


def back_to_settings_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([back_to_settings_row()])


def janitor_back_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(BACK_LABEL, callback_data=CALLBACK_JANITOR_EXIT)


def janitor_back_row() -> list[InlineKeyboardButton]:
    return [janitor_back_button()]


def janitor_back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([janitor_back_row()])
