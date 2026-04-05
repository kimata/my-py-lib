"""ワーカー終了待機の補助機能。"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkerSupervisor:
    """登録済みワーカーの終了待機を管理する。"""

    worker_names: tuple[str, ...] = ()

    _workers: dict[str, threading.Thread | Future[Any]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def register_worker(self, name: str, worker: threading.Thread | Future[Any]) -> None:
        """ワーカーを登録する。"""
        with self._lock:
            if self.worker_names and name not in self.worker_names:
                logger.warning("未知のワーカー名です: %s (expected: %s)", name, self.worker_names)
            self._workers[name] = worker
            logger.debug("ワーカーを登録しました: %s", name)

    def unregister_worker(self, name: str) -> None:
        """ワーカー登録を解除する。"""
        with self._lock:
            if name in self._workers:
                del self._workers[name]
                logger.debug("ワーカー登録を解除しました: %s", name)

    def snapshot(self) -> dict[str, threading.Thread | Future[Any]]:
        """現在の登録ワーカーのコピーを返す。"""
        with self._lock:
            return self._workers.copy()

    def wait_for_workers(self, timeout: float = 30.0) -> bool:
        """すべてのワーカーの終了を待機する。"""
        all_completed = True

        for name, worker in self.snapshot().items():
            logger.info("ワーカー終了待機: %s", name)
            try:
                if isinstance(worker, threading.Thread):
                    worker.join(timeout=timeout)
                    if worker.is_alive():
                        logger.warning("ワーカーがタイムアウト内に終了しませんでした: %s", name)
                        all_completed = False
                else:
                    try:
                        worker.result(timeout=timeout)
                    except TimeoutError:
                        logger.warning("ワーカーがタイムアウト内に完了しませんでした: %s", name)
                        all_completed = False
                    except Exception as exc:
                        logger.warning("ワーカーが失敗しました: %s (%s)", name, exc)
                        all_completed = False
            except Exception as exc:
                logger.warning("ワーカー待機中にエラーが発生しました: %s (%s)", name, exc)
                all_completed = False

        return all_completed

    def shutdown(self, timeout: float = 30.0) -> int:
        """ワーカーの終了を待機し、失敗数を返す。"""
        failed_count = 0

        for name, worker in self.snapshot().items():
            logger.info("ワーカー終了待機: %s", name)
            try:
                if isinstance(worker, threading.Thread):
                    worker.join(timeout=timeout)
                    if worker.is_alive():
                        logger.warning("ワーカーがタイムアウト内に終了しませんでした: %s", name)
                        failed_count += 1
                else:
                    try:
                        result = worker.result(timeout=timeout)
                        if result != 0:
                            logger.warning("ワーカーが異常終了コードを返しました: %s (%s)", name, result)
                            failed_count += 1
                    except TimeoutError:
                        logger.warning("ワーカーがタイムアウト内に完了しませんでした: %s", name)
                        failed_count += 1
                    except Exception as exc:
                        logger.warning("ワーカーが失敗しました: %s (%s)", name, exc)
                        failed_count += 1
            except Exception as exc:
                logger.warning("ワーカー終了処理でエラーが発生しました: %s (%s)", name, exc)
                failed_count += 1

        return failed_count

    def get_worker_count(self) -> int:
        """登録ワーカー数を返す。"""
        return len(self.snapshot())

    def get_worker_names(self) -> list[str]:
        """登録ワーカー名一覧を返す。"""
        return list(self.snapshot().keys())
