# ruff: noqa: S101
"""browser_manager.py のテスト"""

from __future__ import annotations

import pathlib
import unittest.mock

import pytest

import my_lib.browser_manager
import my_lib.selenium_util


class TestBrowserManagerInit:
    """BrowserManager 初期化のテスト"""

    def test_creates_with_required_params(self, temp_dir: pathlib.Path):
        """必須パラメータのみで作成できる"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        assert manager.profile_name == "TestProfile"
        assert manager.data_dir == temp_dir
        assert manager.wait_timeout == 5.0
        assert manager.use_undetected is True
        assert manager.clear_profile_on_error is False

    def test_creates_with_all_params(self, temp_dir: pathlib.Path):
        """全パラメータを指定して作成できる"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="CustomProfile",
            data_dir=temp_dir,
            wait_timeout=10.0,
            use_undetected=False,
            clear_profile_on_error=True,
        )

        assert manager.profile_name == "CustomProfile"
        assert manager.wait_timeout == 10.0
        assert manager.use_undetected is False
        assert manager.clear_profile_on_error is True

    def test_driver_not_started_initially(self, temp_dir: pathlib.Path):
        """初期状態ではドライバーは起動していない"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        assert manager.has_driver() is False


class TestGetDriver:
    """get_driver メソッドのテスト"""

    def test_creates_driver_on_first_call(self, temp_dir: pathlib.Path):
        """初回呼び出し時にドライバーを作成する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver", return_value=mock_driver
            ) as mock_create,
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
        ):
            driver, wait = manager.get_driver()

            mock_create.assert_called_once_with(
                "TestProfile",
                temp_dir,
                use_undetected=True,
            )
            mock_clear.assert_called_once_with(mock_driver)
            assert driver is mock_driver
            assert wait is not None
            assert manager.has_driver() is True

    def test_returns_cached_driver_on_second_call(self, temp_dir: pathlib.Path):
        """2回目以降はキャッシュされたドライバーを返す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver", return_value=mock_driver
            ) as mock_create,
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            driver1, wait1 = manager.get_driver()
            driver2, wait2 = manager.get_driver()

            # create_driver は1回だけ呼ばれる
            mock_create.assert_called_once()
            assert driver1 is driver2
            assert wait1 is wait2

    def test_clears_profile_on_error_when_enabled(self, temp_dir: pathlib.Path):
        """clear_profile_on_error=True の場合、エラー時にプロファイルを削除する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
            clear_profile_on_error=True,
        )

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver",
                side_effect=Exception("Driver creation failed"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete_profile,
        ):
            with pytest.raises(my_lib.selenium_util.SeleniumError):
                manager.get_driver()

            mock_delete_profile.assert_called_once_with("TestProfile", temp_dir)

    def test_does_not_clear_profile_on_error_when_disabled(self, temp_dir: pathlib.Path):
        """clear_profile_on_error=False の場合、エラー時にプロファイルを削除しない"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
            clear_profile_on_error=False,
        )

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver",
                side_effect=Exception("Driver creation failed"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete_profile,
        ):
            with pytest.raises(my_lib.selenium_util.SeleniumError):
                manager.get_driver()

            mock_delete_profile.assert_not_called()

    def test_uses_custom_wait_timeout(self, temp_dir: pathlib.Path):
        """カスタムの wait_timeout を使用する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
            wait_timeout=15.0,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            _, wait = manager.get_driver()

            assert wait._timeout == 15.0  # type: ignore[union-attr]


class TestQuit:
    """quit メソッドのテスト"""

    def test_quits_driver_gracefully(self, temp_dir: pathlib.Path):
        """ドライバーをグレースフルに終了する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            manager.get_driver()

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            manager.quit()

            mock_quit.assert_called_once_with(mock_driver, wait_sec=5)
            assert manager.has_driver() is False

    def test_uses_custom_wait_sec(self, temp_dir: pathlib.Path):
        """カスタムの wait_sec を使用する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            manager.get_driver()

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            manager.quit(wait_sec=10)

            mock_quit.assert_called_once_with(mock_driver, wait_sec=10)

    def test_does_nothing_when_not_started(self, temp_dir: pathlib.Path):
        """ドライバー未起動時は何もしない"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            manager.quit()

            mock_quit.assert_not_called()


class TestClearCache:
    """clear_cache メソッドのテスト"""

    def test_clears_cache_when_driver_running(self, temp_dir: pathlib.Path):
        """ドライバー起動中はキャッシュをクリアする"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
        ):
            manager.get_driver()
            mock_clear.reset_mock()  # get_driver 内での呼び出しをリセット

            manager.clear_cache()

            mock_clear.assert_called_once_with(mock_driver)

    def test_does_nothing_when_not_started(self, temp_dir: pathlib.Path):
        """ドライバー未起動時は何もしない"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        with unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear:
            manager.clear_cache()

            mock_clear.assert_not_called()


class TestHasDriver:
    """has_driver メソッドのテスト"""

    def test_returns_false_initially(self, temp_dir: pathlib.Path):
        """初期状態では False を返す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        assert manager.has_driver() is False

    def test_returns_true_after_get_driver(self, temp_dir: pathlib.Path):
        """get_driver 後は True を返す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            manager.get_driver()

            assert manager.has_driver() is True

    def test_returns_false_after_quit(self, temp_dir: pathlib.Path):
        """quit 後は False を返す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            manager.get_driver()

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"):
            manager.quit()

            assert manager.has_driver() is False
