#!/usr/bin/env python3
import datetime
import inspect
import logging
import os
import random
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

WAIT_RETRY_COUNT = 1
AGENT_NAME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"  # noqa: E501


def create_driver_impl(profile_name, data_path, agent_name, is_headless):  # noqa: ARG001
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

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--disable-desktop-notifications")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")

    options.add_argument("--disable-crash-reporter")

    # ゾンビプロセス対策のオプション
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-component-update")

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1200")

    options.add_argument("--user-data-dir=" + str(chrome_data_path / profile_name))

    # options.add_argument(f'--user-agent="{agent_name}"')

    service = selenium.webdriver.chrome.service.Service(
        service_args=["--verbose", f"--log-path={str(log_path / 'webdriver.log')!s}"],
    )

    driver = selenium.webdriver.Chrome(service=service, options=options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    # driver.execute_cdp_cmd(
    #     "Network.setUserAgentOverride",
    #     {
    #         "userAgent": agent_name,
    #         "acceptLanguage": "ja,en-US;q=0.9,en;q=0.8",
    #         "platform": "macOS",
    #         "userAgentMetadata": {
    #             "brands": [
    #                 {"brand": "Google Chrome", "version": "131"},
    #                 {"brand": "Not:A-Brand", "version": "24"},
    #                 {"brand": "Chromium", "version": "131"},
    #             ],
    #             "platform": "macOS",
    #             "platformVersion": "15.0.0",
    #             "architecture": "x86",
    #             "model": "",
    #             "mobile": False,
    #             "bitness": "64",
    #             "wow64": False,
    #         },
    #     },
    # )

    driver.set_page_load_timeout(30)

    return driver


def create_driver(profile_name, data_path, agent_name=AGENT_NAME, is_headless=True):
    # NOTE: ルートロガーの出力レベルを変更した場合でも Selenium 関係は抑制する
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.common.selenium_manager").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

    # NOTE: 1回だけ自動リトライ
    try:
        return create_driver_impl(profile_name, data_path, agent_name, is_headless)
    except Exception:
        return create_driver_impl(profile_name, data_path, agent_name, is_headless)


def xpath_exists(driver, xpath):
    return len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, xpath)) != 0


def get_text(driver, xpath, safe_text):
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
        time_diff = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromtimestamp(
            item.stat().st_mtime, datetime.timezone.utc
        )
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

    def __enter__(self):  # noqa: D105
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.driver.get(self.url)

    def __exit__(self, exception_type, exception_value, traceback):  # noqa: D105
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(0.5)


def _is_chrome_related_process(process):
    """プロセスがChrome関連かどうかを判定"""
    try:
        return any(name in process.name().lower() for name in ("chrome", "cat"))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def get_chrome_related_processes(driver):
    """Chrome関連の全子プロセスを取得"""
    chrome_pids = []

    try:
        if (
            hasattr(driver, "service")
            and driver.service
            and hasattr(driver.service, "process")
            and driver.service.process
        ):
            # ChromeDriverプロセスを起点に子プロセスを検索
            chromedriver_pid = driver.service.process.pid
            chrome_pids.append(chromedriver_pid)

            # psutilでプロセス階層を取得
            parent_process = psutil.Process(chromedriver_pid)
            children = parent_process.children(recursive=True)

            for child in children:
                if _is_chrome_related_process(child):
                    chrome_pids.append(child.pid)
                    logging.info("Found Chrome-related process: PID %d, name: %s", child.pid, child.name())
    except Exception:
        logging.exception("Failed to get Chrome-related processes")

    return chrome_pids


def _send_signal_to_processes(pids, sig, signal_name):
    """プロセスリストに指定されたシグナルを送信"""
    errors = []
    for pid in pids:
        try:
            if sig == signal.SIGKILL:
                # プロセスがまだ存在するかチェック
                os.kill(pid, 0)  # シグナル0は存在確認
            os.kill(pid, sig)
            logging.info("Sent %s to process: PID %d", signal_name, pid)
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

    # 1. 優雅な終了（SIGTERM）
    _send_signal_to_processes(chrome_pids, signal.SIGTERM, "SIGTERM")

    # 2. 少し待機
    time.sleep(1)

    # 3. 強制終了（SIGKILL）
    _send_signal_to_processes(chrome_pids, signal.SIGKILL, "SIGKILL")


def _reap_single_process(pid):
    """単一プロセスをwaitpidで回収"""
    try:
        # ノンブロッキングでwaitpid
        result_pid, status = os.waitpid(pid, os.WNOHANG)
        if result_pid == pid:
            logging.info("Reaped Chrome process: PID %d", pid)
        elif result_pid == 0:
            # まだ終了していない場合は少し待ってから再試行
            time.sleep(0.1)
            try:
                result_pid, status = os.waitpid(pid, os.WNOHANG)
                if result_pid == pid:
                    logging.info("Reaped Chrome process (retry): PID %d", pid)
            except ChildProcessError:
                # 子プロセスでない場合は無視
                pass
    except ChildProcessError:
        # 子プロセスでない場合は無視
        pass
    except OSError:
        logging.execption("Failed to reap Chrome process")


def reap_chrome_processes(chrome_pids):
    """Chrome関連プロセスを明示的に回収してゾンビ化を防ぐ"""
    for pid in chrome_pids:
        _reap_single_process(pid)


def quit_driver_gracefully(driver):
    """Chrome WebDriverを確実に終了する"""
    if driver is None:
        return

    # Chrome関連プロセスを事前に取得
    chrome_pids = get_chrome_related_processes(driver)

    # 全てのタブを明示的に閉じる
    try:
        handles = driver.window_handles
    except Exception:
        logging.exception("Failed to access window handles")
        handles = []

    for handle in handles:
        try:
            driver.switch_to.window(handle)
            driver.close()
        except Exception:  # noqa: PERF203
            logging.exception("Failed to close window handle")

    try:
        # WebDriverプロセスを終了
        driver.quit()
    except Exception:
        logging.exception("Failed to quit driver normally")

    # ChromeDriverサービスの明示的な停止
    try:
        if (
            hasattr(driver, "service")
            and driver.service
            and hasattr(driver.service, "process")
            and driver.service.process
            and driver.service.process.poll() is None
        ):
            driver.service.stop()
    except Exception:
        logging.exception("Failed to stop Chrome service")

    # プロセス終了を待機
    time.sleep(0.5)

    # Chrome関連プロセスを強制終了
    terminate_chrome_processes(chrome_pids)

    # 少し待機してからプロセス回収
    time.sleep(0.5)
    reap_chrome_processes(chrome_pids)
