"""汎用シャットダウン状態管理。"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ShutdownController:
    """シャットダウン状態と終了理由を扱う軽量コントローラ。"""

    _shutdown_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _exit_reason: str | None = field(default=None, init=False, repr=False)

    def request_shutdown(self, exit_reason: str = "shutdown") -> None:
        """シャットダウンを要求する。"""
        self._exit_reason = exit_reason
        self._shutdown_event.set()
        logger.info("シャットダウンが要求されました (reason: %s)", exit_reason)

    def request_termination(self, exit_reason: str = "shutdown") -> None:
        """互換 API として終了を要求する。"""
        self.request_shutdown(exit_reason)

    def is_shutdown_requested(self) -> bool:
        """シャットダウン要求済みかを返す。"""
        return self._shutdown_event.is_set()

    def is_termination_requested(self) -> bool:
        """互換 API として終了要求済みかを返す。"""
        return self.is_shutdown_requested()

    def get_exit_reason(self) -> str | None:
        """終了理由を返す。"""
        return self._exit_reason

    @property
    def shutdown_event(self) -> threading.Event:
        """シャットダウンイベントを返す。"""
        return self._shutdown_event

    @property
    def termination_event(self) -> threading.Event:
        """互換 API として終了イベントを返す。"""
        return self._shutdown_event

    def reset(self) -> None:
        """シャットダウン状態を初期化する。"""
        self._shutdown_event.clear()
        self._exit_reason = None
        logger.debug("シャットダウン状態をリセットしました")

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """シャットダウン要求が入るまで待機する。"""
        return self._shutdown_event.wait(timeout=timeout)

    def wait_for_termination(self, timeout: float | None = None) -> bool:
        """互換 API として終了要求を待機する。"""
        return self.wait_for_shutdown(timeout=timeout)
