#!/usr/bin/env python3
"""
Web アプリでログを表示します。

Usage:
  log.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: tests/fixtures/config.example.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import enum
import json
import logging
import multiprocessing
import multiprocessing.managers
import os
import pathlib
import sqlite3
import threading
import time
import traceback
import wsgiref.handlers
from typing import Any, Callable, TypeVar

import flask

import my_lib.flask_util
import my_lib.notify.slack
import my_lib.sqlite_util
import my_lib.time
import my_lib.webapp.config
import my_lib.webapp.event

T = TypeVar("T")


class LOG_LEVEL(enum.Enum):  # noqa: N801
    INFO = 0
    WARN = 1
    ERROR = 2


TABLE_NAME = "log"
CHECK_INTERVAL_SEC = 10
MAX_RETRY_COUNT = 5
INITIAL_RETRY_DELAY_SEC = 0.1
MAX_RETRY_DELAY_SEC = 5.0

blueprint = flask.Blueprint("webapp-log", __name__)


class LogManager:
    """ログ管理クラス

    SQLite データベースへのログ記録と、ワーカースレッドによる非同期処理を管理します。
    pytest-xdist による並列テスト実行に対応するため、ワーカー ID ごとに状態を分離します。
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] | None = None
        self._log_thread: dict[str | None, threading.Thread] = {}
        self._queue_lock: dict[str | None, threading.RLock] = {}
        self._log_queue: dict[str | None, Any] = {}
        self._log_manager: dict[str | None, multiprocessing.managers.SyncManager] = {}
        self._log_event: dict[str | None, threading.Event] = {}
        self._should_terminate: dict[str | None, threading.Event] = {}

    @property
    def config(self) -> dict[str, Any] | None:
        """設定 dict"""
        return self._config

    @config.setter
    def config(self, value: dict[str, Any] | None) -> None:
        self._config = value

    @staticmethod
    def get_worker_id() -> str | None:
        """pytest-xdist のワーカー ID を取得する"""
        return os.environ.get("PYTEST_XDIST_WORKER", None)

    def get_log_thread(self) -> threading.Thread | None:
        """現在のワーカーのログスレッドを取得する"""
        return self._log_thread.get(self.get_worker_id(), None)

    def get_queue_lock(self) -> threading.RLock | None:
        """現在のワーカーのキューロックを取得する"""
        return self._queue_lock.get(self.get_worker_id(), None)

    def get_log_manager(self) -> multiprocessing.managers.SyncManager | None:
        """現在のワーカーのマネージャーを取得する"""
        return self._log_manager.get(self.get_worker_id(), None)

    def get_log_queue(self) -> Any:
        """現在のワーカーのログキューを取得する"""
        return self._log_queue.get(self.get_worker_id(), None)

    def get_log_event(self) -> threading.Event | None:
        """現在のワーカーのログイベントを取得する"""
        return self._log_event.get(self.get_worker_id(), None)

    def get_should_terminate(self) -> threading.Event | None:
        """現在のワーカーの終了フラグを取得する"""
        return self._should_terminate.get(self.get_worker_id(), None)

    def get_db_path(self) -> pathlib.Path:
        """データベースパスを取得する（ワーカー ID に応じたパスを返す）"""
        worker_id = self.get_worker_id()
        base_path = my_lib.webapp.config.LOG_DIR_PATH

        if base_path is None:
            raise RuntimeError("LOG_DIR_PATH is not initialized. Call init() first.")

        if worker_id is None:
            return base_path
        else:
            # ワーカー毎に別ディレクトリを作成
            worker_dir = base_path.parent / f"test_worker_{worker_id}"
            worker_dir.mkdir(parents=True, exist_ok=True)
            return worker_dir / base_path.name

    def init(self, config: dict[str, Any], is_read_only: bool = False) -> None:
        """ログシステムを初期化する

        Args:
            config: 設定 dict
            is_read_only: 読み取り専用モード
        """
        self._config = config

        db_path = self.get_db_path()
        # 初回のみsqlite_util.connectを使用してデータベースを初期化
        with my_lib.sqlite_util.connect(db_path) as sqlite:
            sqlite.execute(
                f"CREATE TABLE IF NOT EXISTS {TABLE_NAME}"
                "(id INTEGER primary key autoincrement, date INTEGER, message TEXT)"
            )
            sqlite.commit()

        if not is_read_only:
            self._init_impl()

    def _init_impl(self) -> None:
        """ワーカースレッドを初期化する"""
        # NOTE: atexit とかでログを出したい場合もあるので、Queue はここで閉じる。
        log_manager = self.get_log_manager()
        if log_manager is not None:
            log_manager.shutdown()

        worker_id = self.get_worker_id()

        should_terminate = self.get_should_terminate()
        if should_terminate is not None:
            should_terminate.clear()
        else:
            self._queue_lock[worker_id] = threading.RLock()
            self._should_terminate[worker_id] = threading.Event()
            self._log_event[worker_id] = threading.Event()

        manager = multiprocessing.Manager()

        self._log_manager[worker_id] = manager
        self._log_queue[worker_id] = manager.Queue()

        self._log_thread[worker_id] = threading.Thread(target=self._worker, args=(self.get_log_queue(),))
        self._log_thread[worker_id].start()

    def term(self, is_read_only: bool = False) -> None:
        """ログシステムを終了する

        Args:
            is_read_only: 読み取り専用モード
        """
        if is_read_only:
            return

        log_thread = self.get_log_thread()
        if log_thread is None:
            return

        should_terminate = self.get_should_terminate()
        log_event = self.get_log_event()
        if should_terminate is not None:
            should_terminate.set()
        if log_event is not None:
            log_event.set()

        time.sleep(1)

        log_thread.join()
        del self._log_thread[self.get_worker_id()]

    def _execute_with_retry(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        """リトライ機能付きで関数を実行する"""
        retry_count = 0
        delay = INITIAL_RETRY_DELAY_SEC
        last_exception = None

        while retry_count < MAX_RETRY_COUNT:
            try:
                return func(*args, **kwargs)
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:  # noqa: PERF203
                last_exception = e
                error_msg = str(e).lower()

                if "database is locked" in error_msg or "unable to open database file" in error_msg:
                    retry_count += 1

                    if retry_count >= MAX_RETRY_COUNT:
                        logging.exception("最大リトライ回数 %d に達しました", MAX_RETRY_COUNT)
                        # データベースの復旧を試みる
                        db_path = self.get_db_path()
                        my_lib.sqlite_util.recover(db_path)
                        raise

                    logging.warning("データベースエラー (リトライ %d/%d): %s", retry_count, MAX_RETRY_COUNT, e)
                    time.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY_SEC)  # 指数バックオフ
                else:
                    raise

        if last_exception:
            raise last_exception
        return None

    def _log_impl(self, sqlite: sqlite3.Connection, message: str, level: LOG_LEVEL) -> None:
        """ログをデータベースに記録する"""
        logging.debug("insert: [%s] %s", LOG_LEVEL(level).name, message)

        def _execute_log() -> None:
            sqlite.execute(
                f'INSERT INTO {TABLE_NAME} VALUES (NULL, DATETIME("now"), ?)',  # noqa: S608
                [message],
            )
            sqlite.execute(f'DELETE FROM {TABLE_NAME} WHERE date <= DATETIME("now", "-60 days")')  # noqa: S608
            sqlite.commit()

        # リトライ機能付きでログを記録
        self._execute_with_retry(_execute_log)

        my_lib.webapp.event.notify_event(my_lib.webapp.event.EVENT_TYPE.LOG)

        if level == LOG_LEVEL.ERROR:
            if self._config is not None and "slack" in self._config:
                slack_config = my_lib.notify.slack.parse_config(self._config["slack"])
                if isinstance(
                    slack_config,
                    (
                        my_lib.notify.slack.SlackConfig,
                        my_lib.notify.slack.SlackErrorInfoConfig,
                        my_lib.notify.slack.SlackErrorOnlyConfig,
                    ),
                ):
                    my_lib.notify.slack.error(slack_config, self._config["slack"]["from"], message)

            if (os.environ.get("DUMMY_MODE", "false") == "true") and (
                os.environ.get("TEST", "false") != "true"
            ):  # pragma: no cover
                logging.error("This application is terminated because it is in dummy mode.")
                os._exit(-1)

    def _worker(self, log_queue: Any) -> None:
        """ログキューを監視するワーカー"""
        with my_lib.sqlite_util.connect(self.get_db_path()) as sqlite:
            while True:
                should_terminate = self.get_should_terminate()
                if should_terminate is not None and should_terminate.is_set():
                    break

                # NOTE: とりあえず、イベントを待つ
                log_event = self.get_log_event()
                if log_event is None or not log_event.wait(CHECK_INTERVAL_SEC):
                    continue

                try:
                    queue_lock = self.get_queue_lock()
                    if queue_lock is None:
                        continue
                    with queue_lock:  # NOTE: クリア処理と排他したい
                        log_event.clear()

                        while not log_queue.empty():
                            logging.debug("Found %d log message(s)", log_queue.qsize())
                            log = log_queue.get()
                            self._log_impl(sqlite, log["message"], log["level"])
                except OverflowError:  # pragma: no cover
                    # NOTE: テストする際、time_machine を使って日付をいじるとこの例外が発生する。
                    logging.debug(traceback.format_exc())
                except (ValueError, BrokenPipeError, EOFError, OSError):  # pragma: no cover
                    # NOTE: 終了時、queue が close された後に empty() や get() を呼ぶとこれらの例外が
                    # 発生する。マネージャーがシャットダウンされた場合は BrokenPipeError が発生する。
                    logging.debug("Queue connection closed, terminating worker")
                    break
            logging.info("Terminate worker")

    def add(self, message: str, level: LOG_LEVEL) -> None:
        """ログを追加する

        Args:
            message: ログメッセージ
            level: ログレベル
        """
        queue_lock = self.get_queue_lock()
        log_queue = self.get_log_queue()
        log_event = self.get_log_event()

        if queue_lock is None or log_queue is None or log_event is None:
            logging.warning("Log system not initialized, skipping log: %s", message)
            return

        with queue_lock:  # NOTE: クリア処理と排他したい
            # NOTE: 実際のログ記録は別スレッドに任せて、すぐにリターンする
            log_queue.put({"message": message, "level": level})
            log_event.set()

    def error(self, message: str) -> None:
        """エラーログを記録する"""
        logging.error(message)
        self.add(message, LOG_LEVEL.ERROR)

    def warning(self, message: str) -> None:
        """警告ログを記録する"""
        logging.warning(message)
        self.add(message, LOG_LEVEL.WARN)

    def info(self, message: str) -> None:
        """情報ログを記録する"""
        logging.info(message)
        self.add(message, LOG_LEVEL.INFO)

    def get(self, stop_day: int = 0) -> list[dict[str, Any]]:
        """ログを取得する

        Args:
            stop_day: 取得を停止する日数前

        Returns:
            ログのリスト
        """
        with my_lib.sqlite_util.connect(self.get_db_path()) as sqlite:
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
            return log_list

    def clear(self) -> None:
        """ログをクリアする"""
        with my_lib.sqlite_util.connect(self.get_db_path()) as sqlite:
            cur = sqlite.cursor()

            logging.debug("clear SQLite")
            cur.execute(f"DELETE FROM {TABLE_NAME}")  # noqa: S608
            sqlite.commit()

        logging.debug("clear Queue")
        log_queue = self.get_log_queue()
        if log_queue is not None:
            while not log_queue.empty():  # NOTE: 信用できないけど、許容する
                log_queue.get_nowait()


# モジュールレベルのインスタンス
_manager = LogManager()


def _get_worker_id() -> str | None:
    """pytest-xdist のワーカー ID を取得する（テスト用）"""
    return _manager.get_worker_id()


def init(config_: dict[str, Any], is_read_only: bool = False) -> None:
    """ログシステムを初期化する

    Args:
        config_: 設定 dict
        is_read_only: 読み取り専用モード
    """
    _manager.init(config_, is_read_only)


def _init_impl() -> None:
    """ワーカースレッドを初期化する（テスト用）"""
    _manager._init_impl()


def term(is_read_only: bool = False) -> None:
    """ログシステムを終了する

    Args:
        is_read_only: 読み取り専用モード
    """
    _manager.term(is_read_only)


def _get_log_thread() -> threading.Thread | None:
    """現在のワーカーのログスレッドを取得する（テスト用）"""
    return _manager.get_log_thread()


def _get_queue_lock() -> threading.RLock | None:
    """現在のワーカーのキューロックを取得する（テスト用）"""
    return _manager.get_queue_lock()


def _get_log_manager() -> multiprocessing.managers.SyncManager | None:
    """現在のワーカーのマネージャーを取得する（テスト用）"""
    return _manager.get_log_manager()


def _get_log_queue() -> Any:
    """現在のワーカーのログキューを取得する（テスト用）"""
    return _manager.get_log_queue()


def _get_log_event() -> threading.Event | None:
    """現在のワーカーのログイベントを取得する（テスト用）"""
    return _manager.get_log_event()


def _get_should_terminate() -> threading.Event | None:
    """現在のワーカーの終了フラグを取得する（テスト用）"""
    return _manager.get_should_terminate()


def _get_db_path() -> pathlib.Path:
    """データベースパスを取得する（テスト用）"""
    return _manager.get_db_path()


def _execute_with_retry(func: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
    """リトライ機能付きで関数を実行する（テスト用）"""
    return _manager._execute_with_retry(func, *args, **kwargs)


def _log_impl(sqlite: sqlite3.Connection, message: str, level: LOG_LEVEL) -> None:
    """ログをデータベースに記録する（テスト用）"""
    _manager._log_impl(sqlite, message, level)


def _worker(log_queue: Any) -> None:
    """ログキューを監視するワーカー（テスト用）"""
    _manager._worker(log_queue)


def add(message: str, level: LOG_LEVEL) -> None:
    """ログを追加する

    Args:
        message: ログメッセージ
        level: ログレベル
    """
    _manager.add(message, level)


def error(message: str) -> None:
    """エラーログを記録する"""
    _manager.error(message)


def warning(message: str) -> None:
    """警告ログを記録する"""
    _manager.warning(message)


def info(message: str) -> None:
    """情報ログを記録する"""
    _manager.info(message)


def get(stop_day: int = 0) -> list[dict[str, Any]]:
    """ログを取得する"""
    return _manager.get(stop_day)


def clear() -> None:
    """ログをクリアする"""
    _manager.clear()


@blueprint.route("/api/log_add", methods=["POST"])
@my_lib.flask_util.support_jsonp
def api_log_add() -> flask.Response:
    """ログ追加 API エンドポイント"""
    if not flask.current_app.config["TEST"]:
        flask.abort(403)

    message = flask.request.form.get("message", "")
    level = flask.request.form.get("level", LOG_LEVEL.INFO, type=lambda x: LOG_LEVEL[x])

    add(message, level)

    return flask.jsonify({"result": "success"})


@blueprint.route("/api/log_clear", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_log_clear() -> flask.Response:
    """ログクリア API エンドポイント"""
    log = flask.request.args.get("log", True, type=json.loads)

    queue_lock = _manager.get_queue_lock()
    if queue_lock is None:
        return flask.jsonify({"result": "error", "message": "Log system not initialized"})

    with queue_lock:
        # NOTE: ログの先頭にクリアメッセージが来るようにする
        clear()
        if log:
            info("🧹 ログがクリアされました。")

    return flask.jsonify({"result": "success"})


@blueprint.route("/api/log_view", methods=["GET"])
@my_lib.flask_util.support_jsonp
@my_lib.flask_util.gzipped
def api_log_view() -> flask.Response:
    """ログ表示 API エンドポイント"""
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


def test_run(config: dict[str, Any], port: int, debug_mode: bool) -> None:
    """テスト用サーバを実行する"""
    import flask_cors

    app = flask.Flask("test")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    my_lib.webapp.log.init(config)

    flask_cors.CORS(app)

    app.config["TEST"] = True
    if hasattr(app.json, "compat"):
        app.json.compat = True  # type: ignore[attr-defined]

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

    assert __doc__ is not None
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = int(args["-p"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/test"
    my_lib.webapp.config.init(my_lib.webapp.config.WebappConfig.from_dict(config["webapp"]))

    import my_lib.webapp.base
    import my_lib.webapp.event
    import my_lib.webapp.log

    def sig_handler(num, frame):  # noqa: ARG001
        my_lib.webapp.log.term()

    signal.signal(signal.SIGTERM, sig_handler)

    base_url = f"http://127.0.0.1:{port}/test"

    assert config is not None, "Config must be loaded before running test"
    config_: dict[str, Any] = config  # Capture narrowed type for lambda
    proc = multiprocessing.Process(target=lambda: test_run(config_, port, debug_mode))
    proc.start()

    time.sleep(0.5)

    logging.info(my_lib.pretty.format(requests.get(f"{base_url}/api/log_clear").text))  # noqa: S113

    requests.post(f"{base_url}/api/log_add", data={"message": "Test INFO", "level": "INFO"})  # noqa: S113
    requests.post(f"{base_url}/api/log_add", data={"message": "Test WARN", "level": "WARN"})  # noqa: S113
    requests.post(f"{base_url}/api/log_add", data={"message": "Test ERROR", "level": "ERROR"})  # noqa: S113

    time.sleep(0.5)

    logging.info(my_lib.pretty.format(json.loads(requests.get(f"{base_url}/api/log_view").text)))  # noqa: S113

    if proc.pid is not None:
        os.kill(proc.pid, signal.SIGUSR1)
    proc.terminate()
    proc.join()
