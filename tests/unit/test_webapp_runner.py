#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.runner モジュールのユニットテスト
"""

from __future__ import annotations

import logging
import signal

import pytest

DOC = """
Web UI サーバです。

Usage:
  webui.py [-c CONFIG] [-p PORT] [-D] [-d]

Options:
  -c CONFIG         : 設定ファイルを指定します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
  -d                : ダミーモードで実行します。
"""


class FakeApp:
    def __init__(self):
        self.run_kwargs = None

    def run(self, **kwargs):
        self.run_kwargs = kwargs


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    """logger 初期化・プロセスグループ操作・シグナル登録を無効化する"""
    import my_lib.logger
    import my_lib.webapp.runner as runner

    monkeypatch.setattr(my_lib.logger, "init", lambda *args, **kwargs: None)
    monkeypatch.setattr("os.setpgrp", lambda: None)
    monkeypatch.setattr("atexit.register", lambda func: func)
    monkeypatch.setattr(signal, "signal", lambda *args: None)
    monkeypatch.setattr(runner, "_kill_own_process_group", lambda: None)


@pytest.fixture
def config_file(temp_dir):
    path = temp_dir / "config.yaml"
    path.write_text("dummy: true\n")
    return path


def _make_spec(**kwargs):
    import my_lib.webapp.runner as runner

    defaults = {
        "logger_name": "test.webui",
        "app_factory": lambda config, ctx: FakeApp(),
        "config_loader": lambda config_file, args: {"file": config_file},
    }
    defaults.update(kwargs)
    return runner.WebAppSpec(**defaults)


class TestRun:
    """run 関数のテスト"""

    def test_runs_app_with_defaults(self, config_file, monkeypatch):
        """デフォルト設定で app.run が正しい引数で呼ばれる"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file), "-p", "8123"])

        created = {}

        def factory(config, ctx):
            app = FakeApp()
            created["app"] = app
            created["ctx"] = ctx
            created["config"] = config
            return app

        spec = _make_spec(app_factory=factory)
        runner.run(spec, DOC)

        app = created["app"]
        assert app.run_kwargs == {
            "host": "0.0.0.0",  # noqa: S104
            "port": 8123,
            "threaded": True,
            "use_reloader": True,
            "debug": False,
        }
        assert created["config"] == {"file": str(config_file)}
        ctx = created["ctx"]
        assert ctx.debug_mode is False
        assert ctx.dummy_mode is False
        assert ctx.use_reloader is True

    def test_debug_and_dummy_flags(self, config_file, monkeypatch):
        """-D / -d が RunContext と app.run に反映される"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file), "-D", "-d"])

        created = {}

        def factory(config, ctx):
            created["ctx"] = ctx
            app = FakeApp()
            created["app"] = app
            return app

        spec = _make_spec(app_factory=factory)
        runner.run(spec, DOC)

        assert created["ctx"].debug_mode is True
        assert created["ctx"].dummy_mode is True
        assert created["app"].run_kwargs["debug"] is True

    def test_reloader_resolver(self, config_file, monkeypatch):
        """use_reloader に callable を渡すと args で判定される"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file)])

        created = {}

        def factory(config, ctx):
            created["ctx"] = ctx
            app = FakeApp()
            created["app"] = app
            return app

        spec = _make_spec(app_factory=factory, use_reloader=lambda args: False)
        runner.run(spec, DOC)

        assert created["ctx"].use_reloader is False
        assert created["app"].run_kwargs["use_reloader"] is False

    def test_port_resolver(self, config_file, monkeypatch):
        """port_resolver 指定時は -p ではなく解決結果を使う"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file), "-p", "5000"])

        created = {}

        def factory(config, ctx):
            app = FakeApp()
            created["app"] = app
            return app

        spec = _make_spec(app_factory=factory, port_resolver=lambda config, args: 9999)
        runner.run(spec, DOC)

        assert created["app"].run_kwargs["port"] == 9999

    def test_default_config_loader(self, temp_dir, monkeypatch):
        """config_loader 未指定時は my_lib.config.load が使われる"""
        import my_lib.webapp.runner as runner

        config_file = temp_dir / "config.yaml"
        config_file.write_text("webapp:\n    port: 1234\n")
        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file)])

        created = {}

        def factory(config, ctx):
            created["config"] = config
            return FakeApp()

        spec = _make_spec(app_factory=factory, config_loader=None)
        runner.run(spec, DOC)

        assert created["config"]["webapp"]["port"] == 1234

    def test_keyboard_interrupt_triggers_shutdown(self, config_file, monkeypatch):
        """app.run の KeyboardInterrupt で graceful shutdown が走る"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file)])

        called = []

        class RaisingApp:
            def run(self, **kwargs):
                raise KeyboardInterrupt

        monkeypatch.setattr("my_lib.proc_util.kill_child", lambda: called.append("kill_child"), raising=True)

        spec = _make_spec(
            app_factory=lambda config, ctx: RaisingApp(),
            term_hooks=(lambda: called.append("term"),),
        )

        with pytest.raises(SystemExit) as excinfo:
            runner.run(spec, DOC)

        assert excinfo.value.code == 0
        assert called == ["term", "kill_child"]

    def test_term_hook_exception_does_not_block_shutdown(self, config_file, monkeypatch, caplog):
        """term_hook の例外があっても shutdown は継続する"""
        import my_lib.webapp.runner as runner

        monkeypatch.setattr("sys.argv", ["webui.py", "-c", str(config_file)])
        monkeypatch.setattr("my_lib.proc_util.kill_child", lambda: None, raising=True)

        class RaisingApp:
            def run(self, **kwargs):
                raise KeyboardInterrupt

        def bad_hook():
            raise RuntimeError("boom")

        spec = _make_spec(app_factory=lambda config, ctx: RaisingApp(), term_hooks=(bad_hook,))

        with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as excinfo:
            runner.run(spec, DOC)

        assert excinfo.value.code == 0
        assert "Error in term hook" in caplog.text


class TestShouldInit:
    """should_init 関数のテスト"""

    def test_no_reloader_always_init(self, monkeypatch):
        """リローダーなしなら常に初期化する"""
        import my_lib.webapp.runner as runner

        monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
        assert runner.should_init(use_reloader=False) is True

    def test_reloader_parent_skips_init(self, monkeypatch):
        """リローダー親プロセス (WERKZEUG_RUN_MAIN 未設定) では初期化しない"""
        import my_lib.webapp.runner as runner

        monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
        assert runner.should_init(use_reloader=True) is False

    def test_reloader_child_inits(self, monkeypatch):
        """リローダー子プロセス (WERKZEUG_RUN_MAIN=true) では初期化する"""
        import my_lib.webapp.runner as runner

        monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
        assert runner.should_init(use_reloader=True) is True


class TestSilenceWerkzeugLog:
    """silence_werkzeug_log 関数のテスト"""

    def test_sets_error_level(self):
        """werkzeug ロガーが ERROR レベルになる"""
        import my_lib.webapp.runner as runner

        runner.silence_werkzeug_log()
        assert logging.getLogger("werkzeug").level == logging.ERROR
