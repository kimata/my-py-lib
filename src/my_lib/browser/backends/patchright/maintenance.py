"""Patchright バックエンドの保守操作実装。

キャッシュ・履歴・GC のクリアを CDP セッション経由で行う。CDP の詳細は
このモジュール内にのみ閉じ込め、`Maintenance` Protocol として意味的操作を公開する。
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patchright.sync_api import BrowserContext as PwContext
    from patchright.sync_api import Page as PwPage


class PatchrightMaintenance:
    """CDP セッション経由の保守操作。"""

    def __init__(self, context: PwContext, page: PwPage) -> None:
        self._context = context
        self._page = page

    def _send(self, method: str, failure_message: str) -> None:
        # NOTE: 一時セッションは送信後に detach する。attach したままだと
        #       Node ドライバ側に CDPSession が呼び出しごとに残る。
        try:
            cdp = self._context.new_cdp_session(self._page)
        except Exception:
            logging.warning(failure_message)
            return
        try:
            cdp.send(method)
        except Exception:
            logging.warning(failure_message)
        finally:
            with contextlib.suppress(Exception):
                cdp.detach()

    def clear_cache(self) -> None:
        self._send("Network.clearBrowserCache", "Failed to clear cache")

    def clear_history(self) -> None:
        self._send("Page.resetNavigationHistory", "Failed to clear navigation history")

    def collect_garbage(self) -> None:
        self._send("HeapProfiler.collectGarbage", "Failed to collect garbage")
