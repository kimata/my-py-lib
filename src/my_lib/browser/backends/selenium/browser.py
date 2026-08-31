"""Selenium バックエンドの Browser 実装と launch（移行期の互換用）。

既存の `my_lib.selenium_util.create_driver` を用いてドライバを生成し、Protocol の
Browser として提供する。ログイン済みプロファイルを再利用する等、Selenium のままで
問題ないプロジェクトを、共有 store 層を Protocol 化した後も動かし続けるためのもの。
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

import my_lib.selenium_util
from my_lib.browser.backends.selenium.maintenance import SeleniumMaintenance
from my_lib.browser.backends.selenium.page import SeleniumPage
from my_lib.browser.exceptions import BrowserError
from my_lib.browser.types import BrowserProfile

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


class SeleniumBrowser:
    """単一の WebDriver を束ねる Browser 実装。"""

    def __init__(self, driver: WebDriver) -> None:
        self._driver = driver
        self._default_page = SeleniumPage(driver)

    @property
    def default_page(self) -> SeleniumPage:
        return self._default_page

    def new_page(self) -> SeleniumPage:
        # NOTE: Selenium は 1 ドライバ = 1 ページのモデル。追加ページが要る場合は tab() を使う。
        return self._default_page

    @contextlib.contextmanager
    def tab(self, url: str) -> Iterator[SeleniumPage]:
        original = self._driver.current_window_handle
        self._driver.execute_script("window.open('');")
        self._driver.switch_to.window(self._driver.window_handles[-1])
        try:
            self._driver.get(url)
            yield SeleniumPage(self._driver)
        finally:
            with contextlib.suppress(Exception):
                while len(self._driver.window_handles) > 1:
                    self._driver.switch_to.window(self._driver.window_handles[-1])
                    self._driver.close()
                self._driver.switch_to.window(original)
                time.sleep(0.1)

    def pages(self) -> list[SeleniumPage]:
        return [self._default_page]

    @property
    def maintenance(self) -> SeleniumMaintenance:
        return SeleniumMaintenance(self._driver)

    def close(self) -> None:
        my_lib.selenium_util.quit_driver_gracefully(self._driver)


def launch(profile: BrowserProfile) -> SeleniumBrowser:
    """既存 create_driver で Selenium ドライバを生成して Browser を返す。"""
    try:
        driver = my_lib.selenium_util.create_driver(
            profile.name,
            profile.data_dir,
            is_headless=profile.headless,
            stealth_mode=profile.stealth,
        )
    except Exception as e:
        # NOTE: 起動失敗を BrowserError に正規化する。
        raise BrowserError(str(e)) from e
    return SeleniumBrowser(driver)
