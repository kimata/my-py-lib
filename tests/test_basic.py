#!/usr/bin/env python3
# ruff: noqa: S101

import logging
import pathlib
import re
import time
import unittest

import pytest

import data.sample_webapp
import my_lib.config
import my_lib.notify.slack
import my_lib.webapp.config

CONFIG_FILE = "tests/data/config.example.yaml"
WAIT_TIMEOUT_SEC = 5


@pytest.fixture(scope="session", autouse=True)
def env_mock():
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "NO_COLORED_LOGS": "true",
            "TEST": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    # Create a mock response object that has a .get() method
    mock_response = unittest.mock.MagicMock()
    mock_response.get.return_value = "test_timestamp"

    with unittest.mock.patch(
        "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
        return_value=mock_response,
    ) as fixture:
        yield fixture


@pytest.fixture
def app():
    my_lib.webapp.config.init(my_lib.config.load(CONFIG_FILE))

    with unittest.mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        app = data.sample_webapp.create_app(CONFIG_FILE)

        yield app

        # NOTE: ログをクリア
        test_webapp_log_term()


@pytest.fixture
def client(app):
    test_client = app.test_client()

    time.sleep(1)
    app_log_clear(test_client)

    yield test_client

    test_client.delete()


def app_log_clear(client):
    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_clear")
    assert res.status_code == 200


######################################################################
def test_webapp_config():
    my_lib.webapp.config.init({"webapp": {}})
    my_lib.webapp.config.init({"webapp": {"timezone": {"offset": "+9"}, "data": {"schedule_file_path": "/"}}})
    my_lib.webapp.config.init({"webapp": {"timezone": {}}})


def test_webapp_base(client):
    res = client.get("/")

    assert res.status_code == 302
    assert re.search(rf"{data.sample_webapp.WEBAPP_URL_PREFIX}/$", res.location)

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/")
    assert res.status_code == 200
    assert "Test Data" in res.data.decode("utf-8")

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200


@pytest.mark.xdist_group(name="webapp")
def test_webapp_log(client):
    res = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_clear",
        query_string={
            "log": "false",
        },
    )
    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_view")
    assert res.status_code == 200
    log_list = res.json["data"]

    assert len(log_list) == 0

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/log_write")
    assert res.status_code == 200
    time.sleep(2)

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_view")
    assert res.status_code == 200
    log_list = res.json["data"]

    assert log_list[0]["message"] == "TEST WARN"
    assert log_list[1]["message"] == "TEST ERROR"


@pytest.mark.xdist_group(name="webapp")
def test_webapp_event(client):
    import concurrent.futures
    import multiprocessing

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "1"})
    assert res.status_code == 200
    assert res.data.decode()

    # NOTE: event に先にアクセスさせておいてから、ログに書き込む
    def log_write():
        time.sleep(3)
        client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/log_write")

    my_lib.webapp.event.YEILD_TIMEOUT = 4

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(log_write)

        # NOTE: log_write は内部で 2 回ログ書き込みを行う
        res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "2"})

        logging.info("log: %s", my_lib.webapp.log.get())

        event_list = res.data.decode().split("\n\n")
        expected_list = ["data: log", "data: log"]
        assert [event for event in event_list if event != "data: dummy"][
            : len(expected_list)
        ] == expected_list

        future.result()

    # my_lib.webapp.event.term()
    queue = multiprocessing.Queue()
    my_lib.webapp.event.start(queue)

    # NOTE: event に先にアクセスさせておいてから、ログに書き込む
    def queue_put():
        time.sleep(3)
        queue.put(my_lib.webapp.event.EVENT_TYPE.SCHEDULE)
        queue.put(my_lib.webapp.event.EVENT_TYPE.CONTROL)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(queue_put)

        res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "2"})

        logging.info("log: %s", my_lib.webapp.log.get())

        event_list = res.data.decode().split("\n\n")
        expected_list = [
            f"data: {my_lib.webapp.event.EVENT_TYPE.CONTROL.value}",
            f"data: {my_lib.webapp.event.EVENT_TYPE.SCHEDULE.value}",
        ]
        assert [event for event in event_list if event != "data: dummy"][
            : len(expected_list)
        ] == expected_list

        future.result()

    my_lib.webapp.event.term()


def test_webapp_util(client):
    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/memory")
    assert res.status_code == 200
    assert "memory" in res.json

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/snapshot")
    assert res.status_code == 200
    assert res.json["msg"] == "taken snapshot"

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/snapshot")
    assert res.status_code == 200
    assert type(res.json) is list
    assert len(res.json) != 0

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/sysinfo")
    assert res.status_code == 200
    assert "load_average" in res.json


def test_flask_util(client, mocker):
    res = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/gzipped/through",
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 302

    res = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/",
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 200
    assert res.headers["Cache-Control"] == "max-age=86400"

    res = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/gzipped/disable_cache",
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 200
    assert res.headers["Cache-Control"] == "no-store, must-revalidate"
    assert res.headers["Expires"] == "0"

    res = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/support_jsonp",
        query_string={
            "callback": "CALL",
        },
    )
    assert res.status_code == 200
    assert res.data.decode("utf-8") == """CALL({"status":"OK"})"""

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/remote_host")
    assert res.status_code == 200
    assert res.data.decode("utf-8") == "localhost, Unknown"

    mocker.patch("socket.gethostbyaddr", side_effect=RuntimeError())

    res = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/remote_host")
    assert res.status_code == 200
    assert res.data.decode("utf-8") == "127.0.0.1, Unknown"


def test_footprint():
    import my_lib.footprint

    my_lib.webapp.config.init(my_lib.config.load(CONFIG_FILE))
    path = my_lib.webapp.config.STAT_DIR_PATH / "footprint"

    my_lib.footprint.clear(path)
    assert not my_lib.footprint.exists(path)
    assert my_lib.footprint.elapsed(path) > 10000

    my_lib.footprint.update(path)
    assert my_lib.footprint.exists(path)
    time.sleep(1)
    assert my_lib.footprint.elapsed(path) < 2

    my_lib.footprint.clear(path)
    assert not my_lib.footprint.exists(path)
    assert my_lib.footprint.elapsed(path) > 10000


def test_healthz():
    TEST_HEALTHZ_PATH = pathlib.Path("tests/data/healthz")

    import my_lib.healthz

    my_lib.footprint.clear(TEST_HEALTHZ_PATH)
    assert not my_lib.healthz.check_liveness("TEST", TEST_HEALTHZ_PATH, 5)

    my_lib.footprint.update(TEST_HEALTHZ_PATH)
    assert my_lib.healthz.check_liveness("TEST", TEST_HEALTHZ_PATH, 5)

    assert my_lib.healthz.check_http_port(80, "google.com")
    assert not my_lib.healthz.check_http_port(9999, "google.com")

    assert my_lib.healthz.check_tcp_port(80, "google.com")
    assert not my_lib.healthz.check_tcp_port(9999, "google.com")


def test_rpi():
    import my_lib.rpi

    PIN_NUM = 10

    my_lib.rpi.gpio.setwarnings(False)
    my_lib.rpi.gpio.setmode(my_lib.rpi.gpio.BCM)
    my_lib.rpi.gpio.setup(PIN_NUM, my_lib.rpi.gpio.OUT)

    my_lib.rpi.gpio.output(PIN_NUM, 0)
    assert my_lib.rpi.gpio.input(PIN_NUM) == 0

    my_lib.rpi.gpio.output(PIN_NUM, 1)
    assert my_lib.rpi.gpio.input(PIN_NUM) == 1

    time.sleep(1)

    my_lib.rpi.gpio.output(PIN_NUM, 0)
    assert my_lib.rpi.gpio.input(PIN_NUM) == 0

    assert my_lib.rpi.gpio.hist_get() == [
        {"pin_num": PIN_NUM, "state": "LOW"},
        {"pin_num": PIN_NUM, "state": "HIGH"},
        {"pin_num": PIN_NUM, "high_period": 1, "state": "LOW"},
    ]

    my_lib.rpi.gpio.hist_clear()
    assert my_lib.rpi.gpio.hist_get() == []

    my_lib.rpi.gpio.output(PIN_NUM, 0)

    my_lib.rpi.gpio.cleanup()


def test_notify_slack(mocker):
    import PIL.Image
    import slack_sdk

    config = my_lib.config.load(CONFIG_FILE)

    my_lib.notify.slack.hist_clear()
    my_lib.notify.slack.interval_clear()

    my_lib.notify.slack.info(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify.slack.hist_get() == []

    my_lib.notify.slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify.slack.hist_get() == ["This is Test"]

    my_lib.notify.slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify.slack.hist_get() == ["This is Test", "This is Test"]

    mocker.patch(
        "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
        return_value=True,
    )

    mocker.patch(
        "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
        side_effect=slack_sdk.errors.SlackClientError(),
    )
    my_lib.notify.slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    my_lib.notify.slack.hist_clear()
    my_lib.notify.slack.interval_clear()

    my_lib.notify.slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
    )

    assert my_lib.notify.slack.hist_get() == ["This is Test"]

    my_lib.notify.slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
    )

    assert my_lib.notify.slack.hist_get() == ["This is Test", "This is Test"]
    my_lib.notify.slack.interval_clear()

    with pytest.raises(ValueError, match="ch_id is None"):
        my_lib.notify.slack.error_with_image(
            config["slack"]["bot_token"],
            config["slack"]["error"]["channel"]["name"],
            None,
            "Test",
            "This is Test",
            {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
        )

    assert my_lib.notify.slack.hist_get() == ["This is Test", "This is Test", "This is Test"]
    my_lib.notify.slack.interval_clear()

    my_lib.notify.slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        None,
    )

    assert my_lib.notify.slack.hist_get() == ["This is Test", "This is Test", "This is Test", "This is Test"]


def test_pil_util():
    TEST_IMAGE_PATH = "tests/data/a.png"
    import PIL.Image

    import my_lib.pil_util

    font = my_lib.pil_util.get_font(
        {"path": "tests/data", "map": {"test": "migmix-1p-regular.ttf"}}, "test", 12
    )

    img = PIL.Image.new(
        "RGBA",
        (200, 200),
        (255, 255, 255, 0),
    )
    my_lib.pil_util.draw_text(img, "Test", (0, 0), font)
    my_lib.pil_util.draw_text(img, "Test", (0, 50), font, "right")
    my_lib.pil_util.draw_text(img, "Test", (0, 100), font, "center")

    img_gray = my_lib.pil_util.convert_to_gray(img)
    img_gray.save(TEST_IMAGE_PATH)

    my_lib.pil_util.load_image({"path": TEST_IMAGE_PATH, "scale": 1.2, "brightness": 1.1})
    my_lib.pil_util.load_image({"path": TEST_IMAGE_PATH, "scale": 1.1})
    my_lib.pil_util.load_image({"path": TEST_IMAGE_PATH, "brightness": 0.9})

    my_lib.pil_util.alpha_paste(img, img_gray, (0, 0))


def test_panel_util():
    import my_lib.panel_util

    config = my_lib.config.load(CONFIG_FILE)

    my_lib.panel_util.create_error_image(
        {"panel": {"width": 200, "height": 200}},
        {
            "path": "tests/data",
            "map": {"en_medium": "migmix-1p-regular.ttf", "en_bold": "migmix-1p-regular.ttf"},
        },
        "Test",
    )

    my_lib.panel_util.notify_error({}, "Test")
    my_lib.panel_util.notify_error(config, "Test")

    def draw_panel_pass(panel_config, font_config, slack_config, is_side_by_side, trial, opt_config):  # noqa: ARG001, PLR0913
        return

    def draw_panel_fail(panel_config, font_config, slack_config, is_side_by_side, trial, opt_config):  # noqa: ARG001, PLR0913
        raise Exception("Test")

    my_lib.panel_util.draw_panel_patiently(draw_panel_pass, {}, {}, {}, False)
    my_lib.panel_util.draw_panel_patiently(
        draw_panel_fail,
        {"panel": {"width": 100, "height": 100}},
        {
            "path": "tests/data",
            "map": {"en_medium": "migmix-1p-regular.ttf", "en_bold": "migmix-1p-regular.ttf"},
        },
        {},
        False,
    )


def test_selenium_util(mocker):
    import os

    import selenium.webdriver.common.by
    import selenium.webdriver.support.expected_conditions
    import selenium.webdriver.support.wait

    import my_lib.selenium_util

    TEST_URL = "https://example.net/"
    DUMP_PATH = pathlib.Path("tests/data/dump")

    driver = my_lib.selenium_util.create_driver("test", pathlib.Path("tests/data"))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 10)

    my_lib.selenium_util.warmup(driver, "yahoo.co.jp", "yahoo")

    driver.get(TEST_URL)
    my_lib.selenium_util.wait_patiently(
        driver,
        wait,
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, "//h1")
        ),
    )

    my_lib.selenium_util.click_xpath(driver, "//h1", wait)
    my_lib.selenium_util.click_xpath(driver, "//h10")
    my_lib.selenium_util.click_xpath(driver, "//h10", is_warn=False)

    assert my_lib.selenium_util.get_text(driver, "//h1", "TEST") != "TEST"
    assert my_lib.selenium_util.get_text(driver, "//h10", "TEST") == "TEST"

    my_lib.selenium_util.dump_page(driver, 0, DUMP_PATH)

    with my_lib.selenium_util.browser_tab(driver, TEST_URL):
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
                (selenium.webdriver.common.by.By.XPATH, "//h1")
            )
        )
        my_lib.selenium_util.is_display(driver, "//h1")

    with pytest.raises(selenium.common.exceptions.TimeoutException):
        my_lib.selenium_util.wait_patiently(
            driver,
            wait,
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (selenium.webdriver.common.by.By.XPATH, "//h10")
            ),
        )

    dummy_file_path = DUMP_PATH / "dummy.file"
    dummy_file_path.touch()
    os.utime(dummy_file_path, (0, 0))

    (DUMP_PATH / "dummy.dir").mkdir(parents=True, exist_ok=True)

    my_lib.selenium_util.clear_cache(driver)

    my_lib.selenium_util.clean_dump(DUMP_PATH)
    my_lib.selenium_util.clean_dump(pathlib.Path("tests/not_exists"))

    my_lib.selenium_util.log_memory_usage(driver)

    my_lib.selenium_util.random_sleep(0.5)

    driver.quit()

    mocker.patch("my_lib.selenium_util.create_driver_impl", side_effect=RuntimeError())

    with pytest.raises(RuntimeError):
        my_lib.selenium_util.create_driver("test", pathlib.Path("tests/data"))


def test_weather():
    import my_lib.weather

    my_lib.weather.get_weather_yahoo({"url": "https://weather.yahoo.co.jp/weather/jp/13/4410/13113.html"})
    my_lib.weather.get_clothing_yahoo({"url": "https://weather.yahoo.co.jp/weather/jp/13/4410/13113.html"})
    my_lib.weather.get_wbgt(
        {
            "data": {
                "env_go": {
                    "url": "https://www.wbgt.env.go.jp/graph_ref_td.php?region=03&prefecture=44&point=44132"
                }
            }
        }
    )
    my_lib.weather.get_sunset_nao({"data": {"nao": {"pref": 13}}})


def test_time():
    import datetime

    import my_lib.time

    assert isinstance(my_lib.time.now(), datetime.datetime)


def test_git_util():
    import my_lib.git_util

    assert my_lib.git_util.get_revision_str() != ""


def test_webapp_log_term():
    import my_lib.webapp.log

    config = my_lib.config.load(CONFIG_FILE)
    my_lib.webapp.config.init(config)
    my_lib.webapp.log.init(config)

    my_lib.webapp.log.term()

    # NOTE: 二重に呼んでもエラーにならないことを確認
    my_lib.webapp.log.term()


def test_json_util():
    import datetime

    import my_lib.json_util
    import my_lib.time

    # datetime オブジェクトのシリアライズ・デシリアライズテスト
    now = my_lib.time.now()
    json_str = my_lib.json_util.dumps(now)
    assert isinstance(json_str, str)
    assert now.isoformat() in json_str

    # JSON文字列からdatetimeオブジェクトへの復元テスト
    restored_now = my_lib.json_util.loads(json_str)
    assert isinstance(restored_now, datetime.datetime)
    assert restored_now == now

    # 複合オブジェクトのテスト
    data = {
        "timestamp": now,
        "name": "test",
        "count": 123,
        "nested": {"created_at": now, "items": [now, "string", 456]},
    }

    json_str = my_lib.json_util.dumps(data)
    restored_data = my_lib.json_util.loads(json_str)

    assert restored_data["timestamp"] == now
    assert restored_data["name"] == "test"
    assert restored_data["count"] == 123
    assert restored_data["nested"]["created_at"] == now
    assert restored_data["nested"]["items"][0] == now
    assert restored_data["nested"]["items"][1] == "string"
    assert restored_data["nested"]["items"][2] == 456

    # 通常のJSONデータのテスト（datetimeが含まれない場合）
    simple_data = {"name": "test", "value": 123}
    json_str = my_lib.json_util.dumps(simple_data)
    restored_simple = my_lib.json_util.loads(json_str)
    assert restored_simple == simple_data


def test_sqlite_util():
    import pathlib
    import tempfile
    import threading

    import my_lib.sqlite_util

    def connect_worker(db_path, worker_id, results):
        """ワーカースレッドが実行する関数"""
        try:
            start_time = time.time()
            db_conn = my_lib.sqlite_util.connect(db_path)
            conn = db_conn.get()
            elapsed_time = time.time() - start_time

            # 接続が成功したことを確認
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()
            results[worker_id] = {"success": True, "elapsed": elapsed_time}
        except Exception as e:
            results[worker_id] = {"success": False, "error": str(e)}

    # 同時接続テスト
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "concurrent_test.db"
        num_workers = 5
        threads = []
        results = {}

        # 複数のスレッドを起動
        for i in range(num_workers):
            thread = threading.Thread(target=connect_worker, args=(db_path, i, results))
            threads.append(thread)

        # すべてのスレッドを同時に開始
        for thread in threads:
            thread.start()

        # すべてのスレッドの完了を待つ
        for thread in threads:
            thread.join()

        # 結果を確認
        success_count = sum(1 for r in results.values() if r["success"])
        assert success_count == num_workers, f"Some workers failed: {results}"

        # データベースファイルが作成されたことを確認
        assert db_path.exists()

        # 既存データベースへの再接続テスト
        db_conn = my_lib.sqlite_util.connect(db_path)
        conn = db_conn.get()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()


@pytest.fixture
def slack_mock():
    # NOTE: デフォルトの slack_mock を上書き
    pass


@pytest.mark.mercari
def test_mercari_login(slack_mock):
    import os

    import selenium.webdriver.support.wait

    import my_lib.selenium_util
    import my_lib.store.mercari.login

    config = my_lib.config.load(CONFIG_FILE)
    config["slack"]["bot_token"] = os.environ.get("SLACK_BOT_TOKEN")

    driver = my_lib.selenium_util.create_driver("mercari", pathlib.Path(config["data"]["selenium"]))

    my_lib.selenium_util.clear_cache(driver)

    wait = selenium.webdriver.support.wait.WebDriverWait(driver, WAIT_TIMEOUT_SEC)

    my_lib.store.mercari.login.execute(
        driver,
        wait,
        os.environ.get("LINE_USER"),
        os.environ.get("LINE_PASS"),
        config["slack"],
        pathlib.Path(config["data"]["dump"]),
    )


@pytest.mark.mercari
def test_mercari_iter_items_on_display(slack_mock):
    import os
    import random

    import selenium.webdriver.support.wait

    import my_lib.selenium_util
    import my_lib.store.mercari.login
    import my_lib.store.mercari.scrape

    config = my_lib.config.load(CONFIG_FILE)
    config["slack"]["bot_token"] = os.environ.get("SLACK_BOT_TOKEN")

    dump_path = pathlib.Path(config["data"]["dump"])

    driver = my_lib.selenium_util.create_driver("mercari", pathlib.Path(config["data"]["selenium"]))

    my_lib.selenium_util.clear_cache(driver)

    wait = selenium.webdriver.support.wait.WebDriverWait(driver, WAIT_TIMEOUT_SEC)

    my_lib.store.mercari.login.execute(
        driver, wait, os.environ.get("LINE_USER"), os.environ.get("LINE_PASS"), config["slack"], dump_path
    )

    try:
        my_lib.store.mercari.scrape.iter_items_on_display(
            driver, wait, True, [lambda driver, wait, item, debug_mode: True]
        )
    except Exception:
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100), dump_path)  # noqa: S311
        raise
