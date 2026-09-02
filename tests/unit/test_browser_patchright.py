#!/usr/bin/env python3
# ruff: noqa: S101
"""my_lib.browser.backends.patchright.browser のユニットテスト"""

import pathlib
import unittest.mock

import pytest

import my_lib.browser.backends.patchright.browser
from my_lib.browser.types import BrowserProfile


@pytest.fixture
def temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path


class TestLaunchProfileLockCleanup:
    """launch() の SingletonLock 掃除のテスト

    SIGKILL 等で残った SingletonLock があると Chrome が PROFILE_IN_USE
    （exit code 21）で停止し launch がタイムアウトするため、起動前に
    掃除されることを検証する。
    """

    def _make_profile(self, temp_dir: pathlib.Path) -> BrowserProfile:
        return BrowserProfile(name="TestProfile", data_dir=temp_dir)

    def test_launch_removes_stale_singleton_files(self, temp_dir: pathlib.Path):
        profile = self._make_profile(temp_dir)
        user_data_dir = temp_dir / "chrome" / "TestProfile"
        user_data_dir.mkdir(parents=True)
        # SIGKILL で残った状態を再現（SingletonLock は別ホストを指す symlink）
        (user_data_dir / "SingletonLock").symlink_to("old-host-12345")
        (user_data_dir / "SingletonSocket").symlink_to("nonexistent-socket")
        (user_data_dir / "SingletonCookie").symlink_to("1234567890")

        lock_states: dict[str, bool] = {}

        def fake_launch_persistent_context(**_kwargs):
            # launch_persistent_context 呼び出し時点で掃除済みであることを記録
            for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
                path = user_data_dir / name
                lock_states[name] = path.exists() or path.is_symlink()
            return unittest.mock.MagicMock()

        mock_playwright = unittest.mock.MagicMock()
        mock_playwright.chromium.launch_persistent_context.side_effect = fake_launch_persistent_context

        with unittest.mock.patch(
            "patchright.sync_api.sync_playwright",
            return_value=unittest.mock.MagicMock(start=lambda: mock_playwright),
        ):
            my_lib.browser.backends.patchright.browser.launch(profile)

        assert lock_states == {
            "SingletonLock": False,
            "SingletonSocket": False,
            "SingletonCookie": False,
        }

    def test_launch_without_profile_dir(self, temp_dir: pathlib.Path):
        """プロファイル未作成（初回起動）でも掃除処理がエラーにならない"""
        profile = self._make_profile(temp_dir)

        mock_playwright = unittest.mock.MagicMock()

        with unittest.mock.patch(
            "patchright.sync_api.sync_playwright",
            return_value=unittest.mock.MagicMock(start=lambda: mock_playwright),
        ):
            my_lib.browser.backends.patchright.browser.launch(profile)

        mock_playwright.chromium.launch_persistent_context.assert_called_once()
