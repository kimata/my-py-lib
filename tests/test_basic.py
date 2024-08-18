#!/usr/bin/env python3
# ruff: noqa: S101

import re
import time
from unittest import mock

import data.sample_webapp
import my_lib.config
import my_lib.notify_slack
import my_lib.webapp.config
import pytest

CONFIG_FILE = "tests/data/config.example.yaml"


@pytest.fixture(scope="session", autouse=True)
def env_mock():
    with mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    with mock.patch(
        "my_lib.notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def app():
    my_lib.webapp.config.init(my_lib.config.load(CONFIG_FILE))

    with mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        app = data.sample_webapp.create_app(CONFIG_FILE)

        yield app

        # NOTE: 特定のテストのみ実行したときのため，ここでも呼ぶ
        test_terminate()


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
        {"state": "LOW"},
        {"state": "HIHG"},
        {"period": 1, "state": "LOW"},
    ]

    my_lib.rpi.gpio.hist_clear()

    assert my_lib.rpi.gpio.hist_get() == []


def test_notify_slack(mocker):
    import PIL.Image
    import slack_sdk

    config = my_lib.config.load(CONFIG_FILE)

    my_lib.notify_slack.hist_clear()
    my_lib.notify_slack.interval_clear()

    my_lib.notify_slack.info(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify_slack.hist_get() == []

    my_lib.notify_slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify_slack.hist_get() == ["This is Test"]

    my_lib.notify_slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    assert my_lib.notify_slack.hist_get() == ["This is Test", "This is Test"]

    mocker.patch(
        "my_lib.notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    )

    mocker.patch(
        "my_lib.notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        side_effect=slack_sdk.errors.SlackClientError(),
    )
    my_lib.notify_slack.error(
        config["slack"]["bot_token"], config["slack"]["error"]["channel"]["name"], "Test", "This is Test"
    )

    my_lib.notify_slack.hist_clear()
    my_lib.notify_slack.interval_clear()

    my_lib.notify_slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
    )

    assert my_lib.notify_slack.hist_get() == ["This is Test"]

    my_lib.notify_slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
    )

    assert my_lib.notify_slack.hist_get() == ["This is Test", "This is Test"]
    my_lib.notify_slack.interval_clear()

    with pytest.raises(ValueError, match="ch_id is None"):
        my_lib.notify_slack.error_with_image(
            config["slack"]["bot_token"],
            config["slack"]["error"]["channel"]["name"],
            None,
            "Test",
            "This is Test",
            {"data": PIL.Image.new("RGB", (512, 512)), "text": "dumny"},
        )

    assert my_lib.notify_slack.hist_get() == ["This is Test", "This is Test", "This is Test"]
    my_lib.notify_slack.interval_clear()

    my_lib.notify_slack.error_with_image(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["error"]["channel"]["id"],
        "Test",
        "This is Test",
        None,
    )

    assert my_lib.notify_slack.hist_get() == ["This is Test", "This is Test", "This is Test", "This is Test"]


def test_terminate():
    import my_lib.webapp.log

    my_lib.webapp.log.term()

    # NOTE: 二重に呼んでもエラーにならないことを確認
    my_lib.webapp.log.term()
