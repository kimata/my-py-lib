"""Patchright バックエンドの保守操作実装。

キャッシュ・履歴・GC のクリアを CDP セッション経由で行う。CDP の詳細は
このモジュール内にのみ閉じ込め、`Maintenance` Protocol として意味的操作を公開する。
"""

from __future__ import annotations

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

    def _cdp(self):
        return self._context.new_cdp_session(self._page)

    def clear_cache(self) -> None:
        try:
            cdp = self._cdp()
            cdp.send("Network.clearBrowserCache")
        except Exception:
            logging.warning("Failed to clear cache")

    def clear_history(self) -> None:
        try:
            cdp = self._cdp()
            cdp.send("Page.resetNavigationHistory")
        except Exception:
            logging.warning("Failed to clear navigation history")

    def collect_garbage(self) -> None:
        try:
            cdp = self._cdp()
            cdp.send("HeapProfiler.collectGarbage")
        except Exception:
            logging.warning("Failed to collect garbage")
