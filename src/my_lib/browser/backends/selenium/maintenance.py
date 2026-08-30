"""Selenium バックエンドの保守操作実装（execute_cdp_cmd をここに閉じ込める）。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


class SeleniumMaintenance:
    """CDP コマンド経由の保守操作。"""

    def __init__(self, driver: WebDriver) -> None:
        self._driver = driver

    def clear_cache(self) -> None:
        try:
            self._driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        except Exception:
            logging.warning("Failed to clear cache")

    def clear_history(self) -> None:
        try:
            self._driver.execute_cdp_cmd("Page.resetNavigationHistory", {})
        except Exception:
            logging.warning("Failed to clear navigation history")

    def collect_garbage(self) -> None:
        try:
            self._driver.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
        except Exception:
            logging.warning("Failed to collect garbage")
