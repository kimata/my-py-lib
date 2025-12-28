#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.event モジュールのユニットテスト
"""
from __future__ import annotations

import pytest


class TestEventType:
    """EVENT_TYPE 列挙型のテスト"""

    def test_has_control(self):
        """CONTROL を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.CONTROL.value == "control"

    def test_has_schedule(self):
        """SCHEDULE を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.SCHEDULE.value == "schedule"

    def test_has_log(self):
        """LOG を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.LOG.value == "log"


class TestEventIndex:
    """event_index 関数のテスト"""

    def test_control_index(self):
        """CONTROL のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.CONTROL) == 0

    def test_schedule_index(self):
        """SCHEDULE のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.SCHEDULE) == 1

    def test_log_index(self):
        """LOG のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.LOG) == 2


class TestNotifyEvent:
    """notify_event 関数のテスト"""

    def test_increments_event_count(self):
        """イベントカウントを増加させる"""
        from my_lib.webapp.event import EVENT_TYPE, event_count, event_index, notify_event

        initial = event_count[event_index(EVENT_TYPE.LOG)]
        notify_event(EVENT_TYPE.LOG)

        assert event_count[event_index(EVENT_TYPE.LOG)] == initial + 1


class TestTerm:
    """term 関数のテスト"""

    def test_does_not_raise_without_thread(self):
        """スレッドがなくてもエラーにならない"""
        from my_lib.webapp.event import term

        # 例外が発生しなければ OK
        term()

    def test_sets_should_terminate(self):
        """should_terminate フラグを設定する"""
        import threading
        import unittest.mock

        import my_lib.webapp.event as event_module

        mock_thread = unittest.mock.MagicMock(spec=threading.Thread)
        event_module.watch_thread = mock_thread
        event_module.should_terminate = False

        event_module.term()

        assert event_module.should_terminate is True
        assert event_module.watch_thread is None


class TestStart:
    """start 関数のテスト"""

    def test_starts_watch_thread(self):
        """ウォッチスレッドを開始する"""
        import multiprocessing
        import time
        import unittest.mock

        import my_lib.webapp.event as event_module

        queue = multiprocessing.Queue()

        event_module.start(queue)

        assert event_module.watch_thread is not None
        assert event_module.should_terminate is False

        event_module.term()
        time.sleep(0.2)


class TestWorker:
    """worker 関数のテスト"""

    def test_processes_events(self):
        """イベントを処理する"""
        import multiprocessing
        import threading
        import time

        import my_lib.webapp.event as event_module
        from my_lib.webapp.event import EVENT_TYPE

        queue = multiprocessing.Queue()
        queue.put(EVENT_TYPE.LOG)

        event_module.should_terminate = False

        def run_worker():
            time.sleep(0.2)
            event_module.should_terminate = True

        threading.Thread(target=run_worker).start()
        event_module.worker(queue)

    def test_stops_on_terminate(self):
        """終了フラグで停止する"""
        import multiprocessing

        import my_lib.webapp.event as event_module

        queue = multiprocessing.Queue()
        event_module.should_terminate = True

        event_module.worker(queue)


class TestApiEvent:
    """api_event 関数のテスト"""

    def test_returns_response(self):
        """レスポンスを返す"""
        import flask

        import my_lib.webapp.event as event_module

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        with app.test_client() as client:
            response = client.get("/api/event?count=0")
            assert response.status_code == 200
            assert response.content_type == "text/event-stream; charset=utf-8"

    def test_has_cors_headers(self):
        """CORS ヘッダーを持つ"""
        import flask

        import my_lib.webapp.event as event_module

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        with app.test_client() as client:
            response = client.get("/api/event?count=0")
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_has_cache_control(self):
        """Cache-Control ヘッダーを持つ"""
        import flask

        import my_lib.webapp.event as event_module

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        with app.test_client() as client:
            response = client.get("/api/event?count=0")
            assert "Cache-Control" in response.headers
            assert "no-cache" in response.headers["Cache-Control"]
