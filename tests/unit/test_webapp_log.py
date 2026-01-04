#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.log モジュールのユニットテスト
"""

from __future__ import annotations

import flask
import pytest


@pytest.fixture
def log_db_path(temp_dir):
    """テスト用のログデータベースパスを設定する"""
    import my_lib.webapp.config

    db_path = temp_dir / "log.db"
    my_lib.webapp.config.LOG_DIR_PATH = db_path
    yield db_path


class TestLogLevel:
    """LOG_LEVEL 列挙型のテスト"""

    def test_has_info(self):
        """INFO を持つ"""
        from my_lib.webapp.log import LOG_LEVEL

        assert LOG_LEVEL.INFO.value == 0

    def test_has_warn(self):
        """WARN を持つ"""
        from my_lib.webapp.log import LOG_LEVEL

        assert LOG_LEVEL.WARN.value == 1

    def test_has_error(self):
        """ERROR を持つ"""
        from my_lib.webapp.log import LOG_LEVEL

        assert LOG_LEVEL.ERROR.value == 2


class TestLogManager:
    """LogManager クラスのテスト"""

    def test_init(self):
        """初期化"""
        from my_lib.webapp.log import LogManager

        manager = LogManager()

        assert manager.config is None
        assert manager.get_log_thread() is None
        assert manager.get_queue_lock() is None

    def test_get_worker_id(self, monkeypatch):
        """ワーカー ID の取得"""
        from my_lib.webapp.log import LogManager

        manager = LogManager()

        # 環境変数がない場合
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert manager.get_worker_id() is None

        # 環境変数がある場合
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        assert manager.get_worker_id() == "gw0"

    def test_get_db_path(self, log_db_path, monkeypatch):
        """データベースパスの取得"""
        from my_lib.webapp.log import LogManager

        manager = LogManager()

        # ワーカー ID がない場合
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert manager.get_db_path() == log_db_path

    def test_get_db_path_with_worker_id(self, log_db_path, monkeypatch):
        """ワーカー ID がある場合のデータベースパスの取得"""
        from my_lib.webapp.log import LogManager

        manager = LogManager()

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
        db_path = manager.get_db_path()
        assert "test_worker_gw1" in str(db_path)

    def test_get_db_path_raises_without_init(self, monkeypatch):
        """LOG_DIR_PATH が未設定の場合はエラー"""
        import my_lib.webapp.config
        from my_lib.webapp.log import LogManager

        original = my_lib.webapp.config.LOG_DIR_PATH
        my_lib.webapp.config.LOG_DIR_PATH = None

        try:
            manager = LogManager()
            monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

            with pytest.raises(RuntimeError, match="LOG_DIR_PATH is not initialized"):
                manager.get_db_path()
        finally:
            my_lib.webapp.config.LOG_DIR_PATH = original


class TestInit:
    """init 関数のテスト"""

    def test_creates_database(self, log_db_path, monkeypatch):
        """データベースを作成する"""
        from my_lib.webapp.log import _manager, init, term

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        init({}, is_read_only=False)

        assert log_db_path.exists()
        assert _manager.get_log_thread() is not None

        term()

    def test_read_only_mode(self, log_db_path, monkeypatch):
        """読み取り専用モード"""
        from my_lib.webapp.log import _manager, init

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        init({}, is_read_only=True)

        assert log_db_path.exists()
        # 読み取り専用モードではスレッドは起動しない
        assert _manager.get_log_thread() is None


class TestTerm:
    """term 関数のテスト"""

    def test_does_not_raise_without_thread(self):
        """スレッドがなくてもエラーにならない"""
        from my_lib.webapp.log import term

        # 例外が発生しなければ OK
        term()

    def test_read_only_mode(self):
        """読み取り専用モードでは何もしない"""
        from my_lib.webapp.log import term

        # 例外が発生しなければ OK
        term(is_read_only=True)


class TestAdd:
    """add 関数のテスト"""

    def test_without_init_logs_warning(self, caplog):
        """初期化前は警告を出す"""
        from my_lib.webapp.log import LOG_LEVEL, LogManager

        manager = LogManager()
        manager.add("test message", LOG_LEVEL.INFO)

        assert "Log system not initialized" in caplog.text


class TestLoggingFunctions:
    """error, warning, info 関数のテスト"""

    def test_error_logs_message(self, caplog):
        """error はメッセージをログに出す"""
        import logging

        from my_lib.webapp.log import LogManager

        manager = LogManager()
        with caplog.at_level(logging.ERROR):
            manager.error("test error")

        assert "test error" in caplog.text

    def test_warning_logs_message(self, caplog):
        """warning はメッセージをログに出す"""
        import logging

        from my_lib.webapp.log import LogManager

        manager = LogManager()
        with caplog.at_level(logging.WARNING):
            manager.warning("test warning")

        assert "test warning" in caplog.text

    def test_info_logs_message(self, caplog):
        """info はメッセージをログに出す"""
        import logging

        from my_lib.webapp.log import LogManager

        manager = LogManager()
        with caplog.at_level(logging.INFO):
            manager.info("test info")

        assert "test info" in caplog.text


class TestGet:
    """get 関数のテスト"""

    def test_returns_empty_list_when_no_logs(self, log_db_path, monkeypatch):
        """ログがない場合は空リストを返す"""
        from my_lib.webapp.log import _manager, init

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        init({}, is_read_only=True)

        logs = _manager.get()
        assert logs == []


class TestClear:
    """clear 関数のテスト"""

    def test_clears_database(self, log_db_path, monkeypatch):
        """データベースをクリアする"""
        from my_lib.webapp.log import _manager, init

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        init({}, is_read_only=True)

        # クリア（例外が発生しなければ OK）
        _manager.clear()


class TestModuleFunctions:
    """モジュールレベル関数のテスト（テスト用）"""

    def test_get_worker_id(self, monkeypatch):
        """_get_worker_id が動作する"""
        from my_lib.webapp.log import _get_worker_id

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert _get_worker_id() is None

    def test_get_db_path(self, log_db_path, monkeypatch):
        """_get_db_path が動作する"""
        from my_lib.webapp.log import _get_db_path

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert _get_db_path() == log_db_path


class TestApiEndpoints:
    """API エンドポイントのテスト"""

    def test_api_log_view_returns_json(self, log_db_path, monkeypatch):
        """api_log_view は JSON を返す"""
        import my_lib.webapp.log as log_module

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        app = flask.Flask(__name__)
        app.config["TEST"] = True
        app.register_blueprint(log_module.blueprint)

        log_module.init({}, is_read_only=True)

        with app.test_client() as client:
            response = client.get("/api/log_view")
            assert response.status_code == 200
            data = response.get_json()
            assert "data" in data
            assert "last_time" in data

    def test_api_log_add_requires_test_mode(self, log_db_path, monkeypatch):
        """api_log_add はテストモードでないと 403"""
        import my_lib.webapp.log as log_module

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        app = flask.Flask(__name__)
        app.config["TEST"] = False
        app.register_blueprint(log_module.blueprint)

        log_module.init({}, is_read_only=True)

        with app.test_client() as client:
            response = client.post("/api/log_add", data={"message": "test"})
            assert response.status_code == 403

    def test_api_log_clear_without_init(self, log_db_path, monkeypatch):
        """api_log_clear は初期化前はエラーを返す"""
        import my_lib.webapp.log as log_module
        from my_lib.webapp.log import LogManager

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        # 新しい manager を使用（初期化されていない状態）
        original_manager = log_module._manager
        log_module._manager = LogManager()

        try:
            app = flask.Flask(__name__)
            app.config["TEST"] = True
            app.register_blueprint(log_module.blueprint)

            with app.test_client() as client:
                response = client.get("/api/log_clear")
                assert response.status_code == 200
                data = response.get_json()
                assert data["result"] == "error"
        finally:
            log_module._manager = original_manager
