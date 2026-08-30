"""ブラウザのライフサイクル管理。

`(driver, wait)` タプルに代わり、`BrowserManager` が `Browser` / `Page` を提供する。
遅延起動・プロファイル管理・セッションリトライ（`SessionError` 捕捉時のクリーン再起動）を担う。
バックエンド固有の型には一切依存しない。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

import my_lib.chrome_util
from my_lib.browser import factory
from my_lib.browser.exceptions import SessionError
from my_lib.browser.protocol import Browser, Page
from my_lib.browser.types import BrowserBackend, BrowserProfile

T = TypeVar("T")


class BrowserManager:
    """バックエンド非依存のブラウザ管理。"""

    def __init__(
        self,
        profile: BrowserProfile,
        backend: BrowserBackend = BrowserBackend.PATCHRIGHT,
    ) -> None:
        self._profile = profile
        self._backend = backend
        self._browser: Browser | None = None

    @property
    def profile(self) -> BrowserProfile:
        return self._profile

    def has_browser(self) -> bool:
        return self._browser is not None

    def get_browser(self) -> Browser:
        """ブラウザを取得する（未起動なら起動する）。"""
        if self._browser is None:
            self._browser = factory.launch(self._profile, self._backend)
        return self._browser

    def get_page(self) -> Page:
        """既定ページを取得する。"""
        browser = self.get_browser()
        return browser.new_page() if not browser.pages() else browser.pages()[0]

    def quit(self) -> None:
        """ブラウザを終了する。"""
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    def clear_profile(self) -> None:
        """プロファイルを削除する（次回起動時にクリーンな状態になる）。"""
        my_lib.chrome_util.delete_profile(self._profile.name, self._profile.data_dir)

    def restart_with_clean_profile(self) -> Browser:
        """ブラウザを終了しプロファイルを消して再起動する。"""
        self.quit()
        self.clear_profile()
        return self.get_browser()

    def run_with_session_retry(
        self,
        func: Callable[[], T],
        *,
        max_retries: int = 1,
        clear_profile_on_error: bool = True,
        on_retry: Callable[[int, int], None] | None = None,
    ) -> T:
        """`SessionError` 発生時にクリーン再起動してリトライする。"""
        attempt = 0
        while True:
            try:
                return func()
            except SessionError:
                attempt += 1
                if attempt > max_retries:
                    raise
                logging.warning(
                    "セッションエラーが発生しました。再起動してリトライします（%d/%d）",
                    attempt,
                    max_retries,
                )
                if on_retry is not None:
                    on_retry(attempt, max_retries)
                self.quit()
                if clear_profile_on_error:
                    self.clear_profile()
