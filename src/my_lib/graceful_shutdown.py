"""Graceful shutdown 管理モジュール

Ctrl+C (SIGINT) によるグレースフルシャットダウンを管理します。
シグナルを受信すると確認プロンプトを表示し、ユーザーの応答に応じて
シャットダウンフラグを設定します。
"""

from __future__ import annotations

import logging
from typing import Protocol

from my_lib.lifecycle.shutdown import ShutdownController
from my_lib.lifecycle.signals import install_interactive_shutdown_handler


class LiveDisplayProtocol(Protocol):
    """Rich Live 表示のプロトコル"""

    def pause_live(self) -> None: ...
    def resume_live(self) -> None: ...


class NullLiveDisplay:
    """Live 表示がない環境用の Null Object"""

    def pause_live(self) -> None:
        pass

    def resume_live(self) -> None:
        pass


class GracefulShutdown:
    """Graceful shutdown 管理クラス

    使用例:
        shutdown = GracefulShutdown()
        shutdown.setup_signal_handler()
        shutdown.set_live_display(handle)  # Rich Live 対応オブジェクト

        while not shutdown.is_requested():
            # 処理を続行
            ...
    """

    def __init__(self) -> None:
        """インスタンスを初期化する"""
        self._shutdown = ShutdownController()
        self._live_display: LiveDisplayProtocol = NullLiveDisplay()

    def is_requested(self) -> bool:
        """シャットダウンがリクエストされているかを返す"""
        return self._shutdown.is_shutdown_requested()

    def request(self) -> None:
        """シャットダウンをリクエストする"""
        self._shutdown.request_shutdown("interactive_confirmed")

    def reset(self) -> None:
        """シャットダウンフラグをリセットする"""
        self._shutdown.reset()

    def set_live_display(self, live_display: LiveDisplayProtocol) -> None:
        """Rich Live 表示オブジェクトを設定する

        シグナルハンドラ内で pause_live/resume_live を呼び出すために必要。
        """
        self._live_display = live_display

    def setup_signal_handler(self) -> None:
        """SIGINT シグナルハンドラを設定する"""
        install_interactive_shutdown_handler(
            self._shutdown,
            live_display=self._live_display,
            logger=logging.getLogger(__name__),
            on_confirm=self._suppress_urllib3_warning,
        )

    @staticmethod
    def _suppress_urllib3_warning() -> None:
        """終了確認後に接続エラー WARNING を抑制する。"""
        logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


# デフォルトのシングルトンインスタンス
_default_instance: GracefulShutdown | None = None


def get_default() -> GracefulShutdown:
    """デフォルトのシングルトンインスタンスを取得する"""
    global _default_instance
    if _default_instance is None:
        _default_instance = GracefulShutdown()
    return _default_instance


# 便利な関数（デフォルトインスタンスを使用）
def is_shutdown_requested() -> bool:
    """シャットダウンがリクエストされているかを返す（デフォルトインスタンス）"""
    return get_default().is_requested()


def request_shutdown() -> None:
    """シャットダウンをリクエストする（デフォルトインスタンス）"""
    get_default().request()


def reset_shutdown_flag() -> None:
    """シャットダウンフラグをリセットする（デフォルトインスタンス）"""
    get_default().reset()


def setup_signal_handler() -> None:
    """SIGINT シグナルハンドラを設定する（デフォルトインスタンス）"""
    get_default().setup_signal_handler()


def set_live_display(live_display: LiveDisplayProtocol) -> None:
    """Rich Live 表示オブジェクトを設定する（デフォルトインスタンス）"""
    get_default().set_live_display(live_display)
