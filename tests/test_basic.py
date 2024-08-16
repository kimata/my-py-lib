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

    # app_log_check(test_client, [])
    # ctrl_log_clear(test_client)

    yield test_client

    test_client.delete()


# def time_morning(offset_min=0):
#     return datetime.datetime.now(my_lib.webapp.config.TIMEZONE).replace(
#         hour=7, minute=0 + offset_min, second=0
#     )


# def time_evening(offset_min=0):
#     return datetime.datetime.now(my_lib.webapp.config.TIMEZONE).replace(
#         hour=17, minute=0 + offset_min, second=0
#     )


# def time_str(time):
#     return (time - datetime.timedelta(hours=int(my_lib.webapp.config.TIMEZONE_OFFSET))).strftime("%H:%M")


# def move_to(freezer, target_time):
#     freezer.move_to(target_time)


# SENSOR_DATA_DARK = {
#     "lux": {"valid": True, "value": 10},
#     "solar_rad": {"valid": True, "value": 10},
# }
# SENSOR_DATA_BRIGHT = {
#     "solar_rad": {"valid": True, "value": 200},
#     "lux": {"valid": True, "value": 2000},
# }


# def gen_schedule_data():
#     schedule_data = {
#         "is_active": True,
#         "solar_rad": 0,
#         "lux": 0,
#         "wday": [True] * 7,
#     }

#     return {
#         "open": schedule_data | {"time": time_str(time_morning(1)), "solar_rad": 150, "lux": 1000},
#         "close": schedule_data | {"time": time_str(time_evening(1)), "solar_rad": 80, "lux": 1200},
#     }


# def ctrl_log_clear(client):
#     response = client.get(
#         "/rasp-shutter/api/ctrl/log",
#         query_string={
#             "cmd": "clear",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"


def app_log_clear(client):
    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/api/log_clear")
    assert response.status_code == 200

    # def ctrl_log_check(client, expect):
    #     import logging

    #     response = client.get("/rasp-shutter/api/ctrl/log")
    #     assert response.status_code == 200
    #     assert response.json["result"] == "success"

    #     logging.debug(response.json["log"])

    #     assert response.json["log"] == expect

    # def ctrl_stat_clear():
    #     import my_lib.config

    #     my_lib.webapp.config.init(my_lib.config.load(CONFIG_FILE))

    #     import my_lib.webapp.config
    #     import rasp_shutter.config
    #     import rasp_shutter.webapp_control

    #     rasp_shutter.webapp_control.clean_stat_exec(my_lib.config.load(CONFIG_FILE))

    #     rasp_shutter.config.STAT_AUTO_CLOSE.unlink(missing_ok=True)

    # def check_notify_slack(message, index=-1):
    #     import logging

    #     import my_lib.notify_slack

    #     notify_hist = my_lib.notify_slack.hist_get()
    #     logging.debug(notify_hist)

    #     if message is None:
    #         assert notify_hist == [], "正常なはずなのに，エラー通知がされています。"
    #     else:
    #         assert len(notify_hist) != 0, "異常が発生したはずなのに，エラー通知がされていません。"
    #         assert notify_hist[index].find(message) != -1, f"「{message}」が Slack で通知されていません。"


######################################################################

# def test_time(freezer, client):  # n_oqa:  ARG001
#     import logging

#     import schedule

#     logging.debug("datetime.now()                 = %s", datetime.datetime.now())  # n_oqa: DTZ005
#     logging.debug("datetime.now(JST)            = %s", datetime.datetime.now(my_lib.webapp.config.TIMEZONE))
#     logging.debug(
#         "datetime.now().replace(...)    = %s",
#         datetime.datetime.now().replace(hour=0, minute=0, second=0),  # n_oqa: DTZ005
#     )
#     logging.debug(
#         "datetime.now(JST).replace(...) = %s",
#         datetime.datetime.now(my_lib.webapp.config.TIMEZONE).replace(hour=0, minute=0, second=0),
#     )

#     logging.debug("Freeze time at %s", time_str(time_morning(0)))

#     move_to(freezer, time_morning(0))

#     logging.debug(
#         "datetime.now()                 = %s",
#         datetime.datetime.now(),  # n_oqa: DTZ005
#     )
#     logging.debug("datetime.now(JST)            = %s", datetime.datetime.now(my_lib.webapp.config.TIMEZONE))

#     schedule.clear()
#     job_time_str = time_str(time_morning(1))
#     logging.debug("set schedule at %s", job_time_str)
#     job = schedule.every().day.at(job_time_str, my_lib.webapp.config.TIMEZONE_PYTZ).do(lambda: True)

#     idle_sec = schedule.idle_seconds()
#     logging.error("Time to next jobs is %.1f sec", idle_sec)
#     logging.debug("Next run is %s", job.next_run)

#     assert idle_sec < 60


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
            "log": False,
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(queue_put)

        response = client.get(
            data.sample_webapp.WEBAPP_URL_PREFIX + "/api/event", query_string={"count": "1"}
        )
        assert response.data.decode().split("\n\n")[0] == "data: dummy"
        assert (
            response.data.decode().split("\n\n")[1]
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


def test_flask_util(client):
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


def test_terminate():
    import my_lib.webapp.log

    my_lib.webapp.log.term()

    # NOTE: 二重に呼んでもエラーにならないことを確認
    my_lib.webapp.log.term()
