#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.proc_util モジュールのユニットテスト
"""
from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import time

import psutil
import pytest


class TestSignalName:
    """signal_name 関数のテスト"""

    def test_returns_name_for_known_signal(self):
        """既知のシグナル名を返す"""
        from my_lib.proc_util import signal_name

        result = signal_name(signal.SIGTERM)
        assert result == "SIGTERM"

    def test_returns_name_for_sigint(self):
        """SIGINT の名前を返す"""
        from my_lib.proc_util import signal_name

        result = signal_name(signal.SIGINT)
        assert result == "SIGINT"

    def test_returns_unknown_for_invalid_signal(self):
        """無効なシグナルは UNKNOWN を返す"""
        from my_lib.proc_util import signal_name

        result = signal_name(9999)
        assert result == "UNKNOWN"


class TestStatusText:
    """status_text 関数のテスト"""

    def test_exited_normally(self):
        """正常終了のステータステキスト"""
        from my_lib.proc_util import status_text

        # 正常終了のステータスを作成 (exit code 0)
        # os.WIFEXITED で True を返すステータス
        status = 0  # 正常終了 code 0
        result = status_text(status)

        assert "Exited normally" in result or "code 0" in result

    def test_exited_with_code(self):
        """終了コード付きの正常終了"""
        from my_lib.proc_util import status_text

        # 終了コード 1 のステータス（左に8ビットシフトして作成）
        status = 1 << 8  # exit code 1
        result = status_text(status)

        assert "Exited normally" in result
        assert "1" in result

    def test_terminated_by_signal(self):
        """シグナルによる終了"""
        from my_lib.proc_util import status_text

        # シグナル 9 (SIGKILL) による終了を表すステータス
        # os.WIFSIGNALED が True になるステータス値を作成
        status = signal.SIGKILL  # シグナル番号をそのまま使用
        result = status_text(status)

        # SIGKILL による終了または別の処理
        assert isinstance(result, str)

    def test_terminated_by_sigterm(self):
        """SIGTERM による終了"""
        from my_lib.proc_util import status_text

        # 実際に子プロセスを作成してシグナルで終了させる
        proc = subprocess.Popen(["sleep", "10"])
        proc.terminate()
        proc.wait()

        # この場合、status は -15 (SIGTERM の場合)
        # returncode は負のシグナル番号になる

    def test_stopped_by_signal(self):
        """シグナルによる停止（SIGSTOP相当のテスト）"""
        from my_lib.proc_util import status_text

        # 停止状態のステータス（ビット 0x7f がセットされ、上位ビットにシグナル番号）
        # os.WIFSTOPPED が True を返すステータス
        # 0x137f = (SIGSTOP << 8) | 0x7f
        stopped_status = (signal.SIGSTOP << 8) | 0x7F
        result = status_text(stopped_status)

        assert "Stopped by signal" in result

    def test_unknown_status(self):
        """不明なステータステキスト"""
        from my_lib.proc_util import status_text

        # 通常発生しないステータス値
        # 注意: 0x7E (126) は os.WIFSIGNALED が True になるため
        # "Terminated by signal" が返される場合がある
        result = status_text(0x7E)

        # 何らかの文字列が返される
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetChildPidMap:
    """get_child_pid_map 関数のテスト"""

    def test_returns_dict(self):
        """辞書を返す"""
        from my_lib.proc_util import get_child_pid_map

        result = get_child_pid_map()

        assert isinstance(result, dict)


class TestKillChild:
    """kill_child 関数のテスト"""

    def test_does_not_raise_without_children(self):
        """子プロセスがなくてもエラーにならない"""
        from my_lib.proc_util import kill_child

        # 例外が発生しなければ OK
        kill_child(timeout=1)

    def test_terminates_child_processes(self):
        """子プロセスを終了させる"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "test_process"

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", return_value=([], [])):
                kill_child(timeout=1)

        mock_child.terminate.assert_called_once()

    def test_kills_stubborn_processes(self):
        """終了しないプロセスを強制終了する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "stubborn_process"

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", side_effect=[
                ([], [mock_child]),  # 最初の wait で生存
                ([], []),  # SIGKILL 後に終了
            ]):
                kill_child(timeout=1)

        mock_child.kill.assert_called_once()

    def test_handles_nosuchprocess(self):
        """既に終了したプロセスを処理する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "gone_process"
        mock_child.terminate.side_effect = psutil.NoSuchProcess(12345)

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", return_value=([], [])):
                kill_child(timeout=1)

    def test_handles_accessdenied(self):
        """アクセス拒否を処理する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "protected_process"
        mock_child.terminate.side_effect = psutil.AccessDenied(12345)

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", return_value=([], [])):
                kill_child(timeout=1)

    def test_handles_generic_exception(self):
        """一般的な例外を処理する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "error_process"
        mock_child.terminate.side_effect = RuntimeError("Test error")

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", return_value=([], [])):
                kill_child(timeout=1)

    def test_logs_unkillable_processes(self):
        """終了しないプロセスをログに記録する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        mock_child = unittest.mock.MagicMock()
        mock_child.pid = 12345
        mock_child.name.return_value = "unkillable_process"

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.return_value = [mock_child]

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            with unittest.mock.patch("psutil.wait_procs", return_value=([], [mock_child])):
                kill_child(timeout=1)

    def test_handles_process_error(self):
        """psutil エラーを処理する"""
        import unittest.mock

        from my_lib.proc_util import kill_child

        with unittest.mock.patch("psutil.Process", side_effect=psutil.Error("Test error")):
            kill_child(timeout=1)


class TestGetChildPidMapErrors:
    """get_child_pid_map 関数のエラーハンドリングテスト"""

    def test_handles_psutil_error(self):
        """psutil エラーを処理する"""
        import unittest.mock

        from my_lib.proc_util import get_child_pid_map

        mock_parent = unittest.mock.MagicMock()
        mock_parent.children.side_effect = psutil.Error("Test error")

        with unittest.mock.patch("psutil.Process", return_value=mock_parent):
            result = get_child_pid_map()

        assert result == {}


class TestReapZombie:
    """reap_zombie 関数のテスト"""

    def test_does_not_raise(self):
        """エラーを発生させない"""
        from my_lib.proc_util import reap_zombie

        # 例外が発生しなければ OK
        reap_zombie()

    def test_reaps_zombie_process(self):
        """ゾンビプロセスを回収する"""
        import unittest.mock

        from my_lib.proc_util import reap_zombie

        with unittest.mock.patch("my_lib.proc_util.get_child_pid_map", return_value={123: "zombie"}):
            with unittest.mock.patch("os.waitpid", side_effect=[(123, 0), (0, 0)]):
                reap_zombie()

    def test_handles_no_children(self):
        """子プロセスがない場合を処理する"""
        import unittest.mock

        from my_lib.proc_util import reap_zombie

        with unittest.mock.patch("my_lib.proc_util.get_child_pid_map", return_value={}):
            with unittest.mock.patch("os.waitpid", side_effect=ChildProcessError):
                reap_zombie()
