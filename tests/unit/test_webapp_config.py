#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.config モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import flask
import pytest


class TestConstants:
    """定数のテスト"""

    def test_url_prefix_default(self):
        """URL_PREFIX のデフォルト値"""
        from my_lib.webapp.config import URL_PREFIX

        # デフォルトは None
        assert URL_PREFIX is None

    def test_zoneinfo_exists(self):
        """ZONEINFO が存在する"""
        from my_lib.webapp.config import ZONEINFO

        assert ZONEINFO is not None

    def test_pytz_exists(self):
        """PYTZ が存在する"""
        from my_lib.webapp.config import PYTZ

        assert PYTZ is not None


class TestInit:
    """init 関数のテスト"""

    def test_sets_static_dir_path(self, temp_dir):
        """STATIC_DIR_PATH を設定する"""
        import my_lib.webapp.config

        config_dict = {"static_dir_path": str(temp_dir / "static")}
        config = my_lib.webapp.config.WebappConfig.from_dict(config_dict)

        my_lib.webapp.config.init(config)

        assert my_lib.webapp.config.STATIC_DIR_PATH is not None

    def test_sets_schedule_file_path(self, temp_dir):
        """SCHEDULE_FILE_PATH を設定する"""
        import my_lib.webapp.config

        config_dict = {
            "data": {
                "schedule_file_path": str(temp_dir / "schedule.yaml"),
            }
        }
        config = my_lib.webapp.config.WebappConfig.from_dict(config_dict)

        my_lib.webapp.config.init(config)

        assert my_lib.webapp.config.SCHEDULE_FILE_PATH is not None

    def test_sets_log_dir_path(self, temp_dir):
        """LOG_DIR_PATH を設定する"""
        import my_lib.webapp.config

        config_dict = {
            "data": {
                "log_file_path": str(temp_dir / "log.db"),
            }
        }
        config = my_lib.webapp.config.WebappConfig.from_dict(config_dict)

        my_lib.webapp.config.init(config)

        assert my_lib.webapp.config.LOG_DIR_PATH is not None

    def test_sets_stat_dir_path(self, temp_dir):
        """STAT_DIR_PATH を設定する"""
        import my_lib.webapp.config

        config_dict = {
            "data": {
                "stat_dir_path": str(temp_dir / "stat"),
            }
        }
        config = my_lib.webapp.config.WebappConfig.from_dict(config_dict)

        my_lib.webapp.config.init(config)

        assert my_lib.webapp.config.STAT_DIR_PATH is not None


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
