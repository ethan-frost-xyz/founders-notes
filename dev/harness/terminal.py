"""Interactive async REPL for the mock Telegram harness."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.mock_session import DEFAULT_LOG_DIR, MockBotSession
from harness.scenario_runner import ScenarioRunner, load_scenario


class HarnessREPL:
    def __init__(
        self,
        *,
        llm_mode: str = "live",
        debug: bool = False,
        log_dir: Path | None = None,
        keep_sandbox: bool = False,
    ) -> None:
        self.llm_mode = "echo" if llm_mode == "echo" else "live"
        self.debug = debug
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.keep_sandbox = keep_sandbox
        self._session: MockBotSession | None = None
        self._sandbox = None

    async def run(self) -> None:
        print("Founders mock Telegram harness (type :quit to exit)")
        async with MockBotSession(llm_mode=self.llm_mode, log_dir=self.log_dir) as session:
            self._session = session
            while True:
                try:
                    line = await asyncio.to_thread(input, "you> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                text = line.strip()
                if not text:
                    continue
                if text.startswith(":"):
                    if await self._handle_command(text):
                        break
                    continue
                if text.isdigit() and self._last_buttons():
                    idx = int(text) - 1
                    labels, callbacks = self._last_buttons()
                    if 0 <= idx < len(callbacks):
                        replies = await session.tap_button(callbacks[idx])
                        self._print_replies(replies)
                        continue
                replies = await session.send(text)
                self._print_replies(replies)

    def _last_buttons(self) -> tuple[list[str], list[str]] | None:
        if not self._session or not self._session.replies:
            return None
        last = self._session.replies[-1]
        if not last.inline_keyboard_buttons:
            return None
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        markup = last.reply_markup
        if not isinstance(markup, InlineKeyboardMarkup):
            return None
        labels: list[str] = []
        callbacks: list[str] = []
        for row in markup.inline_keyboard:
            for btn in row:
                if isinstance(btn, InlineKeyboardButton):
                    labels.append(btn.text)
                    callbacks.append(btn.callback_data or "")
        return labels, callbacks

    def _print_replies(self, replies: list) -> None:
        for reply in replies:
            print(f"\nbot> {reply.text}\n")
            if reply.inline_keyboard_buttons:
                parts = [
                    f"[{i + 1}] {label}"
                    for i, label in enumerate(reply.inline_keyboard_buttons)
                ]
                print("  " + "  ".join(parts))
        if self.debug and self._session:
            for entry in self._session.tool_traces:
                tool = entry.get("tool", "?")
                print(f"  [tool: {tool}]")

    async def _handle_command(self, text: str) -> bool:
        assert self._session is not None
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in (":quit", ":q"):
            return True
        if cmd == ":reset":
            await self._session.reset()
            print("session reset")
            return False
        if cmd == ":debug":
            if arg.lower() in ("on", "1", "true"):
                self.debug = True
            elif arg.lower() in ("off", "0", "false"):
                self.debug = False
            print(f"debug={'on' if self.debug else 'off'}")
            return False
        if cmd == ":run":
            if not arg:
                print("usage: :run path/to/scenario.yaml")
                return False
            runner = ScenarioRunner(log_dir=self.log_dir, stub_llm=self.llm_mode == "echo")
            result = await runner.run(Path(arg), session=self._session)
            print(result.summary())
            return False
        if cmd == ":sandbox":
            if self._sandbox:
                print(self._sandbox.inspect())
            else:
                print("no active Janitor sandbox (use Janitor in a scenario with janitor_episode)")
            return False
        print(f"unknown command {cmd}")
        return False


def run_repl(**kwargs) -> None:
    asyncio.run(HarnessREPL(**kwargs).run())
