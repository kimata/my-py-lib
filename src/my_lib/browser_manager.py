#!/usr/bin/env python3
"""
Selenium ブラウザ管理クラス

単一ドライバーの遅延初期化とライフサイクル管理を提供します。
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import selenium.webdriver.support.wait

import my_lib.chrome_util
import my_lib.selenium_util

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait


@dataclass
class BrowserManager:
    """Selenium ブラウザ管理クラス（遅延初期化・単一ドライバー）

    ドライバーの遅延初期化、キャッシュクリア、グレースフルシャットダウンを
    統一されたインターフェースで提供します。

    Attributes:
        profile_name: Chrome プロファイル名
        data_dir: Selenium データディレクトリのパス
        wait_timeout: WebDriverWait のタイムアウト秒数（デフォルト: 5.0）
        use_undetected: undetected_chromedriver を使用するか（デフォルト: True）
        clear_profile_on_error: 起動エラー時にプロファイルを削除するか（デフォルト: False）
        max_retry_on_error: 起動エラー時のリトライ回数（デフォルト: 1）

    Example:
        >>> manager = BrowserManager(
        ...     profile_name="MyProfile",
        ...     data_dir=pathlib.Path("data/selenium"),
        ... )
        >>> driver, wait = manager.get_driver()
        >>> # ... 操作 ...
        >>> manager.quit()

    """

    profile_name: str
    data_dir: pathlib.Path
    wait_timeout: float = 5.0
    use_undetected: bool = True
    clear_profile_on_error: bool = False
    max_retry_on_error: int = 1

    # 内部状態
    _driver: WebDriver | None = field(default=None, init=False, repr=False)
    _wait: WebDriverWait | None = field(default=None, init=False, repr=False)

    def get_driver(self) -> tuple[WebDriver, WebDriverWait]:
        """ドライバーを取得（必要に応じて起動）

        ドライバーが未起動の場合は新規作成し、キャッシュをクリアします。
        既に起動済みの場合は既存のドライバーを返します。

        clear_profile_on_error=True の場合、起動失敗時にプロファイルを削除して
        max_retry_on_error 回までリトライします。

        Returns:
            (WebDriver, WebDriverWait) のタプル

        Raises:
            SeleniumError: ドライバーの起動に失敗した場合

        """
        if self._driver is not None and self._wait is not None:
            return (self._driver, self._wait)

        last_error: Exception | None = None
        max_attempts = self.max_retry_on_error + 1 if self.clear_profile_on_error else 1

        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    logging.info(
                        "Selenium ドライバーを再起動しています (%s) [リトライ %d/%d]...",
                        self.profile_name,
                        attempt,
                        self.max_retry_on_error,
                    )
                else:
                    logging.info("Selenium ドライバーを起動しています (%s)...", self.profile_name)

                self._driver = my_lib.selenium_util.create_driver(
                    self.profile_name,
                    self.data_dir,
                    use_undetected=self.use_undetected,
                )
                self._wait = selenium.webdriver.support.wait.WebDriverWait(self._driver, self.wait_timeout)

                my_lib.selenium_util.clear_cache(self._driver)

                logging.info("Selenium ドライバーを起動しました (%s)", self.profile_name)
                return (self._driver, self._wait)
            except Exception as e:
                last_error = e
                logging.exception("Selenium ドライバーの起動に失敗しました (%s)", self.profile_name)

                if self.clear_profile_on_error and attempt < max_attempts - 1:
                    logging.warning(
                        "プロファイルを削除してリトライします: %s (試行 %d/%d)",
                        self.profile_name,
                        attempt + 1,
                        max_attempts,
                    )
                    my_lib.chrome_util.delete_profile(self.profile_name, self.data_dir)
                    continue

                if self.clear_profile_on_error:
                    logging.warning("プロファイルを削除します: %s", self.profile_name)
                    my_lib.chrome_util.delete_profile(self.profile_name, self.data_dir)

        raise my_lib.selenium_util.SeleniumError(
            f"Selenium の起動に失敗しました: {last_error}"
        ) from last_error

    def has_driver(self) -> bool:
        """ドライバーが起動しているか確認

        Returns:
            ドライバーが起動済みの場合 True

        """
        return self._driver is not None

    def quit(self, wait_sec: float = 5) -> None:
        """ドライバーを終了

        ドライバーが未起動の場合は何もしません。

        Args:
            wait_sec: 終了待機時間（秒）

        """
        if self._driver is not None:
            logging.info("Selenium ドライバーを終了しています (%s)...", self.profile_name)
            my_lib.selenium_util.quit_driver_gracefully(self._driver, wait_sec=wait_sec)
            self._driver = None
            self._wait = None
            logging.info("Selenium ドライバーを終了しました (%s)", self.profile_name)

    def clear_cache(self) -> None:
        """ブラウザキャッシュをクリア

        ドライバーが起動していない場合は何もしません。

        """
        if self._driver is not None:
            my_lib.selenium_util.clear_cache(self._driver)
