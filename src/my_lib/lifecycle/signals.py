"""シグナル連携の補助機能。"""

from __future__ import annotations

import logging
import signal
import sys
from collections.abc import Callable, Iterable
from typing import Protocol

from my_lib.lifecycle.shutdown import ShutdownController


class SupportsLiveDisplay(Protocol):
    """Live 表示の一時停止と再開を持つオブジェクト。"""

    def pause_live(self) -> None: ...
    def resume_live(self) -> None: ...


def install_double_tap_shutdown_handlers(
    controller: ShutdownController,
    *,
    logger: logging.Logger,
    signals: Iterable[signal.Signals] = (signal.SIGINT, signal.SIGTERM),
    exit_fn: Callable[[int], None] = sys.exit,
    on_shutdown: Callable[[str], None] | None = None,
) -> None:
    """二度押しで強制終了するシグナルハンドラを登録する。"""
    force_exit_requested = False

    def signal_handler(signum: int, _frame: object) -> None:
        nonlocal force_exit_requested

        if force_exit_requested:
            logger.warning("強制終了します")
            exit_fn(1)

        force_exit_requested = True
        exit_reason = "sigterm" if signum == signal.SIGTERM else "sigint"
        logger.info("シャットダウン中 (%s)... (もう一度 Ctrl-C で強制終了)", exit_reason)
        controller.request_shutdown(exit_reason)
        if on_shutdown is not None:
            on_shutdown(exit_reason)

    for current_signal in signals:
        signal.signal(current_signal, signal_handler)


def install_interactive_shutdown_handler(
    controller: ShutdownController,
    *,
    live_display: SupportsLiveDisplay,
    logger: logging.Logger,
    confirmation_prompt: str = "\n終了しますか？(y/N): ",
    signal_to_handle: signal.Signals = signal.SIGINT,
    input_fn: Callable[[str], str] = input,
    exit_fn: Callable[[int], None] = sys.exit,
    confirmed_reason: str = "interactive_confirmed",
    on_confirm: Callable[[], None] | None = None,
) -> None:
    """確認付きの SIGINT ハンドラを登録する。"""

    def signal_handler(_signum: int, _frame: object) -> None:
        if controller.is_shutdown_requested():
            logger.warning("強制終了します")
            exit_fn(1)

        try:
            live_display.pause_live()
            response = input_fn(confirmation_prompt).strip().lower()
            if response == "y":
                controller.request_shutdown(confirmed_reason)
                if on_confirm is not None:
                    on_confirm()
                logger.info("終了リクエストを受け付けました。現在の処理が完了次第終了します...")
            else:
                logger.info("処理を継続します")
        except EOFError:
            logger.info("処理を継続します")
        finally:
            live_display.resume_live()

    signal.signal(signal_to_handle, signal_handler)
