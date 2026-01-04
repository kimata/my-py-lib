#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.notify.slack モジュールのユニットテスト
"""

from __future__ import annotations


class TestSlackChannelConfig:
    """SlackChannelConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackChannelConfig

        config = SlackChannelConfig(name="general", id="C123456")

        assert config.name == "general"
        assert config.id == "C123456"

    def test_id_is_optional(self):
        """id はオプション"""
        from my_lib.notify.slack import SlackChannelConfig

        config = SlackChannelConfig(name="general")
        assert config.id is None


class TestSlackInfoConfig:
    """SlackInfoConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackChannelConfig, SlackInfoConfig

        channel = SlackChannelConfig(name="info")
        config = SlackInfoConfig(channel=channel)

        assert config.channel.name == "info"


class TestSlackCaptchaConfig:
    """SlackCaptchaConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackCaptchaConfig, SlackChannelConfig

        channel = SlackChannelConfig(name="captcha")
        config = SlackCaptchaConfig(channel=channel)

        assert config.channel.name == "captcha"


class TestSlackErrorConfig:
    """SlackErrorConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackChannelConfig, SlackErrorConfig

        channel = SlackChannelConfig(name="error", id="C123")
        config = SlackErrorConfig(channel=channel, interval_min=60)

        assert config.channel.name == "error"
        assert config.interval_min == 60


class TestSlackEmptyConfig:
    """SlackEmptyConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackEmptyConfig

        config = SlackEmptyConfig()
        assert config is not None


class TestSlackErrorOnlyConfig:
    """SlackErrorOnlyConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackChannelConfig, SlackErrorConfig, SlackErrorOnlyConfig

        error_channel = SlackChannelConfig(name="error", id="C123")
        error_config = SlackErrorConfig(channel=error_channel, interval_min=60)

        config = SlackErrorOnlyConfig(
            bot_token="xoxb-token",  # noqa: S106
            from_name="bot",
            error=error_config,
        )

        assert config.bot_token == "xoxb-token"  # noqa: S105
        assert config.from_name == "bot"
        assert config.error.interval_min == 60


class TestSlackConfig:
    """SlackConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import (
            SlackCaptchaConfig,
            SlackChannelConfig,
            SlackConfig,
            SlackErrorConfig,
            SlackInfoConfig,
        )

        info_channel = SlackChannelConfig(name="info")
        captcha_channel = SlackChannelConfig(name="captcha")
        error_channel = SlackChannelConfig(name="error", id="C123")

        config = SlackConfig(
            bot_token="xoxb-token",  # noqa: S106
            from_name="bot",
            info=SlackInfoConfig(channel=info_channel),
            captcha=SlackCaptchaConfig(channel=captcha_channel),
            error=SlackErrorConfig(channel=error_channel, interval_min=60),
        )

        assert config.bot_token == "xoxb-token"  # noqa: S105


class TestFormatSimple:
    """format_simple 関数のテスト"""

    def test_returns_formatted_message(self):
        """フォーマットされたメッセージを返す"""
        from my_lib.notify.slack import format_simple

        result = format_simple("Test Title", "Test message")

        assert result["text"] == "Test message"
        assert isinstance(result["json"], list)
        assert len(result["json"]) > 0


class TestParseConfig:
    """parse_config 関数のテスト"""

    def test_returns_empty_config_for_empty_data(self):
        """空のデータは SlackEmptyConfig を返す"""
        from my_lib.notify.slack import SlackEmptyConfig, parse_config

        result = parse_config({})
        assert isinstance(result, SlackEmptyConfig)

    def test_returns_empty_config_without_bot_token(self):
        """bot_token がない場合は SlackEmptyConfig を返す"""
        from my_lib.notify.slack import SlackEmptyConfig, parse_config

        result = parse_config({"from": "bot"})
        assert isinstance(result, SlackEmptyConfig)

    def test_returns_empty_config_without_error_or_captcha(self):
        """error も captcha もない場合は SlackEmptyConfig を返す"""
        from my_lib.notify.slack import SlackEmptyConfig, parse_config

        result = parse_config({"bot_token": "token", "from": "bot"})
        assert isinstance(result, SlackEmptyConfig)

    def test_parses_error_only_config(self):
        """error のみの設定をパースする"""
        from my_lib.notify.slack import SlackErrorOnlyConfig, parse_config

        data = {
            "bot_token": "xoxb-token",
            "from": "bot",
            "error": {
                "channel": {"name": "error", "id": "C123"},
                "interval_min": 60,
            },
        }

        result = parse_config(data)
        assert isinstance(result, SlackErrorOnlyConfig)
        assert result.error.interval_min == 60

    def test_parses_error_info_config(self):
        """error + info の設定をパースする"""
        from my_lib.notify.slack import SlackErrorInfoConfig, parse_config

        data = {
            "bot_token": "xoxb-token",
            "from": "bot",
            "info": {"channel": {"name": "info"}},
            "error": {
                "channel": {"name": "error", "id": "C123"},
                "interval_min": 60,
            },
        }

        result = parse_config(data)
        assert isinstance(result, SlackErrorInfoConfig)

    def test_parses_captcha_only_config(self):
        """captcha のみの設定をパースする"""
        from my_lib.notify.slack import SlackCaptchaOnlyConfig, parse_config

        data = {
            "bot_token": "xoxb-token",
            "from": "bot",
            "captcha": {"channel": {"name": "captcha"}},
        }

        result = parse_config(data)
        assert isinstance(result, SlackCaptchaOnlyConfig)

    def test_parses_full_config(self):
        """全ての設定をパースする"""
        from my_lib.notify.slack import SlackConfig, parse_config

        data = {
            "bot_token": "xoxb-token",
            "from": "bot",
            "info": {"channel": {"name": "info"}},
            "captcha": {"channel": {"name": "captcha"}},
            "error": {
                "channel": {"name": "error", "id": "C123"},
                "interval_min": 60,
            },
        }

        result = parse_config(data)
        assert isinstance(result, SlackConfig)


class TestInfo:
    """info 関数のテスト"""

    def test_does_nothing_for_empty_config(self):
        """SlackEmptyConfig では何もしない"""
        from my_lib.notify.slack import SlackEmptyConfig, info

        config = SlackEmptyConfig()
        # 例外が発生しなければ OK
        info(config, "title", "message")


class TestError:
    """error 関数のテスト"""

    def test_does_nothing_for_empty_config(self):
        """SlackEmptyConfig では何もしない"""
        from my_lib.notify.slack import SlackEmptyConfig, error

        config = SlackEmptyConfig()
        # 例外が発生しなければ OK
        error(config, "title", "message")

    def test_adds_to_history(self, temp_dir):
        """履歴に追加する"""
        from my_lib.notify.slack import (
            SlackChannelConfig,
            SlackErrorConfig,
            SlackErrorOnlyConfig,
            _hist_clear,
            _hist_get,
            _interval_clear,
            error,
        )

        _hist_clear()
        _interval_clear()

        error_channel = SlackChannelConfig(name="error", id="C123")
        error_config = SlackErrorConfig(channel=error_channel, interval_min=0)
        config = SlackErrorOnlyConfig(
            bot_token="dummy-token",  # noqa: S106
            from_name="test",
            error=error_config,
        )

        error(config, "test", "test message")

        hist = _hist_get()
        assert "test message" in hist


class TestSend:
    """send 関数のテスト"""

    def test_does_nothing_for_empty_config(self):
        """SlackEmptyConfig では None を返す"""
        from my_lib.notify.slack import SlackEmptyConfig, format_simple, send

        config = SlackEmptyConfig()
        result = send(config, "channel", format_simple("title", "message"))
        assert result is None


class TestUploadImage:
    """upload_image 関数のテスト"""

    def test_does_nothing_for_empty_config(self):
        """SlackEmptyConfig では None を返す"""
        import PIL.Image

        from my_lib.notify.slack import SlackEmptyConfig, upload_image

        config = SlackEmptyConfig()
        img = PIL.Image.new("RGB", (100, 100))
        result = upload_image(config, "C123", "title", img, "text")
        assert result is None


class TestHistoryFunctions:
    """履歴関数のテスト"""

    def test_hist_clear(self):
        """履歴をクリアする"""
        from my_lib.notify.slack import _hist_add, _hist_clear, _hist_get

        _hist_add("test message")
        _hist_clear()

        assert _hist_get() == []

    def test_hist_add(self):
        """履歴を追加する"""
        from my_lib.notify.slack import _hist_add, _hist_clear, _hist_get

        _hist_clear()
        _hist_add("message1")
        _hist_add("message2")

        hist = _hist_get()
        assert "message1" in hist
        assert "message2" in hist

    def test_hist_get_thread_local(self):
        """スレッドローカルの履歴を取得する"""
        from my_lib.notify.slack import _hist_clear, _hist_get

        _hist_clear()
        hist = _hist_get(is_thread_local=True)
        assert isinstance(hist, list)

    def test_hist_get_global(self):
        """グローバルの履歴を取得する"""
        from my_lib.notify.slack import _hist_clear, _hist_get

        _hist_clear()
        hist = _hist_get(is_thread_local=False)
        assert isinstance(hist, list)


class TestIntervalClear:
    """_interval_clear 関数のテスト"""

    def test_clears_footprint(self):
        """フットプリントをクリアする"""
        from my_lib.notify.slack import _interval_clear

        # 例外が発生しなければ OK
        _interval_clear()
