#!/usr/bin/env python3
# ruff: noqa: S101, S106
"""
my_lib.notify.line モジュールのユニットテスト
"""

from __future__ import annotations


class TestHistoryFunctions:
    """履歴関数のテスト"""

    def test_hist_clear(self):
        """履歴をクリアする"""
        from my_lib.notify.line import hist_add, hist_clear, hist_get

        hist_add("test message")
        hist_clear()

        assert hist_get() == []

    def test_hist_add(self):
        """履歴を追加する"""
        from my_lib.notify.line import hist_add, hist_clear, hist_get

        hist_clear()
        hist_add("message1")
        hist_add("message2")

        hist = hist_get()
        assert "message1" in hist
        assert "message2" in hist

    def test_hist_get_returns_list(self):
        """リストを返す"""
        from my_lib.notify.line import hist_clear, hist_get

        hist_clear()
        result = hist_get()
        assert isinstance(result, list)


class TestGetMsgConfig:
    """get_msg_config 関数のテスト"""

    def test_returns_configuration(self):
        """Configuration オブジェクトを返す"""
        import linebot.v3.messaging

        from my_lib.notify.line import LineChannelConfig, LineConfig, get_msg_config

        line_config = LineConfig(channel=LineChannelConfig(access_token="test-token"))

        result = get_msg_config(line_config)

        assert isinstance(result, linebot.v3.messaging.Configuration)


class TestSendImpl:
    """_send_impl 関数のテスト"""

    def test_adds_to_history(self, mocker):
        """履歴に追加する"""
        import linebot.v3.messaging

        from my_lib.notify.line import LineChannelConfig, LineConfig, _send_impl, hist_clear, hist_get

        hist_clear()

        # ApiClient をモック
        mock_client = mocker.MagicMock()
        mock_api = mocker.MagicMock()
        mocker.patch("linebot.v3.messaging.ApiClient", return_value=mock_client)
        mocker.patch("linebot.v3.messaging.MessagingApi", return_value=mock_api)
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)

        line_config = LineConfig(channel=LineChannelConfig(access_token="test-token"))
        message = linebot.v3.messaging.FlexMessage.from_dict(
            {
                "type": "flex",
                "altText": "test alt text",
                "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": []}},
            }
        )

        _send_impl(line_config, message)

        hist = hist_get()
        assert "test alt text" in hist


class TestSend:
    """send 関数のテスト"""

    def test_calls__send_impl(self, mocker):
        """_send_impl を呼び出す"""
        from my_lib.notify.line import LineChannelConfig, LineConfig, hist_clear, send

        hist_clear()

        # _send_impl をモック
        mock__send_impl = mocker.patch("my_lib.notify.line._send_impl")

        line_config = LineConfig(channel=LineChannelConfig(access_token="test-token"))
        message = {
            "type": "template",
            "altText": "test",
            "template": {
                "type": "buttons",
                "text": "test message",
                "actions": [{"type": "message", "label": "Test", "text": "test"}],
            },
        }

        send(line_config, message)

        assert mock__send_impl.called


class TestError:
    """error 関数のテスト"""

    def test_adds_to_history(self, mocker):
        """履歴に追加する"""
        from my_lib.notify.line import LineChannelConfig, LineConfig, error, hist_clear, hist_get

        hist_clear()

        # ApiClient をモック
        mock_client = mocker.MagicMock()
        mock_api = mocker.MagicMock()
        mocker.patch("linebot.v3.messaging.ApiClient", return_value=mock_client)
        mocker.patch("linebot.v3.messaging.MessagingApi", return_value=mock_api)
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)

        line_config = LineConfig(channel=LineChannelConfig(access_token="test-token"))
        error(line_config, "Error occurred")

        hist = hist_get()
        assert any("ERROR" in h for h in hist)


class TestInfo:
    """info 関数のテスト"""

    def test_adds_to_history(self, mocker):
        """履歴に追加する"""
        from my_lib.notify.line import LineChannelConfig, LineConfig, hist_clear, hist_get, info

        hist_clear()

        # ApiClient をモック
        mock_client = mocker.MagicMock()
        mock_api = mocker.MagicMock()
        mocker.patch("linebot.v3.messaging.ApiClient", return_value=mock_client)
        mocker.patch("linebot.v3.messaging.MessagingApi", return_value=mock_api)
        mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
        mock_client.__exit__ = mocker.MagicMock(return_value=False)

        line_config = LineConfig(channel=LineChannelConfig(access_token="test-token"))
        info(line_config, "Information message")

        hist = hist_get()
        assert any("INFO" in h for h in hist)
