#!/usr/bin/env python3
# ruff: noqa: S101

import pathlib
import re
import time
import unittest

import data.sample_webapp
import my_lib.config
import my_lib.notify.slack
import my_lib.webapp.config
import pytest

CONFIG_FILE = "tests/data/config.example.yaml"


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
    with unittest.mock.patch(
        "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def app():
    my_lib.webapp.config.init(my_lib.config.load(CONFIG_FILE))

    with unittest.mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        app = data.sample_webapp.create_app(CONFIG_FILE)

        yield app

        # NOTE: ログをクリア
        test_webapp_log_term()


@pytest.fixture()
def client(app):
    test_client = app.test_client()

    time.sleep(1)
    app_log_clear(test_client)

    yield test_client

    test_client.delete()


def app_log_clear(client):
    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_clear")
    assert response.status_code == 200


######################################################################
def test_webapp_config():
    my_lib.webapp.config.init({"webapp": {}})
    my_lib.webapp.config.init({"webapp": {"timezone": {"offset": "+9"}, "data": {"schedule_file_path": "/"}}})
    my_lib.webapp.config.init({"webapp": {"timezone": {}}})


def test_webapp_base(client):
    response = client.get("/")

    assert response.status_code == 302
    assert re.search(rf"{data.sample_webapp.WEBAPP_URL_PREFIX}/$", response.location)

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/")
    assert response.status_code == 200
    assert "Test Data" in response.data.decode("utf-8")

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200


def test_webapp_log(client):
    response = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_clear",
        query_string={
            "log": "false",
        },
    )
    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_view")
    assert response.status_code == 200
    log_list = response.json["data"]

    assert len(log_list) == 0

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/log_write")
    assert response.status_code == 200
    time.sleep(1)

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_view")
    assert response.status_code == 200
    log_list = response.json["data"]
    time.sleep(2)

    assert log_list[0]["message"] == "TEST WARN"
    assert log_list[1]["message"] == "TEST ERROR"


def test_webapp_event(client):
    import concurrent.futures
    import multiprocessing

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "1"})
    assert response.status_code == 200
    assert response.data.decode()

    # NOTE: event に先にアクセスさせておいてから，ログに書き込む
    def log_write():
        time.sleep(3)
        client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/log_write")

    my_lib.webapp.event.YEILD_TIMEOUT = 4

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(log_write)

        response = client.get(
            data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "1"}
        )
        assert response.data.decode().split("\n\n")[0] == "data: dummy"
        assert response.data.decode().split("\n\n")[1] == "data: log"
        future.result()

    queue = multiprocessing.Queue()
    my_lib.webapp.event.notify_watch(queue)

    def queue_put():
        time.sleep(3)
        queue.put(my_lib.webapp.event.EVENT_TYPE.SCHEDULE)
        queue.put(my_lib.webapp.event.EVENT_TYPE.CONTROL)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(queue_put)

        response = client.get(
            data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "2"}
        )
        assert response.data.decode().split("\n\n")[0] == "data: dummy"
        assert (
            response.data.decode().split("\n\n")[1] == f"data: {my_lib.webapp.event.EVENT_TYPE.CONTROL.value}"
        )
        assert (
            response.data.decode().split("\n\n")[2]
            == f"data: {my_lib.webapp.event.EVENT_TYPE.SCHEDULE.value}"
        )
        future.result()

    my_lib.webapp.event.stop_watch()


def test_webapp_util(client):
    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/memory")
    assert response.status_code == 200
    assert "memory" in response.json

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/snapshot")
    assert response.status_code == 200
    assert response.json["msg"] == "taken snapshot"

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/snapshot")
    assert response.status_code == 200
    assert type(response.json) is list
    assert len(response.json) != 0

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/sysinfo")
    assert response.status_code == 200
    assert "loadAverage" in response.json


def test_flask_util(client, mocker):
    response = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/gzipped/through",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 302

    response = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "max-age=86400"

    response = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/gzipped/disable_cache",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, must-revalidate"
    assert response.headers["Expires"] == "0"

    response = client.get(
        data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/support_jsonp",
        query_string={
            "callback": "CALL",
        },
    )
    assert response.status_code == 200
    assert response.data.decode("utf-8") == """CALL({"status":"OK"})"""

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/remote_host")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "localhost, Unknown"

    mocker.patch("socket.gethostbyaddr", side_effect=RuntimeError())

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/exec/remote_host")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "127.0.0.1, Unknown"


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

    assert my_lib.healthz.check_port(80, "google.com")
    assert not my_lib.healthz.check_port(9999, "google.com")


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
        retunr_value=True,
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
    import my_lib.pil_util
    import PIL.Image

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
        raise Exception("Test")  # noqa: EM101, TRY002

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

    import my_lib.selenium_util
    import selenium.webdriver.common.by
    import selenium.webdriver.support.wait

    TEST_URL = "https://example.com/"
    DUMP_PATH = pathlib.Path("tests/data/dump")

    driver = my_lib.selenium_util.create_driver("test", pathlib.Path("tests/data"))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 0.5)

    my_lib.selenium_util.warmup(driver, "Yaoo.co.jp", "yahoo", 0.5)

    driver.get(TEST_URL)

    my_lib.selenium_util.click_xpath(driver, "//h1", wait)
    my_lib.selenium_util.click_xpath(driver, "//h10")
    my_lib.selenium_util.click_xpath(driver, "//h10", is_warn=False)

    with my_lib.selenium_util.browser_tab(driver, TEST_URL):
        my_lib.selenium_util.is_display(driver, "//h1")

    my_lib.selenium_util.wait_patiently(
        driver,
        wait,
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, "//h1")
        ),
    )
    with pytest.raises(selenium.common.exceptions.TimeoutException):
        my_lib.selenium_util.wait_patiently(
            driver,
            wait,
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (selenium.webdriver.common.by.By.XPATH, "//h10")
            ),
        )

    assert my_lib.selenium_util.get_text(driver, "//h1", "TEST") != "TEST"
    assert my_lib.selenium_util.get_text(driver, "//h10", "TEST") == "TEST"

    my_lib.selenium_util.dump_page(driver, 0, DUMP_PATH)

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


def test_webapp_log_term():
    import my_lib.webapp.log

    my_lib.webapp.log.term()

    # NOTE: 二重に呼んでもエラーにならないことを確認
    my_lib.webapp.log.term()
