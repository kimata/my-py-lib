"""Graceful shutdown 管理モジュール

Ctrl+C (SIGINT) によるグレースフルシャットダウンを管理します。
シグナルを受信すると確認プロンプトを表示し、ユーザーの応答に応じて
シャットダウンフラグを設定します。
"""

from __future__ import annotations

import logging
import signal
import sys
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from types import FrameType


class LiveDisplayProtocol(Protocol):
    """Rich Live 表示のプロトコル"""

    def pause_live(self) -> None: ...
    def resume_live(self) -> None: ...


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
        self._shutdown_requested: bool = False
        self._live_display: LiveDisplayProtocol | None = None

    def is_requested(self) -> bool:
        """シャットダウンがリクエストされているかを返す"""
        return self._shutdown_requested

    def request(self) -> None:
        """シャットダウンをリクエストする"""
        self._shutdown_requested = True

    def reset(self) -> None:
        """シャットダウンフラグをリセットする"""
        self._shutdown_requested = False

    def set_live_display(self, live_display: LiveDisplayProtocol | None) -> None:
        """Rich Live 表示オブジェクトを設定する

        シグナルハンドラ内で pause_live/resume_live を呼び出すために必要。
        """
        self._live_display = live_display

    def setup_signal_handler(self) -> None:
        """SIGINT シグナルハンドラを設定する"""
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, _signum: int, _frame: FrameType | None) -> Any:
        """Ctrl+C シグナルハンドラ"""
        # 既にシャットダウンリクエスト中の場合は強制終了
        if self._shutdown_requested:
            logging.warning("強制終了します")
            sys.exit(1)

        try:
            # Rich Live を一時停止して入力を受け付ける
            if self._live_display is not None:
                self._live_display.pause_live()

            response = input("\n終了しますか？(y/N): ").strip().lower()
            if response == "y":
                self._shutdown_requested = True
                # urllib3 の接続エラー WARNING を抑制
                logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
                logging.info("終了リクエストを受け付けました。現在の処理が完了次第終了します...")
            else:
                logging.info("処理を継続します")

            # Rich Live を再開
            if self._live_display is not None:
                self._live_display.resume_live()
        except EOFError:
            # 入力が取得できない場合は継続
            logging.info("処理を継続します")
            if self._live_display is not None:
                self._live_display.resume_live()


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


def set_live_display(live_display: LiveDisplayProtocol | None) -> None:
    """Rich Live 表示オブジェクトを設定する（デフォルトインスタンス）"""
    get_default().set_live_display(live_display)
