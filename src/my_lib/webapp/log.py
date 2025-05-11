#!/usr/bin/env python3
import datetime
import json
import logging
import os
import sqlite3
import threading
import time
import traceback
from enum import IntEnum
from multiprocessing import Queue
from wsgiref.handlers import format_date_time

import flask
import my_lib.flask_util
import my_lib.notify.slack
import my_lib.webapp.config
import my_lib.webapp.event


class LOG_LEVEL(IntEnum):  # noqa: N801
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
        log_queue = Queue()
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
            # NOTE: テストする際，freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
        except ValueError:  # pragma: no cover
            # NOTE: 終了時，queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する。
            logging.warning(traceback.format_exc())

        time.sleep(sleep_sec)


def error(message):
    logging.error(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    log_queue.put({"message": message, "level": LOG_LEVEL.ERROR})


def warning(message):
    logging.warning(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    log_queue.put({"message": message, "level": LOG_LEVEL.WARN})


def info(message):
    logging.info(message)

    # NOTE: 実際のログ記録は別スレッドに任せて，すぐにリターンする
    log_queue.put({"message": message, "level": LOG_LEVEL.INFO})


def get(stop_day):
    global sqlite

    cur = sqlite.cursor()
    cur.execute(
        'SELECT * FROM log WHERE date <= DATETIME("now", ?) ORDER BY id DESC LIMIT 500',
        # NOTE: デモ用に stop_day 日前までののログしか出さない指定ができるようにする
        [f"-{stop_day} days"],
    )
    return cur.fetchall()


def clear():
    global sqlite

    with log_lock:
        cur = sqlite.cursor()
        cur.execute("DELETE FROM log")


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

    # NOTE: @gzipped をつけた場合，キャッシュ用のヘッダを付与しているので，
    # 無効化する。
    flask.g.disable_cache = True

    log = get(stop_day)

    if len(log) == 0:
        last_time = time.time()
    else:
        last_time = (
            datetime.datetime.strptime(log[0]["date"], "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=my_lib.webapp.config.TIMEZONE)
            .timestamp()
        )

    response = flask.jsonify({"data": log, "last_time": last_time})

    response.headers["Last-Modified"] = format_date_time(last_time)
    response.make_conditional(flask.request)

    return response
