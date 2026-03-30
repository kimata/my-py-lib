#!/usr/bin/env python3
# ruff: noqa: S101
"""my_lib.webapp.config モジュールのユニットテスト."""

from __future__ import annotations

import flask


class TestWebappConfig:
    """WebappConfig / WebappDataConfig のテスト"""

    def test_parse(self, temp_dir):
        """dict から設定を生成できる"""
        import my_lib.webapp.config

        config = my_lib.webapp.config.WebappConfig.parse(
            {
                "static_dir_path": str(temp_dir / "static"),
                "external_url": "https://example.com/app",
                "data": {
                    "schedule_file_path": str(temp_dir / "schedule.yaml"),
                    "log_file_path": str(temp_dir / "log.db"),
                    "stat_dir_path": str(temp_dir / "stat"),
                },
            }
        )

        assert config.static_dir_path == (temp_dir / "static").resolve()
        assert config.external_url == "https://example.com/app"
        assert config.data is not None
        assert config.data.schedule_file_path == (temp_dir / "schedule.yaml").resolve()
        assert config.data.log_file_path == (temp_dir / "log.db").resolve()
        assert config.data.stat_dir_path == (temp_dir / "stat").resolve()


class TestBuildEnvironment:
    """build_environment 関数のテスト"""

    def test_sets_runtime_paths(self, temp_dir):
        """runtime environment を組み立てる"""
        import my_lib.webapp.config

        config = my_lib.webapp.config.WebappConfig.parse(
            {
                "static_dir_path": str(temp_dir / "static"),
                "data": {
                    "schedule_file_path": str(temp_dir / "schedule.yaml"),
                    "log_file_path": str(temp_dir / "log.db"),
                    "stat_dir_path": str(temp_dir / "stat"),
                },
            }
        )

        environment = my_lib.webapp.config.build_environment(config, url_prefix="/test")

        assert environment.url_prefix == "/test"
        assert environment.static_dir_path == (temp_dir / "static").resolve()
        assert environment.schedule_file_path == (temp_dir / "schedule.yaml").resolve()
        assert environment.log_file_path == (temp_dir / "log.db").resolve()
        assert environment.stat_dir_path == (temp_dir / "stat").resolve()


class TestShowHandlerList:
    """show_handler_list 関数のテスト"""

    def test_does_not_raise(self, monkeypatch):
        """エラーを発生させない"""
        import my_lib.webapp.config

        app = flask.Flask(__name__)

        # WERKZEUG_RUN_MAIN を設定しないとスキップされる
        monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")

        # 例外が発生しなければ OK
        my_lib.webapp.config.show_handler_list(app)

    def test_skips_without_werkzeug_run_main(self, monkeypatch):
        """WERKZEUG_RUN_MAIN がない場合はスキップする"""
        import my_lib.webapp.config

        app = flask.Flask(__name__)

        monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

        # 例外が発生しなければ OK
        my_lib.webapp.config.show_handler_list(app)

    def test_with_is_force(self, monkeypatch):
        """is_force=True の場合は強制実行する"""
        import my_lib.webapp.config

        app = flask.Flask(__name__)

        monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

        # 例外が発生しなければ OK
        my_lib.webapp.config.show_handler_list(app, is_force=True)
