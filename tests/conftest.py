#!/usr/bin/env python3
# ruff: noqa: S101
"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""
from __future__ import annotations

import logging
import pathlib
import sys
import tempfile
import unittest.mock

import pytest

# === オプショナル依存関係のモック ===
# smbus2 がインストールされていない場合はモックする（センサーテスト用）
if "smbus2" not in sys.modules:
    mock_smbus2 = unittest.mock.MagicMock()
    mock_smbus2.smbus2.I2C_M_RD = 0x0001
    sys.modules["smbus2"] = mock_smbus2

# === 定数 ===
CONFIG_FILE = pathlib.Path("tests/fixtures/config.example.yaml")
FIXTURES_DIR = pathlib.Path("tests/fixtures")
EVIDENCE_DIR = pathlib.Path("tests/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# === pytest コマンドラインオプション ===
def pytest_addoption(parser: pytest.Parser) -> None:
    """テスト用のコマンドラインオプションを追加"""
    parser.addoption("--run-web", action="store_true", default=False, help="run web access tests")
    parser.addoption("--run-mercari", action="store_true", default=False, help="run mercari tests")


def pytest_configure(config: pytest.Config) -> None:
    """カスタムマーカーを登録"""
    config.addinivalue_line("markers", "web: mark test as requiring web access")
    config.addinivalue_line("markers", "mercari: mark test as mercari test")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """マーカーに基づいてテストをスキップ"""
    if not config.getoption("--run-web"):
        skip_web = pytest.mark.skip(reason="need --run-web option to run")
        for item in items:
            if "web" in item.keywords:
                item.add_marker(skip_web)

    if not config.getoption("--run-mercari"):
        skip_mercari = pytest.mark.skip(reason="need --run-mercari option to run")
        for item in items:
            if "mercari" in item.keywords:
                item.add_marker(skip_mercari)


# === 環境モック ===
@pytest.fixture(scope="session", autouse=True)
def env_mock():
    """テスト環境用の環境変数モック"""
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    """Slack API のモック"""
    mock_response = unittest.mock.MagicMock()
    mock_response.get.return_value = "test_timestamp"

    with (
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
            return_value=mock_response,
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_upload_v2",
            return_value={"ok": True, "files": [{"id": "test_file_id"}]},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_getUploadURLExternal",
            return_value={"ok": True, "upload_url": "https://example.com"},
        ) as fixture,
    ):
        yield fixture


# === 設定フィクスチャ ===
@pytest.fixture
def config():
    """設定ファイルを読み込む"""
    import my_lib.config

    return my_lib.config.load(CONFIG_FILE)


@pytest.fixture
def slack_config(config):
    """Slack 設定を取得"""
    import my_lib.notify.slack

    return my_lib.notify.slack.parse_config(config["slack"])


@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield pathlib.Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir):
    """一時ファイルパスを提供"""
    return temp_dir / "test_file"


# === Slack 通知検証 ===
@pytest.fixture
def slack_checker():
    """Slack 通知検証ヘルパーを返す"""
    import my_lib.notify.slack

    class SlackChecker:
        def clear(self):
            my_lib.notify.slack._hist_clear()
            my_lib.notify.slack._interval_clear()

        def assert_notified(self, message: str, index: int = -1):
            notify_hist = my_lib.notify.slack._hist_get()
            assert len(notify_hist) != 0, "通知がされていません。"
            assert notify_hist[index].find(message) != -1, f"「{message}」が通知されていません。"

        def assert_not_notified(self):
            notify_hist = my_lib.notify.slack._hist_get()
            assert notify_hist == [], "通知がされています。"

        def get_history(self) -> list[str]:
            return my_lib.notify.slack._hist_get()

    return SlackChecker()


@pytest.fixture(autouse=True)
def clear_slack_state():
    """各テスト前に Slack 状態をクリア"""
    import my_lib.notify.slack

    my_lib.notify.slack._hist_clear()
    my_lib.notify.slack._interval_clear()
    yield
    my_lib.notify.slack._hist_clear()
    my_lib.notify.slack._interval_clear()


# === ロギング設定 ===
logging.getLogger("urllib3").setLevel(logging.WARNING)
