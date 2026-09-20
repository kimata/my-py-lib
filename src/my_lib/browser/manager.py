"""ブラウザのライフサイクル管理。

`(driver, wait)` タプルに代わり、`BrowserManager` が `Browser` / `Page` を提供する。
遅延起動・プロファイル管理・セッションリトライ（`SessionError` 捕捉時のクリーン再起動）を担う。
バックエンド固有の型には一切依存しない。

Page はスコープ内でのみ存在する::

    with manager.page() as page:
        page.goto(url)
        ...
    # ここでタブは閉じられ、タブに紐づくリソースは全て解放される

スコープの単位は「1 つの作業」（1 商品・1 注文・1 検索）とし、巡回全体を 1 つの
スコープで包まないこと。タブの寿命を作業単位に限定することがリーク対策の本体である。
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Iterator
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

    @contextlib.contextmanager
    def page(self) -> Iterator[Page]:
        """新しいタブを開いて返し、with を抜けると閉じる（未起動ならブラウザを起動する）。"""
        with self.get_browser().page() as page:
            yield page

    @contextlib.contextmanager
    def tab(self, url: str) -> Iterator[Page]:
        """新しいタブで URL を開いて返し、with を抜けると閉じる。"""
        with self.get_browser().tab(url) as page:
            yield page

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
        """`SessionError` 発生時にクリーン再起動してリトライする。

        `func` は内部で `page()` スコープを開くこと（再起動後は新しいブラウザで
        スコープを開き直す必要があるため、Page を外から渡す形にはしない）。
        """
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
