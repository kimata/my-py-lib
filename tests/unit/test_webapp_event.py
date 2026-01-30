#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.event モジュールのユニットテスト
"""

from __future__ import annotations


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

    def test_has_content(self):
        """CONTENT を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.CONTENT.value == "content"

    def test_has_log(self):
        """LOG を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.LOG.value == "log"

    def test_index_property(self):
        """index プロパティが正しい値を返す"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.CONTROL.index == 0
        assert EVENT_TYPE.CONTENT.index == 1
        assert EVENT_TYPE.SCHEDULE.index == 2
        assert EVENT_TYPE.LOG.index == 3


class TestNotifyEvent:
    """notify_event 関数のテスト"""

    def test_increments_event_count(self):
        """イベントカウントを増加させる"""
        from my_lib.webapp.event import EVENT_TYPE, _manager, notify_event

        initial = _manager.event_count[EVENT_TYPE.LOG.index]
        notify_event(EVENT_TYPE.LOG)

        assert _manager.event_count[EVENT_TYPE.LOG.index] == initial + 1


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

        from my_lib.webapp.event import _manager, term

        mock_thread = unittest.mock.MagicMock(spec=threading.Thread)
        _manager.watch_thread = mock_thread
        _manager.should_terminate = False

        term()

        assert _manager.should_terminate is True
        assert _manager.watch_thread is None


class TestStart:
    """start 関数のテスト"""

    def test_starts_watch_thread(self):
        """ウォッチスレッドを開始する"""
        import multiprocessing
        import time

        from my_lib.webapp.event import _manager, start, term

        queue = multiprocessing.Queue()

        start(queue)

        assert _manager.watch_thread is not None
        assert _manager.should_terminate is False

        term()
        time.sleep(0.2)


class TestWorker:
    """EventManager._worker メソッドのテスト"""

    def test_processes_events(self):
        """イベントを処理する"""
        import multiprocessing
        import threading
        import time

        from my_lib.webapp.event import EVENT_TYPE, _manager

        queue = multiprocessing.Queue()
        queue.put(EVENT_TYPE.LOG)

        _manager.should_terminate = False

        def run_worker():
            time.sleep(0.2)
            _manager.should_terminate = True

        threading.Thread(target=run_worker).start()
        _manager._worker(queue)

    def test_stops_on_terminate(self):
        """終了フラグで停止する"""
        import multiprocessing

        from my_lib.webapp.event import _manager

        queue = multiprocessing.Queue()
        _manager.should_terminate = True

        _manager._worker(queue)


class TestEventManager:
    """EventManager クラスのテスト"""

    def test_init(self):
        """初期化"""
        from my_lib.webapp.event import EVENT_TYPE, EventManager

        manager = EventManager()

        assert manager.should_terminate is False
        assert manager.watch_thread is None
        assert len(manager.event_count) == len(EVENT_TYPE) + 1

    def test_notify_event(self):
        """イベント通知"""
        from my_lib.webapp.event import EVENT_TYPE, EventManager

        manager = EventManager()
        initial = manager.event_count[EVENT_TYPE.CONTROL.index]

        manager.notify_event(EVENT_TYPE.CONTROL)

        assert manager.event_count[EVENT_TYPE.CONTROL.index] == initial + 1

    def test_start_and_term(self):
        """スレッドの開始と終了"""
        import multiprocessing
        import time

        from my_lib.webapp.event import EventManager

        manager = EventManager()
        queue = multiprocessing.Queue()

        manager.start(queue)

        assert manager.watch_thread is not None
        assert manager.should_terminate is False

        manager.term()
        time.sleep(0.2)

        assert manager.watch_thread is None
        assert manager.should_terminate is True

    def test_get_event_stream(self):
        """イベントストリーム生成"""
        import threading
        import time

        from my_lib.webapp.event import EVENT_TYPE, EventManager

        manager = EventManager()

        def trigger_event():
            time.sleep(0.1)
            manager.notify_event(EVENT_TYPE.SCHEDULE)

        threading.Thread(target=trigger_event).start()

        stream = manager.get_event_stream(count=1)
        # 最初のダミーデータをスキップ
        dummy = next(stream)
        assert "data: dummy" in dummy
        result = next(stream)

        assert "data: schedule" in result


class TestDbStateWatcher:
    """DB 監視ヘルパのテスト"""

    def test_notifies_on_state_change(self, tmp_path):
        """状態変化時に通知される"""
        import sqlite3
        import time

        from my_lib.webapp.event import EVENT_TYPE, _manager, start_db_state_watcher, stop_db_state_watcher

        db_path = tmp_path / "test.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS state (value TEXT)")
            conn.execute("INSERT INTO state (value) VALUES ('a')")
            conn.commit()

        def _get_state(path):
            with sqlite3.connect(path) as conn:
                cursor = conn.execute("SELECT MAX(value) FROM state")
                row = cursor.fetchone()
                return row[0] if row else None

        initial = _manager.event_count[EVENT_TYPE.CONTROL.index]

        stop_event, thread = start_db_state_watcher(
            db_path,
            _get_state,
            EVENT_TYPE.CONTROL,
            interval_sec=0.05,
        )

        # NOTE: 初回チェックで last_state が設定される（notify_on_first=False のため通知されない）
        # 状態変化を検出するには、2回状態を変更する必要がある
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT INTO state (value) VALUES ('b')")
            conn.commit()

        time.sleep(0.15)

        # 2回目の状態変更で通知される
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT INTO state (value) VALUES ('c')")
            conn.commit()

        time.sleep(0.15)

        stop_db_state_watcher(stop_event, thread)

        assert _manager.event_count[EVENT_TYPE.CONTROL.index] >= initial + 1


class TestApiEvent:
    """api_event 関数のテスト"""

    def test_returns_response(self):
        """レスポンスを返す"""
        import threading
        import time

        import flask

        import my_lib.webapp.event as event_module
        from my_lib.webapp.event import EVENT_TYPE

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        # リクエスト中にイベントを発生させるスレッド
        def trigger_event():
            time.sleep(0.1)
            event_module.notify_event(EVENT_TYPE.LOG)

        threading.Thread(target=trigger_event).start()

        with app.test_client() as client:
            response = client.get("/api/event?count=1")
            assert response.status_code == 200
            assert response.content_type == "text/event-stream; charset=utf-8"

    def test_has_cors_headers(self):
        """CORS ヘッダーを持つ"""
        import threading
        import time

        import flask

        import my_lib.webapp.event as event_module
        from my_lib.webapp.event import EVENT_TYPE

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        def trigger_event():
            time.sleep(0.1)
            event_module.notify_event(EVENT_TYPE.LOG)

        threading.Thread(target=trigger_event).start()

        with app.test_client() as client:
            response = client.get("/api/event?count=1")
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_has_cache_control(self):
        """Cache-Control ヘッダーを持つ"""
        import threading
        import time

        import flask

        import my_lib.webapp.event as event_module
        from my_lib.webapp.event import EVENT_TYPE

        app = flask.Flask(__name__)
        app.register_blueprint(event_module.blueprint)

        def trigger_event():
            time.sleep(0.1)
            event_module.notify_event(EVENT_TYPE.LOG)

        threading.Thread(target=trigger_event).start()

        with app.test_client() as client:
            response = client.get("/api/event?count=1")
            assert "Cache-Control" in response.headers
            assert "no-cache" in response.headers["Cache-Control"]
