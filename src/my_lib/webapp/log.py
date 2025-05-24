#!/usr/bin/env python3
"""
Web アプリでログを表示します。

Usage:
  log.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

import datetime
import enum
import json
import logging
import multiprocessing
import os
import sqlite3
import threading
import time
import traceback
import wsgiref.handlers

import my_lib.flask_util
import my_lib.notify.slack
import my_lib.webapp.config
import my_lib.webapp.event

import flask


class LOG_LEVEL(enum.Enum):  # noqa: N801
    INFO = 0
    WARN = 1
    ERROR = 2


blueprint = flask.Blueprint("webapp-log", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

sqlite = None
log_thread = None
log_lock = None
log_queue = None
config = None
should_terminate = False


def init(config_, is_read_only=False):
    global config  # noqa: PLW0603
    global sqlite  # noqa: PLW0603
    global log_lock  # noqa: PLW0603
    global log_queue  # noqa: PLW0603
    global log_thread  # noqa: PLW0603
    global should_terminate  # noqa: PLW0603

    config = config_

    if sqlite is not None:
        raise ValueError("sqlite should be None")  # noqa: TRY003, EM101

    my_lib.webapp.config.LOG_DIR_PATH.parent.mkdir(parents=True, exist_ok=True)
    sqlite = sqlite3.connect(my_lib.webapp.config.LOG_DIR_PATH, check_same_thread=False)
    sqlite.execute(
        "CREATE TABLE IF NOT EXISTS log(id INTEGER primary key autoincrement, date INTEGER, message TEXT)"
    )
    sqlite.execute("PRAGMA journal_mode=WAL")
    sqlite.commit()
    sqlite.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    if not is_read_only:
        should_terminate = False

        # NOTE: atexit とかでログを出したい場合もあるので、Queue はここで閉じる。
        if log_queue is not None:
            log_queue.close()

        log_lock = threading.Lock()
        log_queue = multiprocessing.Queue()
        log_thread = threading.Thread(target=worker, args=(log_queue,))

        log_thread.start()


def term(is_read_only=False):
    global sqlite  # noqa: PLW0603
    global log_thread  # noqa: PLW0603
    global should_terminate  # noqa: PLW0603

    if sqlite is not None:
        sqlite.close()
        sqlite = None

    if not is_read_only:
        if log_thread is None:
            return
        should_terminate = True

        log_thread.join()
        log_thread = None


def log_impl(message, level):
    global config
    global sqlite

    logging.debug("insert: [%s] %s", LOG_LEVEL(level).name, message)

    with log_lock:
        sqlite.execute(
            'INSERT INTO log VALUES (NULL, DATETIME("now"), ?)',
            [message],
        )
        sqlite.execute('DELETE FROM log WHERE date <= DATETIME("now", "-60 days")')
        sqlite.commit()

        my_lib.webapp.event.notify_event(my_lib.webapp.event.EVENT_TYPE.LOG)

    if level == LOG_LEVEL.ERROR:
        if "slack" in config:
            my_lib.notify.slack.error(
                config["slack"]["bot_token"],
                config["slack"]["error"]["channel"]["name"],
                config["slack"]["from"],
                message,
                config["slack"]["error"]["interval_min"],
            )

        if (os.environ.get("DUMMY_MODE", "false") == "true") and (
            os.environ.get("TEST", "false") != "true"
        ):  # pragma: no cover
            logging.error("This application is terminated because it is in dummy mode.")
            os._exit(-1)


def worker(log_queue):
    global should_terminate

    sleep_sec = 0.1

    while True:
        if should_terminate:
            break

        try:
            while not log_queue.empty():
                logging.debug("Found %d log message(s)", log_queue.qsize())
                log = log_queue.get()
                log_impl(log["message"], log["level"])
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際、freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
        except ValueError:  # pragma: no cover
            # NOTE: 終了時、queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する。
            logging.warning(traceback.format_exc())

        time.sleep(sleep_sec)


def add(message, level):
    global log_queue

    # NOTE: 実際のログ記録は別スレッドに任せて、すぐにリターンする
    log_queue.put({"message": message, "level": level})


def error(message):
    logging.error(message)

    add(message, LOG_LEVEL.ERROR)


def warning(message):
    logging.warning(message)

    add(message, LOG_LEVEL.WARN)


def info(message):
    logging.info(message)

    add(message, LOG_LEVEL.INFO)


def get(stop_day):
    global sqlite

    cur = sqlite.cursor()
    cur.execute(
        'SELECT * FROM log WHERE date <= DATETIME("now", ?) ORDER BY id DESC LIMIT 500',
        # NOTE: デモ用に stop_day 日前までののログしか出さない指定ができるようにする
        [f"-{stop_day} days"],
    )
    log_list = [dict(log) for log in cur.fetchall()]
    for log in log_list:
        log["date"] = (
            datetime.datetime.strptime(log["date"], "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=datetime.timezone.utc)
            .astimezone(my_lib.time.get_zoneinfo())
            .strftime("%Y-%m-%d %H:%M:%S")
        )

    return log_list


def clear():
    global sqlite

    with log_lock:
        cur = sqlite.cursor()
        cur.execute("DELETE FROM log")


@blueprint.route("/api/log_add", methods=["POST"])
@my_lib.flask_util.support_jsonp
def api_log_add():
    if not flask.current_app.config["TEST"]:
        flask.abort(403)

    message = flask.request.form.get("message", "")
    level = flask.request.form.get("level", LOG_LEVEL.INFO, type=lambda x: LOG_LEVEL[x])

    logging.info([message, level])

    add(message, level)

    return flask.jsonify({"result": "success"})


@blueprint.route("/api/log_clear", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_log_clear():
    log = flask.request.args.get("log", True, type=json.loads)

    clear()
    if log:
        info("🧹 ログがクリアされました。")

    return flask.jsonify({"result": "success"})


@blueprint.route("/api/log_view", methods=["GET"])
@my_lib.flask_util.support_jsonp
@my_lib.flask_util.gzipped
def api_log_view():
    stop_day = flask.request.args.get("stop_day", 0, type=int)

    # NOTE: @gzipped をつけた場合、キャッシュ用のヘッダを付与しているので、
    # 無効化する。
    flask.g.disable_cache = True

    log_list = get(stop_day)

    if len(log_list) == 0:
        last_time = time.time()
    else:
        last_time = (
            datetime.datetime.strptime(log_list[0]["date"], "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=datetime.timezone.utc)
            .astimezone(my_lib.time.get_zoneinfo())
            .timestamp()
        )

    response = flask.jsonify({"data": log_list, "last_time": last_time})

    response.headers["Last-Modified"] = wsgiref.handlers.format_date_time(last_time)
    response.make_conditional(flask.request)

    return response


def test_run(config, port, debug_mode):
    import flask_cors

    app = flask.Flask("test")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    my_lib.webapp.log.init(config)

    flask_cors.CORS(app)

    app.config["TEST"] = True
    app.json.compat = True

    app.register_blueprint(my_lib.webapp.log.blueprint)
    app.register_blueprint(my_lib.webapp.event.blueprint)

    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False, debug=debug_mode)  # noqa: S104


if __name__ == "__main__":
    # TEST Code
    import signal

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import requests

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = int(args["-p"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/test"
    my_lib.webapp.config.init(config)

    import my_lib.webapp.base
    import my_lib.webapp.event
    import my_lib.webapp.log

    def sig_handler(num, frame):  # noqa: ARG001
        my_lib.webapp.log.term()

    signal.signal(signal.SIGTERM, sig_handler)

    base_url = f"http://127.0.0.1:{port}/test"

    proc = multiprocessing.Process(target=lambda: test_run(config, port, debug_mode))
    proc.start()

    time.sleep(0.5)

    logging.info(my_lib.pretty.format(requests.get(f"{base_url}/api/log_clear").text))  # noqa: S113

    requests.post(f"{base_url}/api/log_add", data={"message": "Test INFO", "level": "INFO"})  # noqa: S113
    requests.post(f"{base_url}/api/log_add", data={"message": "Test WARN", "level": "WARN"})  # noqa: S113
    requests.post(f"{base_url}/api/log_add", data={"message": "Test ERROR", "level": "ERROR"})  # noqa: S113

    time.sleep(0.5)

    logging.info(my_lib.pretty.format(json.loads(requests.get(f"{base_url}/api/log_view").text)))  # noqa: S113

    os.kill(proc.pid, signal.SIGUSR1)
    proc.terminate()
    proc.join()
