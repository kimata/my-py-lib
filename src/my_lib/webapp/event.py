#!/usr/bin/env python3
from __future__ import annotations

import enum
import logging
import multiprocessing
import multiprocessing.queues
import threading
import time
import traceback
from collections.abc import Generator
from typing import Any

import flask

YIELD_TIMEOUT = 100


class EVENT_TYPE(enum.Enum):
    CONTROL = "control"
    SCHEDULE = "schedule"
    LOG = "log"

    @property
    def index(self) -> int:
        """イベントタイプのインデックスを返す"""
        return list(EVENT_TYPE).index(self)


blueprint = flask.Blueprint("webapp-event", __name__)


class EventManager:
    """イベント管理クラス

    SSE (Server-Sent Events) を使用したイベント通知を管理します。
    """

    def __init__(self) -> None:
        # NOTE: サイズは EVENT_TYPE の個数 + 1 にしておく
        self._event_count = multiprocessing.Array("i", len(EVENT_TYPE) + 1)
        self._should_terminate: bool = False
        self._watch_thread: threading.Thread | None = None

    @property
    def event_count(self) -> Any:
        """イベントカウント配列"""
        return self._event_count

    @property
    def should_terminate(self) -> bool:
        """終了フラグ"""
        return self._should_terminate

    @should_terminate.setter
    def should_terminate(self, value: bool) -> None:
        self._should_terminate = value

    @property
    def watch_thread(self) -> threading.Thread | None:
        """監視スレッド"""
        return self._watch_thread

    @watch_thread.setter
    def watch_thread(self, value: threading.Thread | None) -> None:
        self._watch_thread = value

    def start(self, event_queue: multiprocessing.queues.Queue[EVENT_TYPE]) -> None:
        """ワーカースレッドを開始する

        Args:
            event_queue: イベントを受信するキュー
        """
        self._should_terminate = False
        self._watch_thread = threading.Thread(target=self._worker, args=(event_queue,))
        self._watch_thread.start()

    def _worker(self, event_queue: multiprocessing.queues.Queue[EVENT_TYPE]) -> None:
        """イベントキューを監視するワーカー

        Args:
            event_queue: イベントを受信するキュー
        """
        logging.info("Start notify watch thread")

        while True:
            if self._should_terminate:
                break
            try:
                if not event_queue.empty():
                    self.notify_event(event_queue.get())
                time.sleep(0.1)
            except OverflowError:  # pragma: no cover
                # NOTE: テストする際、freezer 使って日付をいじるとこの例外が発生する
                logging.debug(traceback.format_exc())
            except ValueError:  # pragma: no cover
                # NOTE: 終了時、queue が close された後に empty() や get() を呼ぶとこの例外が
                # 発生する。
                logging.warning(traceback.format_exc())

        logging.info("Stop notify watch thread")

    def term(self) -> None:
        """ワーカースレッドを終了する"""
        if self._watch_thread is not None:
            self._should_terminate = True

            # NOTE: pytest で timemachine 使うと下記で固まるので join を見送る
            # self._watch_thread.join()

            self._watch_thread = None

    def notify_event(self, event_type: EVENT_TYPE) -> None:
        """イベントを通知する

        Args:
            event_type: 通知するイベントタイプ
        """
        self._event_count[event_type.index] += 1

    def get_event_stream(self, count: int) -> Generator[str, None, None]:
        """SSE 用のイベントストリームを生成する

        Args:
            count: 取得するイベント数（0 の場合は無限）

        Yields:
            SSE 形式のイベントデータ
        """
        last_count = self._event_count[:]

        i = 0
        j = 0
        while True:
            time.sleep(0.5)
            for event_type in EVENT_TYPE:
                index = event_type.index

                if last_count[index] != self._event_count[index]:
                    logging.debug("notify event: %s", event_type.value)
                    yield f"data: {event_type.value}\n\n"
                    last_count[index] = self._event_count[index]

                    i += 1
                    if i == count:
                        return

            # NOTE: クライアントが切断された時にソケットを解放するため、定期的に yield を呼ぶ
            j += 1
            if j == YIELD_TIMEOUT:
                yield "data: dummy\n\n"
                j = 0


# モジュールレベルのインスタンス
_manager = EventManager()


def start(event_queue: multiprocessing.queues.Queue[Any]) -> None:
    """ワーカースレッドを開始する

    Args:
        event_queue: イベントを受信するキュー
    """
    _manager.start(event_queue)


def term() -> None:
    """ワーカースレッドを終了する"""
    _manager.term()


def notify_event(event_type: EVENT_TYPE) -> None:
    """イベントを通知する

    Args:
        event_type: 通知するイベントタイプ
    """
    _manager.notify_event(event_type)


@blueprint.route("/api/event", methods=["GET"])
def api_event() -> flask.Response:
    """SSE エンドポイント

    Returns:
        SSE 形式のレスポンス
    """
    count = flask.request.args.get("count", 0, type=int)

    res = flask.Response(
        flask.stream_with_context(_manager.get_event_stream(count)),
        mimetype="text/event-stream",
    )
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res
