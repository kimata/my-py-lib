#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.healthz.cli モジュールのユニットテスト
"""

from __future__ import annotations

import pathlib

import pytest

DOC = """
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

DOC_WITH_PORT = """
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""


@pytest.fixture
def config_file(temp_dir):
    """ダミーの設定ファイルを作成して config_loader で使う"""
    path = temp_dir / "config.yaml"
    path.write_text("dummy: true\n")
    return path


@pytest.fixture(autouse=True)
def _no_logger_init(monkeypatch):
    """logger 初期化はテスト出力を汚すので無効化する"""
    import my_lib.logger

    monkeypatch.setattr(my_lib.logger, "init", lambda *args, **kwargs: None)


def _make_spec(**kwargs):
    import my_lib.healthz.cli

    defaults = {
        "logger_name": "test.healthz",
        "targets_builder": lambda config, args: [],
        "config_loader": lambda config_file, args: {"file": config_file},
    }
    defaults.update(kwargs)
    return my_lib.healthz.cli.HealthzCliSpec(**defaults)


def _run(spec, doc, argv):
    import my_lib.healthz.cli

    with pytest.raises(SystemExit) as excinfo:
        my_lib.healthz.cli.run(spec, doc)
    return excinfo.value.code


def _fresh_target(temp_dir, name="worker"):
    import my_lib.footprint
    import my_lib.healthz

    liveness_file = temp_dir / f"{name}.liveness"
    my_lib.footprint.update(liveness_file)
    return my_lib.healthz.HealthzTarget(name=name, liveness_file=liveness_file, interval=60)


class TestRun:
    """run 関数のテスト"""

    def test_all_ok_exits_zero(self, temp_dir, config_file, monkeypatch):
        """全チェック成功で exit code 0"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        target = _fresh_target(temp_dir)
        spec = _make_spec(targets_builder=lambda config, args: [target])

        assert _run(spec, DOC, None) == 0

    def test_missing_liveness_exits_one(self, temp_dir, config_file, monkeypatch):
        """liveness ファイルが無いと exit code 1"""
        import my_lib.healthz

        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        target = my_lib.healthz.HealthzTarget(
            name="worker", liveness_file=temp_dir / "missing.liveness", interval=60
        )
        spec = _make_spec(targets_builder=lambda config, args: [target])

        assert _run(spec, DOC, None) == 1

    def test_targets_builder_receives_config_and_args(self, temp_dir, config_file, monkeypatch):
        """targets_builder に config と docopt args が渡される"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        received = {}

        def builder(config, args):
            received["config"] = config
            received["args"] = args
            return [_fresh_target(temp_dir)]

        spec = _make_spec(targets_builder=builder)

        assert _run(spec, DOC, None) == 0
        assert received["config"] == {"file": str(config_file)}
        assert received["args"]["-c"] == str(config_file)

    def test_targets_builder_value_error_exits_one(self, config_file, monkeypatch):
        """targets_builder の ValueError (未知モード等) は exit code 1"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        def builder(config, args):
            raise ValueError("Unknown mode")

        spec = _make_spec(targets_builder=builder)

        assert _run(spec, DOC, None) == 1

    def test_default_config_loader(self, temp_dir, monkeypatch):
        """config_loader 未指定時は my_lib.config.load が使われる"""

        config_file = temp_dir / "config.yaml"
        config_file.write_text("liveness:\n    interval: 10\n")
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        received = {}

        def builder(config, args):
            received["config"] = config
            return [_fresh_target(temp_dir)]

        spec = _make_spec(config_loader=None, targets_builder=builder)

        assert _run(spec, DOC, None) == 0
        assert received["config"]["liveness"]["interval"] == 10
        # my_lib.config.load は base_dir を付与する
        assert "base_dir" in received["config"]

    def test_extra_check_failure_exits_one(self, temp_dir, config_file, monkeypatch):
        """extra_checks の失敗で exit code 1"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        def failing_check(config, args):
            return False

        spec = _make_spec(
            targets_builder=lambda config, args: [_fresh_target(temp_dir)],
            extra_checks=(failing_check,),
        )

        assert _run(spec, DOC, None) == 1

    def test_extra_check_success_exits_zero(self, temp_dir, config_file, monkeypatch):
        """extra_checks が成功すれば exit code 0"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        spec = _make_spec(
            targets_builder=lambda config, args: [_fresh_target(temp_dir)],
            extra_checks=(lambda config, args: True,),
        )

        assert _run(spec, DOC, None) == 0

    def test_failure_handler_called_on_failure(self, temp_dir, config_file, monkeypatch):
        """失敗時に failure_handler が失敗対象名とともに呼ばれる"""
        import my_lib.healthz

        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        target = my_lib.healthz.HealthzTarget(
            name="worker", liveness_file=temp_dir / "missing.liveness", interval=60
        )
        received = {}

        def handler(config, args, failed):
            received["failed"] = failed

        spec = _make_spec(targets_builder=lambda config, args: [target], failure_handler=handler)

        assert _run(spec, DOC, None) == 1
        assert received["failed"] == ["worker"]

    def test_failure_handler_not_called_on_success(self, temp_dir, config_file, monkeypatch):
        """成功時は failure_handler が呼ばれない"""
        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file)])

        called = []
        spec = _make_spec(
            targets_builder=lambda config, args: [_fresh_target(temp_dir)],
            failure_handler=lambda config, args, failed: called.append(failed),
        )

        assert _run(spec, DOC, None) == 0
        assert called == []

    def test_http_port_check(self, temp_dir, config_file, monkeypatch):
        """use_http_port で -p のポートがチェックされる"""
        import my_lib.healthz

        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file), "-p", "5000"])

        received = {}

        def fake_check(port, address="127.0.0.1"):
            received["port"] = port
            return True

        monkeypatch.setattr(my_lib.healthz, "check_http_port", fake_check)

        spec = _make_spec(
            targets_builder=lambda config, args: [_fresh_target(temp_dir)],
            use_http_port=True,
        )

        assert _run(spec, DOC_WITH_PORT, None) == 0
        assert received["port"] == 5000

    def test_http_port_disabled_by_predicate(self, temp_dir, config_file, monkeypatch):
        """http_port_enabled が False を返すとポートチェックしない"""
        import my_lib.healthz

        monkeypatch.setattr("sys.argv", ["healthz.py", "-c", str(config_file), "-p", "5000"])

        def fail_if_called(port, address="127.0.0.1"):
            pytest.fail("port check should be skipped")

        monkeypatch.setattr(my_lib.healthz, "check_http_port", fail_if_called)

        spec = _make_spec(
            targets_builder=lambda config, args: [_fresh_target(temp_dir)],
            use_http_port=True,
            http_port_enabled=lambda config, args: False,
        )

        assert _run(spec, DOC_WITH_PORT, None) == 0


class TestWithinStartupGrace:
    """within_startup_grace 関数のテスト"""

    def test_within_grace(self, monkeypatch):
        """uptime が猶予以下なら True"""
        import my_lib.container_util
        import my_lib.healthz.cli

        monkeypatch.setattr(my_lib.container_util, "get_uptime", lambda: 10.0)

        assert my_lib.healthz.cli.within_startup_grace(60) is True

    def test_past_grace(self, monkeypatch):
        """uptime が猶予を超えていれば False"""
        import my_lib.container_util
        import my_lib.healthz.cli

        monkeypatch.setattr(my_lib.container_util, "get_uptime", lambda: 120.0)

        assert my_lib.healthz.cli.within_startup_grace(60) is False


class TestPackageCompat:
    """healthz のパッケージ化で既存 API が壊れていないことの確認"""

    def test_flat_api_still_available(self):
        """my_lib.healthz 直下の既存 API が参照できる"""
        import my_lib.healthz

        assert hasattr(my_lib.healthz, "HealthzTarget")
        assert hasattr(my_lib.healthz, "HttpHealthzTarget")
        assert hasattr(my_lib.healthz, "check_liveness_all_with_ports")
        assert hasattr(my_lib.healthz, "check_healthz_all")

    def test_target_dataclass(self):
        """HealthzTarget が従来どおり生成できる"""
        import my_lib.healthz

        target = my_lib.healthz.HealthzTarget(
            name="test",
            liveness_file=pathlib.Path("/tmp/test"),  # noqa: S108
            interval=60.0,
        )
        assert target.name == "test"
