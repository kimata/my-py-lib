"""ワーカーライフサイクル管理モジュール。

軽量なシャットダウン状態管理と、ワーカー終了待機を組み合わせて扱います。

使用例:
    from my_lib.lifecycle import LifecycleManager

    manager = LifecycleManager()
    manager.setup_signal_handler()

    # ワーカーを登録
    future1 = executor.submit(worker_func1, ...)
    manager.register_worker("worker1", future1)

    future2 = executor.submit(worker_func2, ...)
    manager.register_worker("worker2", future2)

    # シャットダウンを待機
    failed_count = manager.shutdown()
"""

from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass, field
from typing import Any

from my_lib.lifecycle.shutdown import ShutdownController
from my_lib.lifecycle.signals import install_double_tap_shutdown_handlers
from my_lib.lifecycle.workers import WorkerSupervisor


@dataclass  # NOTE: 内部状態を更新するため frozen=False
class LifecycleManager:
    """ワーカーライフサイクル管理クラス

    複数のワーカー（Thread または Future）を登録し、
    一括でシャットダウン処理を行います。

    Attributes:
        worker_names: 登録可能なワーカー名のタプル（オプション）
    """

    worker_names: tuple[str, ...] = ()
    _shutdown: ShutdownController = field(default_factory=ShutdownController, init=False, repr=False)
    _workers: WorkerSupervisor = field(init=False, repr=False)
    _signal_registered: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """補助オブジェクトを初期化する。"""
        self._workers = WorkerSupervisor(worker_names=self.worker_names)

    def register_worker(self, name: str, worker: threading.Thread | Any) -> None:
        """ワーカーを登録する

        Args:
            name: ワーカー名
            worker: Thread または Future オブジェクト
        """
        self._workers.register_worker(name, worker)

    def unregister_worker(self, name: str) -> None:
        """ワーカーの登録を解除する

        Args:
            name: ワーカー名
        """
        self._workers.unregister_worker(name)

    def request_termination(self, exit_reason: str = "shutdown") -> None:
        """終了をリクエストする

        登録されたすべてのワーカーに終了シグナルを送信します。
        """
        self._shutdown.request_termination(exit_reason)

    def request_shutdown(self, exit_reason: str = "shutdown") -> None:
        """互換 API としてシャットダウンを要求する。"""
        self.request_termination(exit_reason)

    def is_termination_requested(self) -> bool:
        """終了がリクエストされているかを返す"""
        return self._shutdown.is_termination_requested()

    def is_shutdown_requested(self) -> bool:
        """互換 API としてシャットダウン要求済みかを返す。"""
        return self.is_termination_requested()

    def get_exit_reason(self) -> str | None:
        """終了理由を返す。"""
        return self._shutdown.get_exit_reason()

    def reset(self) -> None:
        """終了フラグをリセットする"""
        self._shutdown.reset()

    @property
    def termination_event(self) -> threading.Event:
        """終了イベントを取得する

        ワーカー内で終了を待機するために使用します。

        Returns:
            終了イベント
        """
        return self._shutdown.termination_event

    def wait_for_termination(self, timeout: float | None = None) -> bool:
        """終了リクエストを待機する

        Args:
            timeout: タイムアウト秒数（None で無制限）

        Returns:
            終了がリクエストされた場合 True、タイムアウトの場合 False
        """
        return self._shutdown.wait_for_termination(timeout=timeout)

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """互換 API としてシャットダウン要求を待機する。"""
        return self.wait_for_termination(timeout=timeout)

    def wait_for_workers(self, timeout: float = 30.0) -> bool:
        """すべてのワーカーの終了を待機する

        Args:
            timeout: 各ワーカーのタイムアウト秒数

        Returns:
            すべてのワーカーが正常終了した場合 True
        """
        return self._workers.wait_for_workers(timeout=timeout)

    def shutdown(self, timeout: float = 30.0) -> int:
        """シャットダウン処理を実行する

        1. 終了をリクエスト
        2. すべてのワーカーの終了を待機
        3. 失敗したワーカー数を返す

        Args:
            timeout: 各ワーカーのタイムアウト秒数

        Returns:
            失敗したワーカー数
        """
        self.request_termination()
        failed_count = self._workers.shutdown(timeout=timeout)
        logging.info("シャットダウンが完了しました。失敗ワーカー数: %d", failed_count)
        return failed_count

    def setup_signal_handler(
        self, signals: tuple[signal.Signals, ...] = (signal.SIGTERM, signal.SIGINT)
    ) -> None:
        """シグナルハンドラを設定する

        指定されたシグナルを受信すると、終了をリクエストします。

        Args:
            signals: 処理するシグナルのタプル
        """
        if self._signal_registered:
            logging.warning("シグナルハンドラは既に登録されています")
            return

        install_double_tap_shutdown_handlers(
            self._shutdown,
            logger=logging.getLogger(__name__),
            signals=signals,
        )

        for sig in signals:
            logging.debug("シグナルハンドラを登録しました: %s", sig.name)

        self._signal_registered = True

    def get_worker_count(self) -> int:
        """登録されているワーカー数を返す"""
        return self._workers.get_worker_count()

    def get_worker_names(self) -> list[str]:
        """登録されているワーカー名のリストを返す"""
        return self._workers.get_worker_names()


# デフォルトのシングルトンインスタンス
_default_instance: LifecycleManager | None = None


def get_default() -> LifecycleManager:
    """デフォルトのシングルトンインスタンスを取得する"""
    global _default_instance
    if _default_instance is None:
        _default_instance = LifecycleManager()
    return _default_instance


def reset_default() -> None:
    """デフォルトインスタンスをリセットする（主にテスト用）"""
    global _default_instance
    _default_instance = None
