"""ワーカーライフサイクル管理モジュール

複数のワーカースレッド/Future のライフサイクルを一元管理します。
シグナルハンドラと連携して、グレースフルシャットダウンを実現します。

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
import sys
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import FrameType


@dataclass  # NOTE: _workers, _should_terminate 等を更新するため frozen=False
class LifecycleManager:
    """ワーカーライフサイクル管理クラス

    複数のワーカー（Thread または Future）を登録し、
    一括でシャットダウン処理を行います。

    Attributes:
        worker_names: 登録可能なワーカー名のタプル（オプション）
    """

    worker_names: tuple[str, ...] = ()

    _should_terminate: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _workers: dict[str, threading.Thread | Future[Any]] = field(default_factory=dict, init=False, repr=False)
    _shutdown_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _signal_registered: bool = field(default=False, init=False, repr=False)

    def register_worker(self, name: str, worker: threading.Thread | Future[Any]) -> None:
        """ワーカーを登録する

        Args:
            name: ワーカー名
            worker: Thread または Future オブジェクト
        """
        with self._shutdown_lock:
            if self.worker_names and name not in self.worker_names:
                logging.warning("Unknown worker name: %s (expected: %s)", name, self.worker_names)
            self._workers[name] = worker
            logging.debug("Worker registered: %s", name)

    def unregister_worker(self, name: str) -> None:
        """ワーカーの登録を解除する

        Args:
            name: ワーカー名
        """
        with self._shutdown_lock:
            if name in self._workers:
                del self._workers[name]
                logging.debug("Worker unregistered: %s", name)

    def request_termination(self) -> None:
        """終了をリクエストする

        登録されたすべてのワーカーに終了シグナルを送信します。
        """
        logging.info("Termination requested")
        self._should_terminate.set()

    def is_termination_requested(self) -> bool:
        """終了がリクエストされているかを返す"""
        return self._should_terminate.is_set()

    def reset(self) -> None:
        """終了フラグをリセットする"""
        self._should_terminate.clear()

    @property
    def termination_event(self) -> threading.Event:
        """終了イベントを取得する

        ワーカー内で終了を待機するために使用します。

        Returns:
            終了イベント
        """
        return self._should_terminate

    def wait_for_termination(self, timeout: float | None = None) -> bool:
        """終了リクエストを待機する

        Args:
            timeout: タイムアウト秒数（None で無制限）

        Returns:
            終了がリクエストされた場合 True、タイムアウトの場合 False
        """
        return self._should_terminate.wait(timeout=timeout)

    def wait_for_workers(self, timeout: float = 30.0) -> bool:
        """すべてのワーカーの終了を待機する

        Args:
            timeout: 各ワーカーのタイムアウト秒数

        Returns:
            すべてのワーカーが正常終了した場合 True
        """
        all_completed = True

        with self._shutdown_lock:
            workers_copy = self._workers.copy()

        for name, worker in workers_copy.items():
            logging.info("Waiting for worker: %s", name)
            try:
                if isinstance(worker, threading.Thread):
                    worker.join(timeout=timeout)
                    if worker.is_alive():
                        logging.warning("Worker %s did not terminate within timeout", name)
                        all_completed = False
                elif isinstance(worker, Future):
                    try:
                        worker.result(timeout=timeout)
                    except TimeoutError:
                        logging.warning("Worker %s did not complete within timeout", name)
                        all_completed = False
                    except Exception as e:
                        logging.warning("Worker %s failed with error: %s", name, e)
            except Exception as e:
                logging.warning("Error waiting for worker %s: %s", name, e)
                all_completed = False

        return all_completed

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

        failed_count = 0

        with self._shutdown_lock:
            workers_copy = self._workers.copy()

        for name, worker in workers_copy.items():
            logging.info("Waiting for worker to finish: %s", name)
            try:
                if isinstance(worker, threading.Thread):
                    worker.join(timeout=timeout)
                    if worker.is_alive():
                        logging.warning("Worker %s did not terminate within timeout", name)
                        failed_count += 1
                elif isinstance(worker, Future):
                    try:
                        result = worker.result(timeout=timeout)
                        if result != 0:
                            logging.warning("Worker %s returned error code: %s", name, result)
                            failed_count += 1
                    except TimeoutError:
                        logging.warning("Worker %s did not complete within timeout", name)
                        failed_count += 1
                    except Exception as e:
                        logging.warning("Worker %s failed with error: %s", name, e)
                        failed_count += 1
            except Exception as e:
                logging.warning("Error during shutdown of worker %s: %s", name, e)
                failed_count += 1

        logging.info("Shutdown complete. Failed workers: %d", failed_count)
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
            logging.warning("Signal handler already registered")
            return

        for sig in signals:
            signal.signal(sig, self._signal_handler)
            logging.debug("Signal handler registered for %s", sig.name)

        self._signal_registered = True

    def _signal_handler(self, signum: int, _frame: FrameType | None) -> Any:
        """シグナルハンドラ"""
        sig_name = signal.Signals(signum).name
        logging.info("Received signal: %s", sig_name)

        if self._should_terminate.is_set():
            logging.warning("Already terminating, forcing exit")
            sys.exit(1)

        self.request_termination()

    def get_worker_count(self) -> int:
        """登録されているワーカー数を返す"""
        return len(self._workers)

    def get_worker_names(self) -> list[str]:
        """登録されているワーカー名のリストを返す"""
        with self._shutdown_lock:
            return list(self._workers.keys())


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
