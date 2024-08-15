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

# from app import create_app

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


def test_webapp_base(client, mocker):
    response = client.get("/")

    assert response.status_code == 302
    assert re.search(rf"{data.sample_webapp.WEBAPP_URL_PREFIX}/$", response.location)

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/")
    assert response.status_code == 200
    assert "Test Data" in response.data.decode("utf-8")

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX + "/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200

    mocker.patch(
        "flask.wrappers.Response.status_code",
        return_value=301,
        new_callable=mocker.PropertyMock,
    )

    response = client.get(data.sample_webapp.WEBAPP_URL_PREFIX, headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 301


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


#     else:
#         snapshot = tracemalloc.take_snapshot()
#         top_stats = snapshot.compare_to(snapshot_prev, "lineno")
#         snapshot_prev = snapshot

#         return flask.jsonify([str(stat) for stat in top_stats[:10]])


# @blueprint.route("/api/sysinfo", methods=["GET"])
# @my_lib.flask_util.support_jsonp
# def api_sysinfo():
#     return flask.jsonify(
#         {


# def test_shutter_ctrl_read(client):
#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR"])
#     check_notify_slack(None)


# def test_shutter_ctrl_inconsistent_read(client):
#     import my_lib.footprint
#     import rasp_shutter.webapp_control

#     # NOTE: 本来ないはずの，oepn と close の両方のファイルが存在する場合 (close が後)
#     ctrl_stat_clear()
#     my_lib.footprint.update(rasp_shutter.webapp_control.exec_stat_file("open", 0))
#     time.sleep(0.1)
#     my_lib.footprint.update(rasp_shutter.webapp_control.exec_stat_file("close", 0))

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     assert response.json["state"][0]["state"] == rasp_shutter.webapp_control.SHUTTER_STATE.CLOSE
#     assert response.json["state"][1]["state"] == rasp_shutter.webapp_control.SHUTTER_STATE.UNKNOWN

#     # NOTE: 本来ないはずの，oepn と close の両方のファイルが存在する場合 (open が後)
#     ctrl_stat_clear()
#     my_lib.footprint.update(rasp_shutter.webapp_control.exec_stat_file("close", 1))
#     time.sleep(0.1)
#     my_lib.footprint.update(rasp_shutter.webapp_control.exec_stat_file("open", 1))

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     assert response.json["state"][1]["state"] == rasp_shutter.webapp_control.SHUTTER_STATE.OPEN
#     assert response.json["state"][0]["state"] == rasp_shutter.webapp_control.SHUTTER_STATE.UNKNOWN
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR"])
#     check_notify_slack(None)


# def test_valve_ctrl_manual_single_1(client):
#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 0,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(client, [{"index": 0, "state": "open"}])

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 0,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(client, [{"index": 0, "state": "open"}, {"index": 0, "state": "close"}])
#     app_log_check(client, ["CLEAR", "OPEN_MANUAL", "CLOSE_MANUAL"])
#     check_notify_slack(None)


# def test_valve_ctrl_manual_single_2(client):
#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(client, [{"index": 1, "state": "open"}])

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(client, [{"index": 1, "state": "open"}, {"index": 1, "state": "close"}])
#     app_log_check(client, ["CLEAR", "OPEN_MANUAL", "CLOSE_MANUAL"])
#     check_notify_slack(None)


# def test_valve_ctrl_manual_all(client):
#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 0,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(client, [{"index": 0, "state": "open"}])

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(client, [{"index": 0, "state": "open"}, {"index": 1, "state": "open"}])

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 0,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#             {"index": 0, "state": "close"},
#         ],
#     )

#     ctrl_log_clear(client)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(2)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "CLOSE_PENDING",
#             "CLOSE_PENDING",
#         ],
#     )
#     check_notify_slack(None)


# def test_valve_ctrl_manual_single_fail(client, mocker):
#     import requests

#     # NOTE: このテストだけは，制御の止め方を変える
#     def request_mock(url, timeout):  # n_oqa: ARG001
#         request_mock.i += 1
#         response = requests.models.Response()
#         if request_mock.i == 1:
#             response.status_code = 500
#         else:
#             response.status_code = 200
#         return response

#     request_mock.i = 0

#     mocker.patch.dict(os.environ, {"DUMMY_MODE": "false"}, clear=True)
#     mocker.patch("rasp_shutter.webapp_control.requests.get", side_effect=request_mock)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 1, "state": "open"},
#         ],
#     )

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#         ],
#     )
#     app_log_check(client, ["CLEAR", "OPEN_FAIL", "CLOSE_MANUAL"])
#     check_notify_slack("手動で開けるのに失敗しました")

#     # NOTE: ログを出し切らせる
#     time.sleep(1)


# def test_event(client):
#     response = client.get("/rasp-shutter/api/event", query_string={"count": "1"})
#     assert response.status_code == 200
#     assert response.data.decode()

#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR"])
#     check_notify_slack(None)


# def test_schedule_ctrl_inactive(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     move_to(freezer, time_evening(3))
#     time.sleep(1)

#     schedule_data["open"]["is_active"] = True
#     schedule_data["open"]["wday"] = [False] * 7
#     schedule_data["close"]["is_active"] = True
#     schedule_data["close"]["wday"] = [False] * 7
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     move_to(freezer, time_evening(3))
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR", "SCHEDULE", "SCHEDULE"])
#     check_notify_slack(None)


# def test_schedule_ctrl_invalid(client):
#     schedule_data = gen_schedule_data()
#     del schedule_data["open"]
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     del schedule_data["open"]["is_active"]
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = "TEST"
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["lux"] = "TEST"
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["solar_rad"] = "TEST"
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["time"] = "TEST"
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["wday"] = [True] * 5
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["wday"] = ["TEST"] * 7
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(5)

#     ctrl_log_check(client, [])
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#             "INVALID",
#         ],
#     )
#     check_notify_slack("スケジュールの指定が不正です。")


# def test_schedule_ctrl_execute(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})
#     mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data", return_value=SENSOR_DATA_BRIGHT)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     move_to(freezer, time_evening(0))
#     time.sleep(1)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#             {"index": 0, "state": "close"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "CLOSE_MANUAL",
#             "SCHEDULE",
#             "CLOSE_SCHEDULE",
#             "CLOSE_PENDING",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_auto_close(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})
#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_evening(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     schedule_data["close"]["time"] = time_str(time_evening(5))
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     move_to(freezer, time_evening(3))
#     time.sleep(1)

#     move_to(freezer, time_evening(4))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     move_to(freezer, time_evening(5))
#     time.sleep(1)

#     move_to(freezer, time_evening(6))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "SCHEDULE",
#             "CLOSE_DARK",
#             "CLOSE_AUTO",
#             "CLOSE_AUTO",
#             "CLOSE_PENDING",
#             "CLOSE_PENDING",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_auto_close_dup(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})
#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_evening(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["time"] = time_str(time_evening(4))
#     schedule_data["open"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     move_to(freezer, time_evening(3))
#     time.sleep(2)

#     move_to(freezer, time_evening(4))
#     time.sleep(2)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#             {"index": 0, "state": "close"},
#         ],
#     )

#     move_to(freezer, time_evening(5))
#     time.sleep(2)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 1, "state": "close"},
#             {"index": 0, "state": "close"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "CLOSE_MANUAL",
#             "SCHEDULE",
#             "CLOSE_DARK",
#             "CLOSE_AUTO",
#             "CLOSE_PENDING",
#             "CLOSE_PENDING",
#             "CLOSE_PENDING",
#         ],
#     )

#     check_notify_slack(None)


# def test_schedule_ctrl_auto_reopen(client, mocker, freezer):  # n_oqa: PLR0915
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["time"] = time_str(time_morning(2))
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(2)

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(4))
#     time.sleep(1)

#     # OPEN
#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     move_to(freezer, time_morning(5))
#     time.sleep(1)

#     # NOT CLOSE (自動的に開いてから時間が経過してない)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     move_to(freezer, time_morning(10))
#     time.sleep(1)

#     # CLOSE
#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(11))
#     time.sleep(1)

#     # NOT OPEN (自動的に閉じてから時間が経過してない)
#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     move_to(freezer, time_morning(12))
#     time.sleep(1)

#     # NOT CLOSE (開いていない)
#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(20))
#     time.sleep(2)

#     # OPEN

#     move_to(freezer, time_evening(1))
#     time.sleep(2)

#     # CLOSE

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     move_to(freezer, time_evening(3))
#     time.sleep(1)

#     response = client.get("/rasp-shutter/api/ctrl/log")
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "SCHEDULE",
#             "OPEN_PENDING",
#             "OPEN_BRIGHT",
#             "OPEN_AUTO",
#             "OPEN_AUTO",
#             "CLOSE_DARK",
#             "CLOSE_AUTO",
#             "CLOSE_AUTO",
#             "OPEN_BRIGHT",
#             "OPEN_AUTO",
#             "OPEN_AUTO",
#             "CLOSE_SCHEDULE",
#             "CLOSE_SCHEDULE",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_auto_inactive(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR", "SCHEDULE"])
#     check_notify_slack(None)


# def test_schedule_ctrl_pending_open(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["time"] = time_str(time_morning(3))
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     move_to(freezer, time_morning(3))
#     time.sleep(2)

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(4))
#     time.sleep(2)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "SCHEDULE",
#             "OPEN_PENDING",
#             "OPEN_BRIGHT",
#             "OPEN_AUTO",
#             "OPEN_AUTO",
#         ],
#     )

#     check_notify_slack(None)


# def test_schedule_ctrl_pending_open_inactive(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#         ],
#     )

#     # NOTE: pending open になった後に，open が inactive
#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(4))
#     time.sleep(1)

#     move_to(freezer, time_morning(5))
#     time.sleep(1)

#     move_to(freezer, time_morning(6))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "SCHEDULE",
#             "OPEN_PENDING",
#             "SCHEDULE",
#         ],
#     )
#     check_notify_slack(None)


# # NOTE: 開けるのを延期したあとでセンサーエラー
# def test_schedule_ctrl_pending_open_fail(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     sensor_data = SENSOR_DATA_BRIGHT.copy()
#     sensor_data["lux"] = {"valid": False, "value": 5000}
#     sensor_data_mock.return_value = sensor_data

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     move_to(freezer, time_morning(4))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"cmd": "pending", "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         ["CLEAR", "CLOSE_MANUAL", "CLOSE_MANUAL", "SCHEDULE", "OPEN_PENDING"],
#     )

#     check_notify_slack(None)

#     # NOTE: 後始末
#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT.copy()
#     move_to(freezer, time_morning(5))
#     time.sleep(1)


# def test_schedule_ctrl_open_dup(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data", return_value=SENSOR_DATA_BRIGHT)

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["time"] = time_str(time_morning(1))
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "SCHEDULE",
#             "OPEN_PENDING",
#             "OPEN_PENDING",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_pending_open_dup(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "close",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "index": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_DARK

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(2)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"index": 1, "state": "open"},
#             {"cmd": "pending", "state": "open"},
#         ],
#     )

#     sensor_data_mock.return_value = SENSOR_DATA_BRIGHT

#     move_to(freezer, time_morning(3))
#     time.sleep(1)

#     move_to(freezer, time_morning(4))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "close"},
#             {"index": 1, "state": "close"},
#             {"index": 1, "state": "open"},
#             {"cmd": "pending", "state": "open"},
#             {"index": 0, "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "CLOSE_MANUAL",
#             "CLOSE_MANUAL",
#             "OPEN_MANUAL",
#             "SCHEDULE",
#             "OPEN_PENDING",
#             "OPEN_BRIGHT",
#             "OPEN_AUTO",
#             "OPEN_PENDING",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_control_fail_1(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("rasp_shutter.scheduler.exec_shutter_control_impl", return_value=False)
#     mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data", return_value=SENSOR_DATA_DARK)

#     move_to(freezer, time_evening(0))
#     time.sleep(0.5)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     move_to(freezer, time_evening(3))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )
#     app_log_check(
#         client,
#         [
#             "CLEAR",
#             "OPEN_MANUAL",
#             "OPEN_MANUAL",
#             "SCHEDULE",
#             "FAIL_CONTROL",
#         ],
#     )
#     check_notify_slack(None)


# def test_schedule_ctrl_control_fail_2(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data", return_value=SENSOR_DATA_DARK)

#     response = client.get(
#         "/rasp-shutter/api/shutter_ctrl",
#         query_string={
#             "cmd": 1,
#             "state": "open",
#         },
#     )
#     assert response.status_code == 200
#     assert response.json["result"] == "success"

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )

#     mocker.patch(
#         "rasp_shutter.scheduler.rasp_shutter.webapp_control.set_shutter_state",
#         side_effect=RuntimeError(),
#     )

#     move_to(freezer, time_evening(0))
#     time.sleep(0.5)

#     schedule_data = gen_schedule_data()
#     schedule_data["open"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_evening(1))
#     time.sleep(1)

#     move_to(freezer, time_evening(2))
#     time.sleep(1)

#     ctrl_log_check(
#         client,
#         [
#             {"index": 0, "state": "open"},
#             {"index": 1, "state": "open"},
#         ],
#     )
#     app_log_check(client, ["CLEAR", "OPEN_MANUAL", "OPEN_MANUAL", "SCHEDULE", "FAIL_CONTROL"])
#     check_notify_slack(None)


# def test_schedule_ctrl_invalid_sensor_1(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     sensor_data = SENSOR_DATA_BRIGHT.copy()
#     sensor_data["lux"] = {"valid": False, "value": 5000}
#     sensor_data_mock.return_value = sensor_data

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(1)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR", "SCHEDULE", "FAIL_SENSOR"])
#     check_notify_slack("センサの値が不明なので開けるのを見合わせました。")


# def test_schedule_ctrl_invalid_sensor_2(client, mocker, freezer):
#     mocker.patch.dict("os.environ", {"FROZEN": "true"})

#     mocker.patch("slack_sdk.WebClient.chat_postMessage", return_value=True)
#     sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")

#     move_to(freezer, time_morning(0))
#     time.sleep(0.5)

#     sensor_data = SENSOR_DATA_BRIGHT.copy()
#     sensor_data["solar_rad"] = {"valid": False, "value": 5000}
#     sensor_data_mock.return_value = sensor_data

#     schedule_data = gen_schedule_data()
#     schedule_data["close"]["is_active"] = False
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200
#     time.sleep(1)

#     move_to(freezer, time_morning(1))
#     time.sleep(2)

#     move_to(freezer, time_morning(2))
#     time.sleep(1)

#     ctrl_log_check(client, [])
#     app_log_check(client, ["CLEAR", "SCHEDULE", "FAIL_SENSOR"])
#     check_notify_slack("センサの値が不明なので開けるのを見合わせました。")


# def test_schedule_ctrl_read(client):
#     response = client.get("/rasp-shutter/api/schedule_ctrl")
#     assert response.status_code == 200
#     assert len(response.json) == 2


# def test_schedule_ctrl_read_fail_1(client, mocker):
#     schedule_data = gen_schedule_data()
#     del schedule_data["open"]

#     mocker.patch("pickle.load", return_value=schedule_data)

#     response = client.get("/rasp-shutter/api/schedule_ctrl")
#     assert response.status_code == 200
#     assert len(response.json) == 2


# def test_schedule_ctrl_read_fail_2(client):
#     with pathlib.Path(my_lib.webapp.config.SCHEDULE_FILE_PATH).open(mode="wb") as f:
#         f.write(b"TEST")

#     response = client.get("/rasp-shutter/api/schedule_ctrl")
#     assert response.status_code == 200
#     assert len(response.json) == 2


# def test_schedule_ctrl_write_fail(client, mocker):
#     mocker.patch("pickle.dump", side_effect=RuntimeError())

#     schedule_data = gen_schedule_data()
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200

#     # NOTE: 次回のテストに向けて，正常なものに戻しておく
#     schedule_data = gen_schedule_data()
#     response = client.get(
#         "/rasp-shutter/api/schedule_ctrl",
#         query_string={"cmd": "set", "data": json.dumps(schedule_data)},
#     )
#     assert response.status_code == 200


# def test_schedule_ctrl_validate_fail(client, mocker):
#     mocker.patch("rasp_shutter.scheduler.schedule_validate", return_value=False)

#     response = client.get("/rasp-shutter/api/schedule_ctrl")
#     assert response.status_code == 200
#     assert len(response.json) == 2


# def test_shutter_list(client):
#     response = client.get("/rasp-shutter/api/shutter_list")
#     assert response.status_code == 200


# def test_dummy_open(client):
#     response = client.get("/rasp-shutter/api/dummy/open")
#     assert response.status_code == 200


# def test_dummy_close(client):
#     response = client.get("/rasp-shutter/api/dummy/close")
#     assert response.status_code == 200


# def test_sensor_1(client):
#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200


# def test_sensor_2(client, mocker):
#     mocker.patch("my_lib.sensor_data.fetch_data", return_value={"valid": False})

#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200

#     mocker.patch(
#         "my_lib.sensor_data.fetch_data",
#         return_value={
#             "valid": True,
#             "value": [0],
#             "time": [datetime.datetime.now(datetime.timezone.utc)],
#         },
#     )

#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200


# def test_sensor_dummy(client, mocker):
#     # NOTE: 何かがまだ足りない
#     def value_mock():
#         value_mock.i += 1
#         if value_mock.i == 1:
#             return None
#         else:
#             return 1

#     value_mock.i = 0

#     table_entry_mock = mocker.MagicMock()
#     record_mock = mocker.MagicMock()
#     query_api_mock = mocker.MagicMock()
#     mocker.patch.object(
#         record_mock,
#         "get_value",
#         side_effect=value_mock,
#     )
#     mocker.patch.object(
#         record_mock,
#         "get_time",
#         return_value=datetime.datetime.now(datetime.timezone.utc),
#     )
#     table_entry_mock.__iter__.return_value = [record_mock, record_mock]
#     type(table_entry_mock).records = table_entry_mock
#     query_api_mock.query.return_value = [table_entry_mock]
#     mocker.patch(
#         "influxdb_client.InfluxDBClient.query_api",
#         return_value=query_api_mock,
#     )

#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200


# def test_sensor_fail_1(client, mocker):
#     mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200


# def test_sensor_fail_2(client, mocker):
#     mocker.patch(
#         "influxdb_client.client.flux_table.FluxRecord.get_value",
#         return_value=None,
#     )

#     response = client.get("/rasp-shutter/api/sensor")
#     assert response.status_code == 200


# def test_log_view(client):
#     response = client.get(
#         "/rasp-shutter/api/log_view",
#         headers={"Accept-Encoding": "gzip"},
#         query_string={
#             "callback": "TEST",
#         },
#     )
#     assert response.status_code == 200


# def test_log_clear(client):
#     response = client.get("/rasp-shutter/api/log_clear")
#     assert response.status_code == 200

#     response = client.get(
#         "/rasp-shutter/api/log_view",
#         headers={"Accept-Encoding": "gzip"},
#         query_string={
#             "callback": "TEST",
#         },
#     )
#     assert response.status_code == 200


# def test_sysinfo(client):
#     response = client.get("/rasp-shutter/api/sysinfo")
#     assert response.status_code == 200
#     assert "date" in response.json
#     assert "uptime" in response.json
#     assert "loadAverage" in response.json


# def test_snapshot(client):
#     response = client.get("/rasp-shutter/api/snapshot")
#     assert response.status_code == 200
#     assert "msg" in response.json
#     response = client.get("/rasp-shutter/api/snapshot")
#     assert response.status_code == 200
#     assert "msg" not in response.json


# def test_memory(client):
#     response = client.get("/rasp-shutter/api/memory")
#     assert response.status_code == 200
#     assert "memory" in response.json


# def test_second_str():
#     import rasp_shutter.webapp_control

#     assert rasp_shutter.webapp_control.time_str(3600) == "1時間"
#     assert rasp_shutter.webapp_control.time_str(3660) == "1時間1分"
#     assert rasp_shutter.webapp_control.time_str(50) == "50秒"


def test_terminate():
    import my_lib.webapp.log

    my_lib.webapp.log.term()

    # NOTE: 二重に呼んでもエラーにならないことを確認
    my_lib.webapp.log.term()
