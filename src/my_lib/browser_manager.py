#!/usr/bin/env python3
"""
Selenium ブラウザ管理クラス

単一ドライバーの遅延初期化とライフサイクル管理を提供します。
"""

from __future__ import annotations

import contextlib
import logging
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import selenium.webdriver.support.wait

import my_lib.chrome_util
import my_lib.selenium_util

if TYPE_CHECKING:
    from collections.abc import Iterator

    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait


@dataclass(frozen=True)
class BrowserProfile:
    """ブラウザ設定プロファイル

    BrowserManager の設定を集約するクラスです。
    複数のプロジェクトで共通の設定パターンを再利用できます。

    Attributes:
        name: Chrome プロファイル名
        data_dir: Selenium データディレクトリのパス
        wait_timeout: WebDriverWait のタイムアウト秒数（デフォルト: 5.0）
        use_undetected: undetected_chromedriver を使用するか（デフォルト: True）
        stealth_mode: ボット検出回避のための User-Agent 偽装を行うか（デフォルト: True）
        clear_profile_on_error: 起動エラー時にプロファイルを削除するか（デフォルト: False）
        max_retry: 起動エラー時のリトライ回数（デフォルト: 1）

    Example:
        >>> profile = BrowserProfile(
        ...     name="MyProfile",
        ...     data_dir=pathlib.Path("data/selenium"),
        ...     clear_profile_on_error=True,
        ...     max_retry=3,
        ... )
        >>> manager = BrowserManager.from_profile(profile)

    """

    name: str
    data_dir: pathlib.Path
    wait_timeout: float = 5.0
    use_undetected: bool = True
    stealth_mode: bool = True
    clear_profile_on_error: bool = False
    max_retry: int = 1


@dataclass(frozen=True)
class DriverInitialized:
    """ドライバー起動済み状態"""

    driver: WebDriver
    wait: WebDriverWait


@dataclass(frozen=True)
class DriverUninitialized:
    """ドライバー未起動状態"""

    pass


@dataclass  # NOTE: _driver_state を更新するため frozen=False
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
        stealth_mode: ボット検出回避のための User-Agent 偽装を行うか（デフォルト: True）

    Example:
        個別パラメータで作成::

            >>> manager = BrowserManager(
            ...     profile_name="MyProfile",
            ...     data_dir=pathlib.Path("data/selenium"),
            ... )
            >>> driver, wait = manager.get_driver()
            >>> # ... 操作 ...
            >>> manager.quit()

        BrowserProfile で作成::

            >>> profile = BrowserProfile(
            ...     name="MyProfile",
            ...     data_dir=pathlib.Path("data/selenium"),
            ...     clear_profile_on_error=True,
            ... )
            >>> manager = BrowserManager.from_profile(profile)

        context manager として使用::

            >>> with BrowserManager.from_profile(profile) as manager:
            ...     driver, wait = manager.get_driver()
            ...     driver.get("https://example.com")
            ... # 自動的に quit() が呼ばれる

    """

    profile_name: str
    data_dir: pathlib.Path
    wait_timeout: float = 5.0
    use_undetected: bool = True
    clear_profile_on_error: bool = False
    max_retry_on_error: int = 1
    stealth_mode: bool = True

    # 内部状態
    _driver_state: DriverInitialized | DriverUninitialized = field(
        default_factory=DriverUninitialized, init=False, repr=False
    )

    @classmethod
    def from_profile(cls, profile: BrowserProfile) -> BrowserManager:
        """BrowserProfile からインスタンスを作成

        Args:
            profile: ブラウザ設定プロファイル

        Returns:
            BrowserManager インスタンス

        """
        return cls(
            profile_name=profile.name,
            data_dir=profile.data_dir,
            wait_timeout=profile.wait_timeout,
            use_undetected=profile.use_undetected,
            clear_profile_on_error=profile.clear_profile_on_error,
            max_retry_on_error=profile.max_retry,
            stealth_mode=profile.stealth_mode,
        )

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
        if isinstance(self._driver_state, DriverInitialized):
            return (self._driver_state.driver, self._driver_state.wait)

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

                driver = my_lib.selenium_util.create_driver(
                    self.profile_name,
                    self.data_dir,
                    use_undetected=self.use_undetected,
                    stealth_mode=self.stealth_mode,
                )
                wait = selenium.webdriver.support.wait.WebDriverWait(driver, self.wait_timeout)

                my_lib.selenium_util.clear_cache(driver)

                self._driver_state = DriverInitialized(driver=driver, wait=wait)

                logging.info("Selenium ドライバーを起動しました (%s)", self.profile_name)
                return (driver, wait)
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
        return isinstance(self._driver_state, DriverInitialized)

    def quit(self, wait_sec: float = 5) -> None:
        """ドライバーを終了

        ドライバーが未起動の場合は何もしません。

        Args:
            wait_sec: 終了待機時間（秒）

        """
        if isinstance(self._driver_state, DriverInitialized):
            logging.info("Selenium ドライバーを終了しています (%s)...", self.profile_name)
            my_lib.selenium_util.quit_driver_gracefully(self._driver_state.driver, wait_sec=wait_sec)
            self._driver_state = DriverUninitialized()

            # Chrome が正常終了してもロックファイルが残ることがあるためクリーンアップ
            my_lib.chrome_util.cleanup_profile_lock(self.profile_name, self.data_dir)

            logging.info("Selenium ドライバーを終了しました (%s)", self.profile_name)

    def clear_cache(self) -> None:
        """ブラウザキャッシュをクリア

        ドライバーが起動していない場合は何もしません。

        """
        if isinstance(self._driver_state, DriverInitialized):
            my_lib.selenium_util.clear_cache(self._driver_state.driver)

    def cleanup_profile_lock(self) -> None:
        """プロファイルのロックファイルをクリーンアップ

        Chrome が正常終了してもロックファイルが残ることがあるため、
        明示的にクリーンアップします。

        """
        my_lib.chrome_util.cleanup_profile_lock(self.profile_name, self.data_dir)

    @contextlib.contextmanager
    def driver(self) -> Iterator[WebDriver]:
        """ドライバーを取得するコンテキストマネージャ

        ドライバーを取得し、ブロック終了後にキャッシュをクリアします。
        ドライバー自体は終了しません（複数回使用可能）。

        Yields:
            WebDriver インスタンス

        Example:
            >>> with manager.driver() as driver:
            ...     driver.get("https://example.com")

        """
        driver, _ = self.get_driver()
        try:
            yield driver
        finally:
            self.clear_cache()

    def __enter__(self) -> BrowserManager:
        """コンテキストマネージャのエントリーポイント

        Returns:
            self

        """
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object,
    ) -> None:
        """コンテキストマネージャの終了処理

        ドライバーを終了し、ロックファイルをクリーンアップします。
        （quit() 内で cleanup_profile_lock も呼ばれる）

        """
        self.quit()
