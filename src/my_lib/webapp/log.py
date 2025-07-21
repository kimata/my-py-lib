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

import flask
import my_lib.flask_util
import my_lib.notify.slack
import my_lib.webapp.config
import my_lib.webapp.event


class LOG_LEVEL(enum.Enum):  # noqa: N801
    INFO = 0
    WARN = 1
    ERROR = 2


TABLE_NAME = "log"
CHECK_INTERVAL_SEC = 10

blueprint = flask.Blueprint("webapp-log", __name__)

config = None

_log_thread = {}
_queue_lock = {}
_log_queue = {}
_log_manager = {}
_log_event = {}
_should_terminate = {}


def init(config_, is_read_only=False):
    global config  # noqa: PLW0603

    config = config_

    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite = sqlite3.connect(db_path)
    sqlite.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME}"
        "(id INTEGER primary key autoincrement, date INTEGER, message TEXT)"
    )
    sqlite.execute("PRAGMA journal_mode=WAL")
    sqlite.commit()
    sqlite.close()

    if not is_read_only:
        init_impl()


def term(is_read_only=False):
    if is_read_only:
        return

    get_should_terminate().set()
    get_log_event().set()

    if get_log_thread() is not None:
        time.sleep(1)
        get_log_thread().join()
        del _log_thread[get_worker_id()]


def get_worker_id():
    return os.environ.get("PYTEST_XDIST_WORKER", "")


def init_impl():
    # NOTE: atexit とかでログを出したい場合もあるので、Queue はここで閉じる。
    if get_log_manager() is not None:
        get_log_manager().shutdown()

    if get_should_terminate() is not None:
        get_should_terminate().clear()

    worker_id = get_worker_id()
    manager = multiprocessing.Manager()

    _queue_lock[worker_id] = threading.RLock()
    _log_manager[worker_id] = manager
    _log_queue[worker_id] = manager.Queue()
    _log_event[worker_id] = threading.Event()
    _log_thread[worker_id] = threading.Thread(target=worker, args=(get_log_queue(),))
    _should_terminate[worker_id] = threading.Event()

    _log_thread[worker_id].start()


def get_log_thread():
    return _log_thread.get(get_worker_id(), None)


def get_queue_lock():
    return _queue_lock.get(get_worker_id(), None)


def get_log_manager():
    return _log_manager.get(get_worker_id(), None)


def get_log_queue():
    return _log_queue.get(get_worker_id(), None)


def get_log_event():
    return _log_event.get(get_worker_id(), None)


def get_should_terminate():
    return _should_terminate.get(get_worker_id(), None)


def get_db_path():
    # NOTE: Pytest を並列実行できるようにする
    worker_id = get_worker_id()
    base_path = my_lib.webapp.config.LOG_DIR_PATH

    if worker_id is None:
        return base_path
    else:
        # ワーカー毎に別ディレクトリを作成
        worker_dir = base_path.parent / f"test_worker_{worker_id}"
        worker_dir.mkdir(parents=True, exist_ok=True)
        return worker_dir / base_path.name


def log_impl(sqlite, message, level):
    global config

    logging.debug("insert: [%s] %s", LOG_LEVEL(level).name, message)

    sqlite.execute(
        f'INSERT INTO {TABLE_NAME} VALUES (NULL, DATETIME("now"), ?)',  # noqa: S608
        [message],
    )
    sqlite.execute(f'DELETE FROM {TABLE_NAME} WHERE date <= DATETIME("now", "-60 days")')  # noqa: S608
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


def worker(log_queue):  # noqa: ARG001
    sqlite = sqlite3.connect(get_db_path())
    while True:
        if get_should_terminate().is_set():
            break

        # NOTE: とりあえず、イベントを待つ
        if not get_log_event().wait(CHECK_INTERVAL_SEC):
            continue

        try:
            with get_queue_lock():  # NOTE: クリア処理と排他したい
                get_log_event().clear()

                while not get_log_queue().empty():
                    logging.debug("Found %d log message(s)", get_log_queue().qsize())
                    log = get_log_queue().get()
                    log_impl(sqlite, log["message"], log["level"])
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際、time_machine を使って日付をいじるとこの例外が発生する。
            logging.debug(traceback.format_exc())
        except ValueError:  # pragma: no cover
            # NOTE: 終了時、queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する。
            logging.warning(traceback.format_exc())

    sqlite.close()

    logging.info("Terminate worker")


def add(message, level):
    with get_queue_lock():  # NOTE: クリア処理と排他したい
        # NOTE: 実際のログ記録は別スレッドに任せて、すぐにリターンする
        get_log_queue().put({"message": message, "level": level})
        get_log_event().set()


def error(message):
    logging.error(message)

    add(message, LOG_LEVEL.ERROR)


def warning(message):
    logging.warning(message)

    add(message, LOG_LEVEL.WARN)


def info(message):
    logging.info(message)

    add(message, LOG_LEVEL.INFO)


def get(stop_day=0):
    sqlite = sqlite3.connect(get_db_path())

    sqlite.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r, strict=True))
    cur = sqlite.cursor()
    cur.execute(
        f'SELECT * FROM {TABLE_NAME} WHERE date <= DATETIME("now", ?) ORDER BY id DESC LIMIT 500',  # noqa: S608
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
    sqlite.close()

    return log_list


def clear():
    sqlite = sqlite3.connect(get_db_path())
    cur = sqlite.cursor()

    logging.debug("clear SQLite")
    cur.execute(f"DELETE FROM {TABLE_NAME}")  # noqa: S608
    sqlite.commit()
    sqlite.close()

    logging.debug("clear Queue")
    while not get_log_queue().empty():  # NOTE: 信用できないけど、許容する
        get_log_queue().get_nowait()


@blueprint.route("/api/log_add", methods=["POST"])
@my_lib.flask_util.support_jsonp
def api_log_add():
    if not flask.current_app.config["TEST"]:
        flask.abort(403)

    message = flask.request.form.get("message", "")
    level = flask.request.form.get("level", LOG_LEVEL.INFO, type=lambda x: LOG_LEVEL[x])

    add(message, level)

    return flask.jsonify({"result": "success"})


@blueprint.route("/api/log_clear", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_log_clear():
    log = flask.request.args.get("log", True, type=json.loads)

    with get_queue_lock():
        # NOTE: ログの先頭にクリアメッセージが来るようにする
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
            .replace(tzinfo=my_lib.time.get_zoneinfo())
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
    import requests

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

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
