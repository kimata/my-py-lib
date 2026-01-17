#!/usr/bin/env python3
"""
Selenium を Chrome Driver を使って動かします。

Usage:
  selenium_util.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import inspect
import io
import logging
import os
import pathlib
import random
import re
import signal
import subprocess
import time
from typing import TYPE_CHECKING, Any, Self, TypeVar

import PIL.Image
import psutil
import selenium
import selenium.common.exceptions
import selenium.webdriver.chrome.options
import selenium.webdriver.chrome.service
import selenium.webdriver.common.action_chains
import selenium.webdriver.common.by
import selenium.webdriver.common.keys
import selenium.webdriver.support.expected_conditions

import my_lib.chrome_util
import my_lib.time

if TYPE_CHECKING:
    import types
    from collections.abc import Callable

    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait

T = TypeVar("T")

WAIT_RETRY_COUNT: int = 1


class SeleniumError(Exception):
    """Selenium 関連エラーの基底クラス"""


def _get_chrome_version() -> int | None:
    try:
        result = subprocess.run(
            ["google-chrome", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        match = re.search(r"(\d+)\.", result.stdout)
        if match:
            return int(match.group(1))
    except Exception:
        logging.warning("Failed to detect Chrome version")
    return None


def _create_chrome_options(
    profile_name: str,
    chrome_data_path: pathlib.Path,
    log_path: pathlib.Path,
    is_headless: bool,
) -> selenium.webdriver.chrome.options.Options:
    """Chrome オプションを作成する

    Args:
        profile_name: プロファイル名
        chrome_data_path: Chrome データディレクトリのパス
        log_path: ログディレクトリのパス
        is_headless: ヘッドレスモードで起動するか

    Returns:
        設定済みの Chrome オプション

    """
    options = selenium.webdriver.chrome.options.Options()

    if is_headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker
    options.add_argument("--disable-gpu")

    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-plugins")

    options.add_argument("--no-first-run")

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1080")

    # NOTE: Accept-Language ヘッダーを日本語優先に設定
    options.add_experimental_option("prefs", {"intl.accept_languages": "ja-JP,ja,en-US,en"})

    options.add_argument("--user-data-dir=" + str(chrome_data_path / profile_name))

    options.add_argument("--enable-logging")
    options.add_argument("--v=1")

    chrome_log_file = log_path / f"chrome_{profile_name}.log"
    options.add_argument(f"--log-file={chrome_log_file!s}")

    if not is_headless:
        options.add_argument("--auto-open-devtools-for-tabs")

    return options


def _create_driver_impl(
    profile_name: str,
    data_path: pathlib.Path,
    is_headless: bool,
    use_subprocess: bool,
    use_undetected: bool,
) -> WebDriver:
    """WebDriver を作成する内部実装

    Args:
        profile_name: プロファイル名
        data_path: データディレクトリのパス
        is_headless: ヘッドレスモードで起動するか
        use_subprocess: サブプロセスで Chrome を起動するか（undetected_chromedriver のみ）
        use_undetected: undetected_chromedriver を使用するか

    Returns:
        WebDriver インスタンス

    """
    chrome_data_path = data_path / "chrome"
    log_path = data_path / "log"

    # NOTE: Pytest を並列実行できるようにする
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    if suffix is not None:
        profile_name += "." + suffix

    chrome_data_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    options = _create_chrome_options(profile_name, chrome_data_path, log_path, is_headless)

    service = selenium.webdriver.chrome.service.Service(
        service_args=["--verbose", f"--log-path={str(log_path / 'webdriver.log')!s}"],
    )

    if use_undetected:
        import undetected_chromedriver

        chrome_version = _get_chrome_version()

        # NOTE: user_multi_procs=True は既存の chromedriver ファイルが存在することを前提としているため、
        # ファイルが存在しない場合（CI環境の初回実行など）は False にする
        uc_data_path = pathlib.Path("~/.local/share/undetected_chromedriver").expanduser()
        use_multi_procs = uc_data_path.exists() and any(uc_data_path.glob("*chromedriver*"))

        driver = undetected_chromedriver.Chrome(
            service=service,
            options=options,
            use_subprocess=use_subprocess,
            version_main=chrome_version,
            user_multi_procs=use_multi_procs,
        )
    else:
        driver = selenium.webdriver.Chrome(
            service=service,
            options=options,
        )

    driver.set_page_load_timeout(30)

    # CDP を使って日本語ロケールを強制設定
    set_japanese_locale(driver)

    return driver


def create_driver(
    profile_name: str,
    data_path: pathlib.Path,
    is_headless: bool = True,
    clean_profile: bool = False,
    auto_recover: bool = True,
    use_undetected: bool = True,
    use_subprocess: bool = False,
) -> WebDriver:
    """Chrome WebDriver を作成する

    Args:
        profile_name: プロファイル名
        data_path: データディレクトリのパス
        is_headless: ヘッドレスモードで起動するか
        clean_profile: 起動前にロックファイルを削除するか
        auto_recover: プロファイル破損時に自動リカバリするか
        use_undetected: undetected_chromedriver を使用するか（デフォルト: True）
        use_subprocess: サブプロセスで Chrome を起動するか（undetected_chromedriver のみ）

    Raises:
        ValueError: use_undetected=False かつ use_subprocess=True の場合

    """
    if not use_undetected and use_subprocess:
        raise ValueError("use_subprocess=True は use_undetected=True の場合のみ有効です")

    # NOTE: ルートロガーの出力レベルを変更した場合でも Selenium 関係は抑制する
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.common.selenium_manager").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

    # NOTE: chrome_util の内部関数を使用（同一パッケージ内での使用は許容）
    actual_profile_name = my_lib.chrome_util._get_actual_profile_name(profile_name)
    profile_path = data_path / "chrome" / actual_profile_name

    # プロファイル健全性チェック
    health = my_lib.chrome_util._check_profile_health(profile_path)
    if not health.is_healthy:
        logging.warning("Profile health check failed: %s", ", ".join(health.errors))

        if health.has_lock_files and not (health.has_corrupted_json or health.has_corrupted_db):
            # ロックファイルのみの問題なら削除して続行
            logging.info("Cleaning up lock files only")
            my_lib.chrome_util._cleanup_profile_lock(profile_path)
        elif auto_recover and (health.has_corrupted_json or health.has_corrupted_db):
            # JSON または DB が破損している場合はプロファイルをリカバリ
            logging.warning("Profile is corrupted, attempting recovery")
            if my_lib.chrome_util._recover_corrupted_profile(profile_path):
                logging.info("Profile recovery successful, will create new profile")
            else:
                logging.error("Profile recovery failed")

    if clean_profile:
        my_lib.chrome_util._cleanup_profile_lock(profile_path)

    # NOTE: 1回だけ自動リトライ
    try:
        return _create_driver_impl(profile_name, data_path, is_headless, use_subprocess, use_undetected)
    except Exception as e:
        logging.warning("First attempt to create driver failed: %s", e)

        # コンテナ内で実行中の場合のみ、残った Chrome プロセスをクリーンアップ
        my_lib.chrome_util._cleanup_orphaned_chrome_processes_in_container()

        # プロファイルのロックファイルを削除
        my_lib.chrome_util._cleanup_profile_lock(profile_path)

        # 再度健全性チェック
        health = my_lib.chrome_util._check_profile_health(profile_path)
        if not health.is_healthy and auto_recover and (health.has_corrupted_json or health.has_corrupted_db):
            logging.warning("Profile still corrupted after first attempt, recovering")
            my_lib.chrome_util._recover_corrupted_profile(profile_path)

        return _create_driver_impl(profile_name, data_path, is_headless, use_subprocess, use_undetected)


def xpath_exists(driver: WebDriver, xpath: str) -> bool:
    return len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0


def get_text(
    driver: WebDriver,
    xpath: str,
    safe_text: str,
    wait: WebDriverWait[WebDriver] | None = None,
) -> str:
    if wait is not None:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
                (selenium.webdriver.common.by.By.XPATH, xpath)
            )
        )

    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0:
        return driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).text.strip()
    else:
        return safe_text


def input_xpath(
    driver: WebDriver,
    xpath: str,
    text: str,
    wait: WebDriverWait[WebDriver] | None = None,
    is_warn: bool = True,
) -> bool:
    if wait is not None:
        wait.until(
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (selenium.webdriver.common.by.By.XPATH, xpath)
            )
        )
        time.sleep(0.05)

    if xpath_exists(driver, xpath):
        driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).send_keys(text)
        return True
    else:
        if is_warn:
            logging.warning("Element is not found: %s", xpath)
        return False


def click_xpath(
    driver: WebDriver,
    xpath: str,
    wait: WebDriverWait[WebDriver] | None = None,
    is_warn: bool = True,
    move: bool = False,
) -> bool:
    if wait is not None:
        wait.until(
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (selenium.webdriver.common.by.By.XPATH, xpath)
            )
        )
        time.sleep(0.05)

    if xpath_exists(driver, xpath):
        elem = driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath)
        if move:
            action = selenium.webdriver.common.action_chains.ActionChains(driver)
            action.move_to_element(elem)
            action.perform()

        elem.click()
        return True
    else:
        if is_warn:
            logging.warning("Element is not found: %s", xpath)
        return False


def is_display(driver: WebDriver, xpath: str) -> bool:
    return (len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0) and (
        driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).is_displayed()
    )


def random_sleep(sec: float) -> None:
    RATIO = 0.8

    time.sleep((sec * RATIO) + (sec * (1 - RATIO) * 2) * random.random())  # noqa: S311


def with_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], bool | None] | None = None,
) -> T:
    """リトライ付きで関数を実行

    全て失敗した場合は最後の例外を再スロー。
    呼び出し側で try/except してエラー処理を行う。

    Args:
        func: 実行する関数
        max_retries: 最大リトライ回数
        delay: リトライ間の待機秒数
        exceptions: リトライ対象の例外タプル
        on_retry: リトライ時のコールバック (attempt, exception)
            - None または True を返すとリトライを継続
            - False を返すとリトライを中止して例外を再スロー

    Returns:
        成功時は関数の戻り値

    Raises:
        最後の例外を再スロー

    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                if on_retry:
                    should_continue = on_retry(attempt + 1, e)
                    if should_continue is False:
                        raise
                time.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in with_retry")


def with_session_retry(
    func: Callable[[], T],
    driver_name: str,
    data_dir: pathlib.Path,
    *,
    max_retries: int = 1,
    clear_profile_on_error: bool = True,
    on_retry: Callable[[int, int], None] | None = None,
    before_retry: Callable[[], None] | None = None,
) -> T:
    """InvalidSessionIdException 発生時にプロファイル削除してリトライ

    ブラウザのセッションが無効になった場合（クラッシュ等）、
    プロファイルを削除して再起動することで復旧を試みる。

    Args:
        func: 実行する関数
        driver_name: Chrome プロファイル名
        data_dir: Selenium データディレクトリ
        max_retries: 最大リトライ回数 (デフォルト: 1)
        clear_profile_on_error: エラー時にプロファイルを削除するか
        on_retry: リトライ時のコールバック (attempt, max_retries) - ステータス更新用
        before_retry: リトライ前のコールバック - quit_selenium() 呼び出し用

    Returns:
        成功時は関数の戻り値

    Raises:
        InvalidSessionIdException: リトライ上限に達した場合

    """

    def retry_handler(attempt: int, exception: Exception) -> bool | None:
        if before_retry:
            before_retry()

        if attempt <= max_retries and clear_profile_on_error:
            logging.warning(
                "セッションエラーが発生しました。プロファイルを削除してリトライします（%d/%d）",
                attempt,
                max_retries,
            )
            if on_retry:
                on_retry(attempt, max_retries)
            my_lib.chrome_util.delete_profile(driver_name, data_dir)
            return True
        return False

    return with_retry(
        func,
        max_retries=max_retries + 1,
        delay=0,
        exceptions=(selenium.common.exceptions.InvalidSessionIdException,),
        on_retry=retry_handler,
    )


def wait_patiently(
    driver: WebDriver,
    wait: WebDriverWait[WebDriver],
    target: Any,
) -> None:
    error: selenium.common.exceptions.TimeoutException | None = None
    for i in range(WAIT_RETRY_COUNT + 1):
        try:
            wait.until(target)
            return
        except selenium.common.exceptions.TimeoutException as e:
            logging.warning(
                "タイムアウトが発生しました。(%s in %s line %d)",
                inspect.stack()[1].function,
                inspect.stack()[1].filename,
                inspect.stack()[1].lineno,
            )
            error = e

            logging.info(i)
            if i != WAIT_RETRY_COUNT:
                logging.info("refresh")
                driver.refresh()

    if error is not None:
        raise error


def dump_page(
    driver: WebDriver,
    index: int,
    dump_path: pathlib.Path,
    stack_index: int = 1,
) -> None:
    name = inspect.stack()[stack_index].function.replace("<", "").replace(">", "")

    dump_path.mkdir(parents=True, exist_ok=True)

    png_path = dump_path / f"{name}_{index:02d}.png"
    htm_path = dump_path / f"{name}_{index:02d}.htm"

    driver.save_screenshot(str(png_path))

    with htm_path.open("w", encoding="utf-8") as f:
        f.write(driver.page_source)

    logging.info(
        "page dump: %02d from %s in %s line %d",
        index,
        inspect.stack()[stack_index].function,
        inspect.stack()[stack_index].filename,
        inspect.stack()[stack_index].lineno,
    )


def clear_cache(driver: WebDriver) -> None:
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})


def set_japanese_locale(driver: WebDriver) -> None:
    """CDP を使って日本語ロケールを強制設定

    Chrome の起動オプションだけでは言語設定が変わってしまうことがあるため、
    CDP を使って Accept-Language ヘッダーとロケールを強制的に日本語に設定する。
    """
    try:
        # NOTE: Network.setExtraHTTPHeaders は Network.enable を先に呼ばないと機能しない
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {"headers": {"Accept-Language": "ja-JP,ja;q=0.9"}},
        )
        driver.execute_cdp_cmd(
            "Emulation.setLocaleOverride",
            {"locale": "ja-JP"},
        )
        logging.debug("Japanese locale set via CDP")
    except Exception:
        logging.warning("Failed to set Japanese locale via CDP")


def clean_dump(dump_path: pathlib.Path, keep_days: int = 1) -> None:
    if not dump_path.exists():
        return

    time_threshold = datetime.timedelta(keep_days)

    for item in dump_path.iterdir():
        if not item.is_file():
            continue
        try:
            time_diff = datetime.datetime.now(datetime.UTC) - datetime.datetime.fromtimestamp(
                item.stat().st_mtime, datetime.UTC
            )
        except FileNotFoundError:
            # ファイルが別プロセスにより削除された場合（SQLiteの一時ファイルなど）
            continue
        if time_diff > time_threshold:
            logging.warning("remove %s [%s day(s) old].", item.absolute(), f"{time_diff.days:,}")

            item.unlink(missing_ok=True)


def get_memory_info(driver: WebDriver) -> dict[str, Any]:
    """ブラウザのメモリ使用量を取得（単位: KB）"""
    total_bytes = subprocess.Popen(  # noqa: S602
        "smem -t -c pss -P chrome | tail -n 1",  # noqa: S607
        shell=True,
        stdout=subprocess.PIPE,
    ).communicate()[0]
    total = int(str(total_bytes, "utf-8").strip())  # smem の出力は KB 単位

    try:
        memory_info = driver.execute_cdp_cmd("Memory.getAllTimeSamplingProfile", {})
        heap_usage = driver.execute_cdp_cmd("Runtime.getHeapUsage", {})

        heap_used = heap_usage.get("usedSize", 0) // 1024  # bytes → KB
        heap_total = heap_usage.get("totalSize", 0) // 1024  # bytes → KB
    except Exception as e:
        logging.debug("Failed to get memory usage: %s", e)

        memory_info = None
        heap_used = 0
        heap_total = 0

    return {
        "total": total,
        "heap_used": heap_used,
        "heap_total": heap_total,
        "memory_info": memory_info,
    }


def log_memory_usage(driver: WebDriver) -> None:
    mem_info = get_memory_info(driver)
    logging.info(
        "Chrome memory: %s MB (JS heap: %s MB)",
        f"""{mem_info["total"] // 1024:,}""",
        f"""{mem_info["heap_used"] // 1024:,}""",
    )


def _warmup(
    driver: WebDriver,
    keyword: str,
    url_pattern: str,
    sleep_sec: int = 3,
) -> None:
    # NOTE: ダミーアクセスを行って BOT ではないと思わせる。(効果なさそう...)
    driver.get("https://www.yahoo.co.jp/")
    time.sleep(sleep_sec)

    driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@name="p"]').send_keys(keyword)
    driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@name="p"]').send_keys(
        selenium.webdriver.common.keys.Keys.ENTER
    )

    time.sleep(sleep_sec)

    driver.find_element(
        selenium.webdriver.common.by.By.XPATH, f'//a[contains(@href, "{url_pattern}")]'
    ).click()

    time.sleep(sleep_sec)


class browser_tab:
    """新しいブラウザタブで URL を開くコンテキストマネージャ"""

    def __init__(self, driver: WebDriver, url: str) -> None:
        """初期化

        Args:
            driver: WebDriver インスタンス
            url: 開く URL

        """
        self.driver = driver
        self.url = url
        self.original_window: str | None = None

    def __enter__(self) -> None:
        """新しいタブを開いて URL にアクセス"""
        self.original_window = self.driver.current_window_handle
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        try:
            self.driver.get(self.url)
        except Exception:
            # NOTE: URL読み込みに失敗した場合もクリーンアップしてから例外を再送出
            self._cleanup()
            raise

    def _cleanup(self) -> None:
        """タブを閉じて元のウィンドウに戻る"""
        try:
            # 余分なタブを閉じる
            while len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.close()
            if self.original_window is not None:
                self.driver.switch_to.window(self.original_window)
            time.sleep(0.1)
        except Exception:
            # NOTE: Chromeがクラッシュした場合は無視（既に終了しているため操作不可）
            logging.exception("タブのクリーンアップに失敗しました（Chromeがクラッシュした可能性があります）")

    def _recover_from_error(self) -> None:
        """エラー後にブラウザの状態を回復する"""
        try:
            # ページロードタイムアウトをリセット（負の値になっている可能性があるため）
            self.driver.set_page_load_timeout(30)

            # about:blank に移動してレンダラーの状態をリセット
            self.driver.get("about:blank")
            time.sleep(0.5)
        except Exception:
            logging.warning("ブラウザの回復に失敗しました")

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        """タブを閉じて元のウィンドウに戻る"""
        self._cleanup()

        # 例外が発生した場合はブラウザの状態を回復
        if exception_type is not None:
            self._recover_from_error()


class error_handler:
    """Selenium操作時のエラーハンドリング用コンテキストマネージャ

    エラー発生時に自動でログ出力、スクリーンショット取得、コールバック呼び出しを行う。

    Args:
        driver: WebDriver インスタンス
        message: ログに出力するエラーメッセージ
        on_error: エラー時に呼ばれるコールバック関数
            (exception, screenshot: PIL.Image.Image | None, page_source: str | None) -> None
        capture_screenshot: スクリーンショットを自動取得するか（デフォルト: True）
        reraise: 例外を再送出するか（デフォルト: True）

    Attributes:
        exception: 発生した例外（エラーがなければ None）
        screenshot: 取得したスクリーンショット（PIL.Image.Image、取得失敗時は None）
        page_source: 取得したページソース（取得失敗時は None）

    Examples:
        基本的な使用方法::

            with my_lib.selenium_util.error_handler(driver, message="ログイン処理に失敗") as handler:
                driver.get(login_url)
                driver.find_element(...).click()

        コールバック付き（Slack通知など）::

            def notify(exc, screenshot, page_source):
                slack.notify_error_with_page(config, "エラー発生", exc, screenshot, page_source)

            with my_lib.selenium_util.error_handler(
                driver,
                message="クロール処理に失敗",
                on_error=notify,
            ):
                crawl_page(driver)

        例外を抑制して続行::

            with my_lib.selenium_util.error_handler(driver, reraise=False) as handler:
                risky_operation()

            if handler.exception:
                logging.warning("処理をスキップしました")

    """

    def __init__(
        self,
        driver: WebDriver,
        message: str = "Selenium operation failed",
        on_error: Callable[[Exception, PIL.Image.Image | None, str | None], None] | None = None,
        capture_screenshot: bool = True,
        reraise: bool = True,
    ) -> None:
        """初期化"""
        self.driver = driver
        self.message = message
        self.on_error = on_error
        self.capture_screenshot = capture_screenshot
        self.reraise = reraise
        self.exception: Exception | None = None
        self.screenshot: PIL.Image.Image | None = None
        self.page_source: str | None = None

    def __enter__(self) -> Self:
        """コンテキストマネージャの開始"""
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> bool:
        """コンテキストマネージャの終了、エラー処理を実行"""
        if exception_value is None:
            return False

        # 例外を記録
        if isinstance(exception_value, Exception):
            self.exception = exception_value
        else:
            # BaseException（KeyboardInterrupt など）は処理せず再送出
            return False

        # ログ出力
        logging.exception(self.message)

        # スクリーンショット・ページソース取得
        if self.capture_screenshot:
            try:
                self.page_source = self.driver.page_source
            except Exception:
                logging.debug("Failed to capture page source for error handling")
            try:
                screenshot_bytes = self.driver.get_screenshot_as_png()
                self.screenshot = PIL.Image.open(io.BytesIO(screenshot_bytes))
            except Exception:
                logging.debug("Failed to capture screenshot for error handling")

        # コールバック呼び出し
        if self.on_error is not None:
            try:
                self.on_error(self.exception, self.screenshot, self.page_source)
            except Exception:
                logging.exception("Error in on_error callback")

        # reraise=False なら例外を抑制
        return not self.reraise


def _is_chrome_related_process(process: psutil.Process) -> bool:
    """プロセスがChrome関連かどうかを判定"""
    try:
        process_name = process.name().lower()
        # Chrome関連のプロセス名パターン
        chrome_patterns = ["chrome", "chromium", "google-chrome", "undetected_chro"]
        # chromedriverは除外
        if "chromedriver" in process_name:
            return False
        return any(pattern in process_name for pattern in chrome_patterns)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _get_chrome_processes_by_pgid(chromedriver_pid: int, existing_pids: set[int]) -> list[int]:
    """プロセスグループIDで追加のChrome関連プロセスを取得"""
    additional_pids = []
    try:
        pgid = os.getpgid(chromedriver_pid)
        for proc in psutil.process_iter(["pid", "name", "ppid"]):
            if proc.info["pid"] in existing_pids:
                continue
            try:
                if os.getpgid(proc.info["pid"]) == pgid:
                    proc_obj = psutil.Process(proc.info["pid"])
                    if _is_chrome_related_process(proc_obj):
                        additional_pids.append(proc.info["pid"])
                        logging.debug(
                            "Found Chrome-related process by pgid: PID %d, name: %s",
                            proc.info["pid"],
                            proc.info["name"],
                        )
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass
    except (OSError, psutil.NoSuchProcess):
        logging.debug("Failed to get process group ID for chromedriver")
    return additional_pids


def _get_chrome_related_processes(driver: WebDriver) -> list[int]:
    """Chrome関連の全子プロセスを取得

    undetected_chromedriver 使用時、Chrome プロセスは chromedriver の子ではなく
    Python プロセスの直接の子として起動されることがあるため、両方を検索する。
    """
    chrome_pids = set()

    # 1. driver.service.process の子プロセスを検索
    # NOTE: Chrome/Firefox WebDriver には service 属性があるが、型スタブでは定義されていない
    try:
        if hasattr(driver, "service") and driver.service and hasattr(driver.service, "process"):  # type: ignore[union-attr]
            process = driver.service.process  # type: ignore[union-attr]
            if process and hasattr(process, "pid"):
                chromedriver_pid = process.pid

                # psutilでプロセス階層を取得
                parent_process = psutil.Process(chromedriver_pid)
                children = parent_process.children(recursive=True)

                for child in children:
                    chrome_pids.add(child.pid)
                    logging.debug(
                        "Found Chrome-related process (service child): PID %d, name: %s",
                        child.pid,
                        child.name(),
                    )
    except Exception:
        logging.exception("Failed to get Chrome-related processes from service")

    # 2. 現在の Python プロセスの全子孫から Chrome 関連プロセスを検索
    try:
        current_process = psutil.Process()
        all_children = current_process.children(recursive=True)

        for child in all_children:
            if child.pid in chrome_pids:
                continue
            try:
                if _is_chrome_related_process(child):
                    chrome_pids.add(child.pid)
                    logging.debug(
                        "Found Chrome-related process (python child): PID %d, name: %s",
                        child.pid,
                        child.name(),
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        logging.exception("Failed to get Chrome-related processes from python children")

    return list(chrome_pids)


def _send_signal_to_processes(pids: list[int], sig: signal.Signals, signal_name: str) -> None:
    """プロセスリストに指定されたシグナルを送信"""
    errors = []
    for pid in pids:
        try:
            # プロセス名を取得
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "unknown"

            if sig == signal.SIGKILL:
                # プロセスがまだ存在するかチェック
                os.kill(pid, 0)  # シグナル0は存在確認
            os.kill(pid, sig)
            logging.info("Sent %s to process: PID %d (%s)", signal_name, pid, process_name)
        except (ProcessLookupError, OSError) as e:
            # プロセスが既に終了している場合は無視
            errors.append((pid, e))

    # エラーが発生した場合はまとめてログ出力
    if errors:
        logging.debug("Failed to send %s to some processes: %s", signal_name, errors)


def _terminate_chrome_processes(chrome_pids: list[int], timeout: float = 5.0) -> None:
    """Chrome関連プロセスを段階的に終了

    Args:
        chrome_pids: 終了対象のプロセスIDリスト
        timeout: SIGTERM後にプロセス終了を待機する最大時間（秒）

    """
    if not chrome_pids:
        return

    # 優雅な終了（SIGTERM）
    _send_signal_to_processes(chrome_pids, signal.SIGTERM, "SIGTERM")

    # プロセスの終了を待機（ポーリング）
    remaining_pids = list(chrome_pids)
    poll_interval = 0.2
    elapsed = 0.0

    while remaining_pids and elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        # まだ生存しているプロセスをチェック
        still_alive = []
        for pid in remaining_pids:
            try:
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                        still_alive.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        remaining_pids = still_alive

    # タイムアウト後もまだ残っているプロセスにのみ SIGKILL を送信
    if remaining_pids:
        logging.warning(
            "Chrome processes still alive after %.1fs, sending SIGKILL to %d processes",
            elapsed,
            len(remaining_pids),
        )
        _send_signal_to_processes(remaining_pids, signal.SIGKILL, "SIGKILL")


def _reap_single_process(pid: int) -> None:
    """単一プロセスをwaitpidで回収"""
    try:
        # ノンブロッキングでwaitpid
        result_pid, status = os.waitpid(pid, os.WNOHANG)
        if result_pid == pid:
            # プロセス名を取得
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "unknown"
            logging.debug("Reaped Chrome process: PID %d (%s)", pid, process_name)
    except (ChildProcessError, OSError):
        # 子プロセスでない場合や既に回収済みの場合は無視
        pass


def _reap_chrome_processes(chrome_pids: list[int]) -> None:
    """Chrome関連プロセスを明示的に回収してゾンビ化を防ぐ"""
    for pid in chrome_pids:
        _reap_single_process(pid)


def _get_remaining_chrome_pids(chrome_pids: list[int]) -> list[int]:
    """指定されたPIDリストから、まだ生存しているChrome関連プロセスを取得"""
    remaining = []
    for pid in chrome_pids:
        try:
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                if (
                    process.is_running()
                    and process.status() != psutil.STATUS_ZOMBIE
                    and _is_chrome_related_process(process)
                ):
                    remaining.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return remaining


def _wait_for_processes_with_check(
    chrome_pids: list[int],
    timeout: float,
    poll_interval: float = 0.2,
    log_interval: float = 1.0,
) -> list[int]:
    """プロセスの終了を待機しつつ、残存プロセスをチェック

    Args:
        chrome_pids: 監視対象のプロセスIDリスト
        timeout: 最大待機時間（秒）
        poll_interval: チェック間隔（秒）
        log_interval: ログ出力間隔（秒）

    Returns:
        タイムアウト後も残存しているプロセスIDのリスト

    """
    elapsed = 0.0
    last_log_time = 0.0
    remaining_pids = list(chrome_pids)

    while remaining_pids and elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        remaining_pids = _get_remaining_chrome_pids(remaining_pids)

        if remaining_pids and (elapsed - last_log_time) >= log_interval:
            logging.info(
                "Found %d remaining Chrome processes after %.0fs",
                len(remaining_pids),
                elapsed,
            )
            last_log_time = elapsed

    return remaining_pids


def quit_driver_gracefully(
    driver: WebDriver | None,
    wait_sec: float = 5.0,
    sigterm_wait_sec: float = 5.0,
    sigkill_wait_sec: float = 5.0,
) -> None:
    """Chrome WebDriverを確実に終了する

    終了フロー:
    1. driver.quit() を呼び出し
    2. wait_sec 秒待機しつつプロセス終了をチェック
    3. 残存プロセスがあれば SIGTERM を送信
    4. sigterm_wait_sec 秒待機しつつプロセス終了をチェック
    5. 残存プロセスがあれば SIGKILL を送信
    6. sigkill_wait_sec 秒待機

    Args:
        driver: 終了する WebDriver インスタンス
        wait_sec: quit 後にプロセス終了を待機する秒数（デフォルト: 5秒）
        sigterm_wait_sec: SIGTERM 後にプロセス終了を待機する秒数（デフォルト: 5秒）
        sigkill_wait_sec: SIGKILL 後にプロセス回収を待機する秒数（デフォルト: 5秒）

    """
    if driver is None:
        return

    # quit前にChrome関連プロセスを記録
    chrome_pids_before = _get_chrome_related_processes(driver)

    try:
        # WebDriverの正常終了を試行（これがタブのクローズも含む）
        driver.quit()
        logging.info("WebDriver quit successfully")
    except Exception:
        logging.warning("Failed to quit driver normally", exc_info=True)
    finally:
        # undetected_chromedriver の __del__ がシャットダウン時に再度呼ばれるのを防ぐ
        if hasattr(driver, "_has_quit"):
            driver._has_quit = True  # type: ignore[attr-defined]

    # ChromeDriverサービスの停止を試行
    try:
        if hasattr(driver, "service") and driver.service and hasattr(driver.service, "stop"):  # type: ignore[union-attr]
            driver.service.stop()  # type: ignore[union-attr]
    except (ConnectionResetError, OSError):
        # Chrome が既に終了している場合は無視
        logging.debug("Chrome service already stopped")
    except Exception:
        logging.warning("Failed to stop Chrome service", exc_info=True)

    # Step 1: quit 後に wait_sec 秒待機しつつプロセス終了をチェック
    remaining_pids = _wait_for_processes_with_check(chrome_pids_before, wait_sec)

    if not remaining_pids:
        logging.debug("All Chrome processes exited normally")
        return

    # Step 2: 残存プロセスに SIGTERM を送信
    logging.info(
        "Found %d remaining Chrome processes after %.0fs, sending SIGTERM",
        len(remaining_pids),
        wait_sec,
    )
    _send_signal_to_processes(remaining_pids, signal.SIGTERM, "SIGTERM")

    # Step 3: SIGTERM 後に sigterm_wait_sec 秒待機しつつプロセス終了をチェック
    remaining_pids = _wait_for_processes_with_check(remaining_pids, sigterm_wait_sec)

    if not remaining_pids:
        logging.info("All Chrome processes exited after SIGTERM")
        _reap_chrome_processes(chrome_pids_before)
        return

    # Step 4: 残存プロセスに SIGKILL を送信
    logging.warning(
        "Chrome processes still alive after SIGTERM + %.1fs, sending SIGKILL to %d processes",
        sigterm_wait_sec,
        len(remaining_pids),
    )
    _send_signal_to_processes(remaining_pids, signal.SIGKILL, "SIGKILL")

    # Step 5: SIGKILL 後に sigkill_wait_sec 秒待機してプロセス回収
    time.sleep(sigkill_wait_sec)
    _reap_chrome_processes(chrome_pids_before)

    # 最終チェック：まだ残っているプロセスがあるか確認
    still_remaining = _get_remaining_chrome_pids(remaining_pids)

    # 回収できなかったプロセスについて警告
    if still_remaining:
        for pid in still_remaining:
            try:
                process = psutil.Process(pid)
                logging.warning("Failed to collect Chrome-related process: PID %d (%s)", pid, process.name())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass


if __name__ == "__main__":
    import pathlib

    import docopt
    import selenium.webdriver.support.wait

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = create_driver("test", pathlib.Path(config["data"]["selenium"]))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

    driver.get("https://www.google.com/")
    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, '//input[contains(@value, "Google")]')
        )
    )

    quit_driver_gracefully(driver)
