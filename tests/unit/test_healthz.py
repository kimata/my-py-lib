#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.healthz モジュールのユニットテスト
"""

from __future__ import annotations

import pathlib
import time


class TestHealthzTarget:
    """HealthzTarget データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.healthz import HealthzTarget

        target = HealthzTarget(
            name="test",
            liveness_file=pathlib.Path("/tmp/test"),  # noqa: S108
            interval=60.0,
        )

        assert target.name == "test"
        assert target.liveness_file == pathlib.Path("/tmp/test")  # noqa: S108
        assert target.interval == 60.0


class TestCheckLiveness:
    """check_liveness 関数のテスト"""

    def test_returns_false_when_file_not_exists(self, temp_dir):
        """ファイルが存在しない場合 False を返す"""
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        target = HealthzTarget(
            name="test",
            liveness_file=temp_dir / "nonexistent",
            interval=60.0,
        )

        assert not my_lib.healthz.check_liveness(target)

    def test_returns_true_when_recently_updated(self, temp_dir):
        """最近更新されたファイルに対して True を返す"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file = temp_dir / "liveness"
        my_lib.footprint.update(liveness_file)

        target = HealthzTarget(
            name="test",
            liveness_file=liveness_file,
            interval=60.0,
        )

        assert my_lib.healthz.check_liveness(target)

    def test_returns_false_when_too_old(self, temp_dir):
        """古すぎるファイルに対して False を返す"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file = temp_dir / "liveness"
        # 1時間前の時刻を設定
        old_time = time.time() - 3600
        my_lib.footprint.update(liveness_file, mtime=old_time)

        target = HealthzTarget(
            name="test",
            liveness_file=liveness_file,
            interval=60.0,
        )

        assert not my_lib.healthz.check_liveness(target)

    def test_returns_elapsed_when_stale(self, temp_dir):
        """古すぎるファイルに対して経過秒を返す"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file = temp_dir / "liveness"
        old_time = time.time() - 3600
        my_lib.footprint.update(liveness_file, mtime=old_time)

        target = HealthzTarget(
            name="test",
            liveness_file=liveness_file,
            interval=60.0,
        )

        elapsed = my_lib.healthz.check_liveness_elapsed(target)
        assert elapsed is not None
        assert elapsed > 0


class TestCheckLivenessAll:
    """check_liveness_all 関数のテスト"""

    def test_returns_empty_list_when_all_healthy(self, temp_dir):
        """全て健全な場合、空のリストを返す"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file1 = temp_dir / "liveness1"
        liveness_file2 = temp_dir / "liveness2"
        my_lib.footprint.update(liveness_file1)
        my_lib.footprint.update(liveness_file2)

        targets = [
            HealthzTarget(name="target1", liveness_file=liveness_file1, interval=60.0),
            HealthzTarget(name="target2", liveness_file=liveness_file2, interval=60.0),
        ]

        result = my_lib.healthz.check_liveness_all(targets)
        assert result == []

    def test_returns_failed_target_names(self, temp_dir):
        """失敗したターゲット名のリストを返す"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file1 = temp_dir / "liveness1"
        my_lib.footprint.update(liveness_file1)

        targets = [
            HealthzTarget(name="healthy", liveness_file=liveness_file1, interval=60.0),
            HealthzTarget(name="unhealthy", liveness_file=temp_dir / "nonexistent", interval=60.0),
        ]

        result = my_lib.healthz.check_liveness_all(targets)
        assert result == ["unhealthy"]


class TestCheckLivenessAllWithPorts:
    """check_liveness_all_with_ports 関数のテスト"""

    def test_returns_port_failure(self, temp_dir):
        """HTTPポートチェックが失敗する場合に失敗リストへ追加"""
        import my_lib.footprint
        import my_lib.healthz
        from my_lib.healthz import HealthzTarget

        liveness_file = temp_dir / "liveness"
        my_lib.footprint.update(liveness_file)

        targets = [
            HealthzTarget(name="target", liveness_file=liveness_file, interval=60.0),
        ]

        result = my_lib.healthz.check_liveness_all_with_ports(targets, http_port=59999)
        assert "http_port" in result


class TestCheckTcpPort:
    """check_tcp_port 関数のテスト"""

    def test_returns_false_for_closed_port(self):
        """閉じているポートに対して False を返す"""
        import my_lib.healthz

        # 閉じていると思われるポート
        assert not my_lib.healthz.check_tcp_port(59999, "127.0.0.1")

    def test_handles_connection_error_gracefully(self):
        """接続エラーを適切に処理する"""
        import my_lib.healthz

        # 存在しないホスト
        result = my_lib.healthz.check_tcp_port(80, "192.0.2.1")  # TEST-NET-1
        assert result is False


class TestCheckHttpPort:
    """check_http_port 関数のテスト"""

    def test_returns_false_for_closed_port(self):
        """閉じているポートに対して False を返す"""
        import my_lib.healthz

        assert not my_lib.healthz.check_http_port(59999, "127.0.0.1")

    def test_handles_connection_error_gracefully(self):
        """接続エラーを適切に処理する"""
        import my_lib.healthz

        result = my_lib.healthz.check_http_port(80, "192.0.2.1")  # TEST-NET-1
        assert result is False

    def test_returns_true_for_successful_response(self, mocker):
        """成功したレスポンスに対して True を返す"""
        import my_lib.healthz

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mocker.patch("requests.get", return_value=mock_response)

        assert my_lib.healthz.check_http_port(80, "127.0.0.1")

    def test_returns_false_for_non_200_response(self, mocker):
        """200 以外のレスポンスに対して False を返す"""
        import my_lib.healthz

        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mocker.patch("requests.get", return_value=mock_response)

        assert not my_lib.healthz.check_http_port(80, "127.0.0.1")
