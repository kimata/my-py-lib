#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.notify.mail モジュールのユニットテスト
"""

from __future__ import annotations


class TestMailSmtpConfig:
    """MailSmtpConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.mail import MailSmtpConfig

        config = MailSmtpConfig(
            host="smtp.example.com",
            port=587,
            user="user@example.com",
            password="password",  # noqa: S106
        )

        assert config.host == "smtp.example.com"
        assert config.port == 587
        assert config.user == "user@example.com"
        assert config.password == "password"  # noqa: S105


class TestMailEmptyConfig:
    """MailEmptyConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.mail import MailEmptyConfig

        config = MailEmptyConfig()
        assert config is not None


class TestMailConfig:
    """MailConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.mail import MailConfig, MailSmtpConfig

        smtp = MailSmtpConfig(
            host="smtp.example.com",
            port=587,
            user="user",
            password="pass",  # noqa: S106
        )

        config = MailConfig(
            smtp=smtp,
            from_address="from@example.com",
            to="to@example.com",
        )

        assert config.smtp.host == "smtp.example.com"
        assert config.from_address == "from@example.com"
        assert config.to == "to@example.com"


class TestImageAttachmentFromPath:
    """ImageAttachmentFromPath データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.mail import ImageAttachmentFromPath

        attachment = ImageAttachmentFromPath(id="img1", path="/path/to/image.png")

        assert attachment.id == "img1"
        assert attachment.path == "/path/to/image.png"


class TestImageAttachmentFromData:
    """ImageAttachmentFromData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.mail import ImageAttachmentFromData

        attachment = ImageAttachmentFromData(id="img1", data=b"binary data")

        assert attachment.id == "img1"
        assert attachment.data == b"binary data"


class TestParseConfig:
    """parse_config 関数のテスト"""

    def test_returns_empty_config_for_empty_data(self):
        """空のデータは MailEmptyConfig を返す"""
        from my_lib.notify.mail import MailEmptyConfig, parse_config

        result = parse_config({})
        assert isinstance(result, MailEmptyConfig)

    def test_returns_empty_config_without_smtp(self):
        """smtp がない場合は MailEmptyConfig を返す"""
        from my_lib.notify.mail import MailEmptyConfig, parse_config

        result = parse_config({"from": "from@example.com"})
        assert isinstance(result, MailEmptyConfig)

    def test_parses_valid_config(self):
        """有効な設定をパースする"""
        from my_lib.notify.mail import MailConfig, parse_config

        data = {
            "smtp": {
                "host": "smtp.example.com",
                "port": 587,
            },
            "user": "user@example.com",
            "pass": "password",
            "from": "from@example.com",
            "to": "to@example.com",
        }

        result = parse_config(data)

        assert isinstance(result, MailConfig)
        assert result.smtp.host == "smtp.example.com"
        assert result.smtp.port == 587
        assert result.smtp.user == "user@example.com"
        assert result.smtp.password == "password"  # noqa: S105
        assert result.from_address == "from@example.com"
        assert result.to == "to@example.com"


class TestSend:
    """send 関数のテスト"""

    def test_does_nothing_for_empty_config(self):
        """MailEmptyConfig では何もしない"""
        from my_lib.notify.mail import MailEmptyConfig, send

        config = MailEmptyConfig()
        # 例外が発生しなければ OK
        send(config, "test message")

    def test_handles_exception_gracefully(self, mocker):
        """例外を適切に処理する"""
        from my_lib.notify.mail import MailConfig, MailSmtpConfig, send

        # SMTP 接続をモック
        mock_smtp = mocker.patch("smtplib.SMTP")
        mock_smtp.side_effect = Exception("Connection failed")

        smtp = MailSmtpConfig(
            host="smtp.example.com",
            port=587,
            user="user",
            password="pass",  # noqa: S106
        )
        config = MailConfig(
            smtp=smtp,
            from_address="from@example.com",
            to="to@example.com",
        )

        # 例外が発生しないことを確認
        send(config, "test message")


class TestBuildMessage:
    """build_message 関数のテスト"""

    def test_builds_simple_message(self):
        """シンプルなメッセージを構築する"""
        from my_lib.notify.mail import build_message

        result = build_message("Test Subject", "<p>Test message</p>")

        assert "Subject: Test Subject" in result
        assert "Test message" in result

    def test_builds_message_with_path_image(self, temp_dir):
        """パス指定の画像付きメッセージを構築する"""
        from my_lib.notify.mail import ImageAttachmentFromPath, build_message

        # テスト用画像ファイルを作成
        img_path = temp_dir / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG ヘッダー

        image = ImageAttachmentFromPath(id="test_img", path=str(img_path))
        result = build_message("Test Subject", "<p>Test</p>", image)

        assert "Subject: Test Subject" in result
        assert "Content-ID: <test_img>" in result

    def test_builds_message_with_data_image(self):
        """データ指定の画像付きメッセージを構築する"""
        from my_lib.notify.mail import ImageAttachmentFromData, build_message

        image = ImageAttachmentFromData(id="test_img", data=b"\x89PNG\r\n\x1a\n")
        result = build_message("Test Subject", "<p>Test</p>", image)

        assert "Subject: Test Subject" in result
        assert "Content-ID: <test_img>" in result
