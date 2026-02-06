# ruff: noqa: S101
"""browser_manager.py のテスト"""

from __future__ import annotations

import pathlib
import unittest.mock

import pytest

import my_lib.browser_manager
import my_lib.selenium_util


class TestBrowserProfile:
    """BrowserProfile のテスト"""

    def test_creates_with_required_params(self, temp_dir: pathlib.Path):
        """必須パラメータのみで作成できる"""
        profile = my_lib.browser_manager.BrowserProfile(
            name="TestProfile",
            data_dir=temp_dir,
        )

        assert profile.name == "TestProfile"
        assert profile.data_dir == temp_dir
        assert profile.wait_timeout == 5.0
        assert profile.use_undetected is True
        assert profile.stealth_mode is True
        assert profile.clear_profile_on_error is False
        assert profile.max_retry == 1

    def test_creates_with_all_params(self, temp_dir: pathlib.Path):
        """全パラメータを指定して作成できる"""
        profile = my_lib.browser_manager.BrowserProfile(
            name="CustomProfile",
            data_dir=temp_dir,
            wait_timeout=10.0,
            use_undetected=False,
            stealth_mode=False,
            clear_profile_on_error=True,
            max_retry=3,
        )

        assert profile.name == "CustomProfile"
        assert profile.wait_timeout == 10.0
        assert profile.use_undetected is False
        assert profile.stealth_mode is False
        assert profile.clear_profile_on_error is True
        assert profile.max_retry == 3


class TestBrowserManagerFromProfile:
    """BrowserManager.from_profile のテスト"""

    def test_creates_from_profile(self, temp_dir: pathlib.Path):
        """BrowserProfile から BrowserManager を作成できる"""
        profile = my_lib.browser_manager.BrowserProfile(
            name="ProfileTest",
            data_dir=temp_dir,
            wait_timeout=15.0,
            use_undetected=False,
            stealth_mode=False,
            clear_profile_on_error=True,
            max_retry=5,
        )

        manager = my_lib.browser_manager.BrowserManager.from_profile(profile)

        assert manager.profile_name == "ProfileTest"
        assert manager.data_dir == temp_dir
        assert manager.wait_timeout == 15.0
        assert manager.use_undetected is False
        assert manager.stealth_mode is False
        assert manager.clear_profile_on_error is True
        assert manager.max_retry_on_error == 5
        assert manager.has_driver() is False


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
                stealth_mode=True,
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
            max_retry_on_error=0,
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

            assert wait._timeout == 15.0


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


class TestContextManager:
    """context manager のテスト"""

    def test_context_manager_quits_on_exit(self, temp_dir: pathlib.Path):
        """context manager 終了時に quit が呼ばれる"""
        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit,
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock") as mock_cleanup,
        ):
            with my_lib.browser_manager.BrowserManager(
                profile_name="TestProfile",
                data_dir=temp_dir,
            ) as manager:
                manager.get_driver()
                assert manager.has_driver() is True

            mock_quit.assert_called_once()
            # quit() 内で cleanup_profile_lock が呼ばれる
            mock_cleanup.assert_called_with("TestProfile", temp_dir)

    def test_context_manager_returns_self(self, temp_dir: pathlib.Path):
        """context manager は self を返す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        with (
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock"),
            manager as ctx,
        ):
            assert ctx is manager

    def test_context_manager_quits_on_exception(self, temp_dir: pathlib.Path):
        """例外発生時も quit が呼ばれる"""
        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit,
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock") as mock_cleanup,
        ):
            with (
                pytest.raises(ValueError, match="test error"),
                my_lib.browser_manager.BrowserManager(
                    profile_name="TestProfile",
                    data_dir=temp_dir,
                ) as manager,
            ):
                manager.get_driver()
                raise ValueError("test error")

            mock_quit.assert_called_once()
            # quit() 内で cleanup_profile_lock が呼ばれる
            mock_cleanup.assert_called()


class TestDriverContextManager:
    """driver() コンテキストマネージャのテスト"""

    def test_driver_context_yields_driver(self, temp_dir: pathlib.Path):
        """driver() はドライバーを yield する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
            manager.driver() as driver,
        ):
            assert driver is mock_driver

    def test_driver_context_clears_cache_on_exit(self, temp_dir: pathlib.Path):
        """driver() 終了時にキャッシュをクリアする"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
        ):
            with manager.driver():
                mock_clear.reset_mock()  # get_driver 内での呼び出しをリセット

            mock_clear.assert_called_once_with(mock_driver)

    def test_driver_context_does_not_quit(self, temp_dir: pathlib.Path):
        """driver() は終了時に quit しない（複数回使用可能）"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit,
        ):
            with manager.driver():
                pass

            mock_quit.assert_not_called()
            assert manager.has_driver() is True


class TestCleanupProfileLock:
    """cleanup_profile_lock メソッドのテスト"""

    def test_calls_chrome_util(self, temp_dir: pathlib.Path):
        """chrome_util.cleanup_profile_lock を呼び出す"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        with unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock") as mock_cleanup:
            manager.cleanup_profile_lock()

            mock_cleanup.assert_called_once_with("TestProfile", temp_dir)


class TestRestartWithCleanProfile:
    """restart_with_clean_profile メソッドのテスト"""

    def test_quits_deletes_and_restarts(self, temp_dir: pathlib.Path):
        """quit → delete_profile → get_driver の順で呼ばれる"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()
        call_order = []

        def track_quit(*args, **kwargs):
            call_order.append("quit")

        def track_delete(*args, **kwargs):
            call_order.append("delete")

        def track_create(*args, **kwargs):
            call_order.append("create")
            return mock_driver

        with (
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully", side_effect=track_quit),
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock"),
            unittest.mock.patch("my_lib.chrome_util.delete_profile", side_effect=track_delete) as mock_delete,
            unittest.mock.patch("my_lib.selenium_util.create_driver", side_effect=track_create),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            # 最初にドライバを作成
            manager.get_driver()
            call_order.clear()

            # restart を呼ぶ
            driver, wait = manager.restart_with_clean_profile()

            # quit → delete → create の順で呼ばれる
            assert call_order == ["quit", "delete", "create"]
            assert driver is mock_driver
            mock_delete.assert_called_once_with("TestProfile", temp_dir)

    def test_works_without_existing_driver(self, temp_dir: pathlib.Path):
        """ドライバー未起動でも動作する"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit,
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock"),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            # ドライバー未起動の状態で restart
            driver, wait = manager.restart_with_clean_profile()

            # quit は呼ばれない（未起動のため）
            mock_quit.assert_not_called()
            # delete_profile は呼ばれる
            mock_delete.assert_called_once_with("TestProfile", temp_dir)
            assert driver is mock_driver

    def test_resets_driver_state(self, temp_dir: pathlib.Path):
        """ドライバー状態がリセットされる"""
        manager = my_lib.browser_manager.BrowserManager(
            profile_name="TestProfile",
            data_dir=temp_dir,
        )

        mock_driver_1 = unittest.mock.MagicMock()
        mock_driver_2 = unittest.mock.MagicMock()
        drivers = iter([mock_driver_1, mock_driver_2])

        with (
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
            unittest.mock.patch("my_lib.chrome_util.cleanup_profile_lock"),
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver", side_effect=lambda *a, **kw: next(drivers)
            ),
            unittest.mock.patch("my_lib.selenium_util.clear_cache"),
        ):
            # 最初のドライバを作成
            driver1, _ = manager.get_driver()
            assert driver1 is mock_driver_1

            # restart で新しいドライバを取得
            driver2, _ = manager.restart_with_clean_profile()
            assert driver2 is mock_driver_2
            assert driver2 is not driver1
