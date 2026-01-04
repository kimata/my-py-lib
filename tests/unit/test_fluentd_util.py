#!/usr/bin/env python3
# ruff: noqa: S101
"""fluentd_util.py のテスト"""

from __future__ import annotations

import sys
import unittest.mock

# fluent.sender がインストールされていない場合はモックする
if "fluent.sender" not in sys.modules:
    mock_fluent = unittest.mock.MagicMock()
    sys.modules["fluent"] = mock_fluent
    sys.modules["fluent.sender"] = mock_fluent.sender

import my_lib.fluentd_util


class TestGetHandle:
    """get_handle 関数のテスト"""

    def test_creates_fluent_sender(self):
        """FluentSender を作成する"""
        with unittest.mock.patch("fluent.sender.FluentSender") as mock_sender:
            mock_sender.return_value = unittest.mock.MagicMock()
            result = my_lib.fluentd_util.get_handle("test_tag", "localhost")

            mock_sender.assert_called_once_with("test_tag", "localhost")
            assert result is not None

    def test_passes_tag_and_host(self):
        """タグとホストを正しく渡す"""
        with unittest.mock.patch("fluent.sender.FluentSender") as mock_sender:
            my_lib.fluentd_util.get_handle("my_app", "192.168.1.100")

            mock_sender.assert_called_once_with("my_app", "192.168.1.100")


class TestSend:
    """send 関数のテスト"""

    def test_emits_data_successfully(self):
        """データを正常に送信する"""
        mock_handle = unittest.mock.MagicMock()
        mock_handle.emit.return_value = True

        result = my_lib.fluentd_util.send(mock_handle, "info", {"key": "value"})

        assert result is True
        mock_handle.emit.assert_called_once_with("info", {"key": "value"})

    def test_returns_false_on_failure(self):
        """送信失敗時に False を返す"""
        mock_handle = unittest.mock.MagicMock()
        mock_handle.emit.return_value = False
        mock_handle.last_error = "Connection refused"

        result = my_lib.fluentd_util.send(mock_handle, "error", {"msg": "test"})

        assert result is False

    def test_logs_error_on_failure(self, caplog):
        """送信失敗時にエラーをログに記録する"""
        mock_handle = unittest.mock.MagicMock()
        mock_handle.emit.return_value = False
        mock_handle.last_error = "Connection timeout"

        import logging

        with caplog.at_level(logging.ERROR):
            my_lib.fluentd_util.send(mock_handle, "test", {})

        assert "Connection timeout" in caplog.text

    def test_sends_complex_data(self):
        """複雑なデータ構造を送信できる"""
        mock_handle = unittest.mock.MagicMock()
        mock_handle.emit.return_value = True

        data = {
            "level": "info",
            "message": "test message",
            "nested": {"key1": "value1", "key2": 123},
            "list": [1, 2, 3],
        }

        result = my_lib.fluentd_util.send(mock_handle, "complex", data)

        assert result is True
        mock_handle.emit.assert_called_once_with("complex", data)
