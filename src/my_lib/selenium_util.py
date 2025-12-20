#!/usr/bin/env python3
"""
Selenium を Chrome Driver を使って動かします。

Usage:
  selenium_util.py [-c CONFIG] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -d                : デバッグモードで動作します。
"""

import datetime
import inspect
import logging
import os
import pathlib
import random
import re
import signal
import subprocess
import time

import psutil
import selenium
import selenium.common.exceptions
import selenium.webdriver.chrome.options
import selenium.webdriver.chrome.service
import selenium.webdriver.common.action_chains
import selenium.webdriver.common.by
import selenium.webdriver.common.keys
import selenium.webdriver.support.expected_conditions
import undetected_chromedriver

WAIT_RETRY_COUNT = 1


def get_chrome_version():
    try:
        result = subprocess.run(
            ["google-chrome", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        match = re.search(r"(\d+)\.", result.stdout)
        if match:
            return int(match.group(1))
    except Exception:
        logging.warning("Failed to detect Chrome version")
    return None


def create_driver_impl(profile_name, data_path, is_headless):  # noqa: ARG001
    chrome_data_path = data_path / "chrome"
    log_path = data_path / "log"

    # NOTE: Pytest を並列実行できるようにする
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    if suffix is not None:
        profile_name += "." + suffix

    chrome_data_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    options = selenium.webdriver.chrome.options.Options()

    if is_headless:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--disable-gpu")

    # ポップアップブロックを無効化（新しいタブを開くために必要）
    options.add_argument("--disable-popup-blocking")

    # ゾンビプロセス対策のオプション
    options.add_argument("--no-zygote")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-background-networking")
    options.add_argument("--no-first-run")

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1080")

    # NOTE: Accept-Language ヘッダーを日本語優先に設定
    options.add_experimental_option("prefs", {"intl.accept_languages": "ja-JP,ja,en-US,en"})

    options.add_argument("--user-data-dir=" + str(chrome_data_path / profile_name))

    if not is_headless:
        options.add_argument("--auto-open-devtools-for-tabs")

    service = selenium.webdriver.chrome.service.Service(
        service_args=["--verbose", f"--log-path={str(log_path / 'webdriver.log')!s}"],
    )

    chrome_version = get_chrome_version()

    # NOTE: user_multi_procs=True は既存の chromedriver ファイルが存在することを前提としているため、
    # ファイルが存在しない場合（CI環境の初回実行など）は False にする
    uc_data_path = pathlib.Path("~/.local/share/undetected_chromedriver").expanduser()
    use_multi_procs = uc_data_path.exists() and any(uc_data_path.glob("*chromedriver*"))

    driver = undetected_chromedriver.Chrome(
        service=service,
        options=options,
        use_subprocess=False,
        version_main=chrome_version,
        user_multi_procs=use_multi_procs,
    )

    driver.set_page_load_timeout(30)

    return driver


def _cleanup_profile_lock(profile_path):
    """プロファイルのロックファイルを削除する"""
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    found_locks = []
    for lock_file in lock_files:
        lock_path = profile_path / lock_file
        if lock_path.exists() or lock_path.is_symlink():
            found_locks.append(lock_path)

    if found_locks:
        logging.warning("Profile lock files found: %s", ", ".join(str(p.name) for p in found_locks))
        for lock_path in found_locks:
            try:
                lock_path.unlink()
            except OSError as e:
                logging.warning("Failed to remove lock file %s: %s", lock_path, e)


def create_driver(profile_name, data_path, is_headless=True, clean_profile=False):
    # NOTE: ルートロガーの出力レベルを変更した場合でも Selenium 関係は抑制する
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.common.selenium_manager").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

    # NOTE: Pytest を並列実行できるようにする
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    actual_profile_name = profile_name + ("." + suffix if suffix is not None else "")
    profile_path = data_path / "chrome" / actual_profile_name

    if clean_profile:
        _cleanup_profile_lock(profile_path)

    # NOTE: 1回だけ自動リトライ
    try:
        return create_driver_impl(profile_name, data_path, is_headless)
    except Exception as e:
        logging.warning("First attempt to create driver failed: %s", e)
        # NOTE: コンテナ内で実行中の場合のみ、残った Chrome プロセスをクリーンアップ
        if os.path.exists("/.dockerenv"):
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    proc_name = proc.info["name"].lower() if proc.info["name"] else ""
                    if "chrome" in proc_name:
                        logging.info("Terminating orphaned Chrome process: PID %d", proc.info["pid"])
                        os.kill(proc.info["pid"], signal.SIGTERM)
                except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError, OSError):
                    pass
            time.sleep(1)

        # NOTE: プロファイルのロックファイルを削除
        _cleanup_profile_lock(profile_path)

        return create_driver_impl(profile_name, data_path, is_headless)


def xpath_exists(driver, xpath):
    return len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0


def get_text(driver, xpath, safe_text, wait=None):
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


def input_xpath(driver, xpath, text, wait=None, is_warn=True):
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


def click_xpath(driver, xpath, wait=None, is_warn=True):
    if wait is not None:
        wait.until(
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (selenium.webdriver.common.by.By.XPATH, xpath)
            )
        )
        time.sleep(0.05)

    if xpath_exists(driver, xpath):
        elem = driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath)
        action = selenium.webdriver.common.action_chains.ActionChains(driver)
        action.move_to_element(elem)
        action.perform()

        elem.click()
        return True
    else:
        if is_warn:
            logging.warning("Element is not found: %s", xpath)
        return False


def is_display(driver, xpath):
    return (len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0) and (
        driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).is_displayed()
    )


def random_sleep(sec):
    RATIO = 0.8

    time.sleep((sec * RATIO) + (sec * (1 - RATIO) * 2) * random.random())  # noqa: S311


def wait_patiently(driver, wait, target):
    error = None
    for i in range(WAIT_RETRY_COUNT + 1):
        try:
            wait.until(target)
            return
        except selenium.common.exceptions.TimeoutException as e:  # noqa: PERF203
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

    raise error


def dump_page(driver, index, dump_path, stack=1):
    name = inspect.stack()[stack].function.replace("<", "").replace(">", "")

    dump_path.mkdir(parents=True, exist_ok=True)

    png_path = dump_path / f"{name}_{index:02d}.png"
    htm_path = dump_path / f"{name}_{index:02d}.htm"

    driver.save_screenshot(str(png_path))

    with htm_path.open("w", encoding="utf-8") as f:
        f.write(driver.page_source)

    logging.info(
        "page dump: %02d from %s in %s line %d",
        index,
        inspect.stack()[stack].function,
        inspect.stack()[stack].filename,
        inspect.stack()[stack].lineno,
    )


def clear_cache(driver):
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})


def clean_dump(dump_path, keep_days=1):
    if not dump_path.exists():
        return

    time_threshold = datetime.timedelta(keep_days)

    for item in dump_path.iterdir():
        if not item.is_file():
            continue
        try:
            time_diff = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromtimestamp(
                item.stat().st_mtime, datetime.timezone.utc
            )
        except FileNotFoundError:
            # ファイルが別プロセスにより削除された場合（SQLiteの一時ファイルなど）
            continue
        if time_diff > time_threshold:
            logging.info("remove %s [%s day(s) old].", item.absolute(), f"{time_diff.days:,}")

            item.unlink(missing_ok=True)


def get_memory_info(driver):
    total = subprocess.Popen(  # noqa: S602
        "smem -t -c pss -P chrome | tail -n 1",  # noqa: S607
        shell=True,
        stdout=subprocess.PIPE,
    ).communicate()[0]
    total = int(str(total, "utf-8").strip()) // 1024

    js_heap = driver.execute_script("return window.performance.memory.usedJSHeapSize") // (1024 * 1024)

    return {"total": total, "js_heap": js_heap}


def log_memory_usage(driver):
    mem_info = get_memory_info(driver)
    logging.info(
        "Chrome memory: %s MB (JS: %s MB)", f"""{mem_info["total"]:,}""", f"""{mem_info["js_heap"]:,}:"""
    )


def warmup(driver, keyword, url_pattern, sleep_sec=3):
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


class browser_tab:  # noqa: N801
    def __init__(self, driver, url):  # noqa: D107
        self.driver = driver
        self.url = url
        self.original_window = None

    def __enter__(self):  # noqa: D105
        self.original_window = self.driver.current_window_handle
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.driver.get(self.url)

    def __exit__(self, exception_type, exception_value, traceback):  # noqa: D105
        try:
            self.driver.close()
            self.driver.switch_to.window(self.original_window)
            time.sleep(0.1)
        except Exception:
            # NOTE: Chromeがクラッシュした場合は無視（既に終了しているため操作不可）
            logging.exception("Failed to close browser tab (Chrome may have crashed)")


def _is_chrome_related_process(process):
    """プロセスがChrome関連かどうかを判定"""
    try:
        process_name = process.name().lower()
        # chromedriverは除外
        return "chromedriver" not in process_name
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _get_chrome_processes_by_pgid(chromedriver_pid, existing_pids):
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


def get_chrome_related_processes(driver):
    """Chrome関連の全子プロセスを取得"""
    chrome_pids = []

    try:
        if hasattr(driver, "service") and driver.service and hasattr(driver.service, "process"):
            process = driver.service.process
            if process and hasattr(process, "pid"):
                chromedriver_pid = process.pid

                # psutilでプロセス階層を取得
                parent_process = psutil.Process(chromedriver_pid)
                children = parent_process.children(recursive=True)

                for child in children:
                    chrome_pids.append(child.pid)
                    logging.debug("Found Chrome-related process: PID %d, name: %s", child.pid, child.name())

                # # プロセスグループIDでの検索を追加
                # additional_pids = _get_chrome_processes_by_pgid(chromedriver_pid, chrome_pids)
                # chrome_pids.extend(additional_pids)

    except Exception:
        logging.exception("Failed to get Chrome-related processes")

    return chrome_pids


def _send_signal_to_processes(pids, sig, signal_name):
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
        except (ProcessLookupError, OSError) as e:  # noqa: PERF203
            # プロセスが既に終了している場合は無視
            errors.append((pid, e))

    # エラーが発生した場合はまとめてログ出力
    if errors:
        logging.debug("Failed to send %s to some processes: %s", signal_name, errors)


def terminate_chrome_processes(chrome_pids):
    """Chrome関連プロセスを段階的に終了"""
    if not chrome_pids:
        return

    # 優雅な終了（SIGTERM）
    _send_signal_to_processes(chrome_pids, signal.SIGTERM, "SIGTERM")

    # 少し待機してから強制終了（SIGKILL）
    time.sleep(0.5)
    _send_signal_to_processes(chrome_pids, signal.SIGKILL, "SIGKILL")


def _reap_single_process(pid):
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


def reap_chrome_processes(chrome_pids):
    """Chrome関連プロセスを明示的に回収してゾンビ化を防ぐ"""
    for pid in chrome_pids:
        _reap_single_process(pid)


def quit_driver_gracefully(driver):  # noqa: C901, PLR0912
    """Chrome WebDriverを確実に終了する"""
    if driver is None:
        return

    # quit前にChrome関連プロセスを記録
    chrome_pids_before = get_chrome_related_processes(driver)

    try:
        # WebDriverの正常終了を試行（これがタブのクローズも含む）
        driver.quit()
        logging.info("WebDriver quit successfully")
    except Exception:
        logging.exception("Failed to quit driver normally")

    # quit後に残存プロセスをチェック
    time.sleep(2)
    remaining_pids = []
    for pid in chrome_pids_before:
        try:
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                if _is_chrome_related_process(process):
                    remaining_pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):  # noqa: PERF203
            # プロセスが既に終了している場合は無視
            pass

    # 残存プロセスがある場合は強化した終了処理を実行
    if remaining_pids:
        logging.info(
            "Found %d remaining Chrome processes after quit, attempting cleanup", len(remaining_pids)
        )

        # ChromeDriverサービスの停止を試行
        try:
            if hasattr(driver, "service") and driver.service and hasattr(driver.service, "stop"):
                driver.service.stop()
        except Exception:
            logging.exception("Failed to stop Chrome service")

        # プロセスの強制終了
        terminate_chrome_processes(remaining_pids)

        # プロセス回収
        time.sleep(0.5)
        reap_chrome_processes(remaining_pids)

        # 最終チェック：まだ残っているプロセスがあるか確認
        still_remaining = []
        for pid in remaining_pids:
            try:
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    if _is_chrome_related_process(process):
                        still_remaining.append((pid, process.name()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):  # noqa: PERF203
                pass

        # 回収できなかったプロセスについて警告
        if still_remaining:
            for pid, name in still_remaining:
                logging.warning("Failed to collect Chrome-related process: PID %d (%s)", pid, name)


if __name__ == "__main__":
    import pathlib

    import docopt
    import selenium.webdriver.support.wait

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-d"]

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
