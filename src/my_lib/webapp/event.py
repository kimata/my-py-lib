#!/usr/bin/env python3
from __future__ import annotations

import enum
import logging
import multiprocessing
import multiprocessing.queues
import threading
import time
import traceback
from typing import Any

import flask

YIELD_TIMEOUT = 100


class EVENT_TYPE(enum.Enum):  # noqa: N801
    CONTROL = "control"
    SCHEDULE = "schedule"
    LOG = "log"


blueprint = flask.Blueprint("webapp-event", __name__)


# NOTE: サイズは上の Enum の個数+1 にしておく
event_count = multiprocessing.Array("i", 4)  # type: ignore[type-arg]

should_terminate: bool = False
watch_thread: threading.Thread | None = None


def start(event_queue: multiprocessing.queues.Queue[Any]) -> None:
    global should_terminate  # noqa: PLW0603
    global watch_thread  # noqa: PLW0603

    should_terminate = False

    watch_thread = threading.Thread(target=worker, args=(event_queue,))
    watch_thread.start()


def worker(event_queue: multiprocessing.queues.Queue[Any]) -> None:
    global should_terminate

    logging.info("Start notify watch thread")

    while True:
        if should_terminate:
            break
        try:
            if not event_queue.empty():
                notify_event(event_queue.get())
            time.sleep(0.1)
        except OverflowError:  # pragma: no cover
            # NOTE: テストする際、freezer 使って日付をいじるとこの例外が発生する
            logging.debug(traceback.format_exc())
        except ValueError:  # pragma: no cover
            # NOTE: 終了時、queue が close された後に empty() や get() を呼ぶとこの例外が
            # 発生する。
            logging.warning(traceback.format_exc())

    logging.info("Stop notify watch thread")


def term() -> None:
    global should_terminate  # noqa: PLW0603
    global watch_thread  # noqa: PLW0603

    if watch_thread is not None:
        should_terminate = True

        # NOTE: pytest で timemachine 使うと下記で固まるので join を見送る
        # watch_thread.join()

        watch_thread = None


def event_index(event_type: EVENT_TYPE) -> int:
    if event_type == EVENT_TYPE.CONTROL:
        return 0
    elif event_type == EVENT_TYPE.SCHEDULE:
        return 1
    elif event_type == EVENT_TYPE.LOG:
        return 2
    else:  # pragma: no cover
        return 3


def notify_event(event_type: EVENT_TYPE) -> None:
    global event_count
    event_count[event_index(event_type)] += 1  # type: ignore[index]


@blueprint.route("/api/event", methods=["GET"])
def api_event() -> flask.Response:
    count = flask.request.args.get("count", 0, type=int)

    def event_stream() -> Any:
        global event_count

        last_count = event_count[:]  # type: ignore[index]

        i = 0
        j = 0
        while True:
            time.sleep(0.5)
            for event_type in EVENT_TYPE.__members__.values():
                index = event_index(event_type)

                if last_count[index] != event_count[index]:  # type: ignore[index]
                    logging.debug("notify event: %s", event_type.value)
                    yield f"data: {event_type.value}\n\n"
                    last_count[index] = event_count[index]  # type: ignore[index]

                    i += 1
                    if i == count:
                        return

            # NOTE: クライアントが切断された時にソケットを解放するため、定期的に yield を呼ぶ
            j += 1
            if j == YIELD_TIMEOUT:
                yield "data: dummy\n\n"
                j = 0

    res = flask.Response(flask.stream_with_context(event_stream()), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res
