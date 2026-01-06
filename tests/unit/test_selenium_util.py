# ruff: noqa: S101
"""selenium_util.py のテスト"""

from __future__ import annotations

import time
import unittest.mock

import pytest

import my_lib.selenium_util


class TestGetChromeVersion:
    """_get_chrome_version 関数のテスト"""

    def test_returns_version_number(self):
        """バージョン番号を返す"""
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = "Google Chrome 120.0.6099.109"

        with unittest.mock.patch("subprocess.run", return_value=mock_result):
            result = my_lib.selenium_util._get_chrome_version()

            assert result == 120

    def test_returns_none_on_error(self):
        """エラー時は None を返す"""
        with unittest.mock.patch("subprocess.run", side_effect=Exception("Not found")):
            result = my_lib.selenium_util._get_chrome_version()

            assert result is None

    def test_returns_none_for_invalid_output(self):
        """無効な出力では None を返す"""
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = "Invalid output"

        with unittest.mock.patch("subprocess.run", return_value=mock_result):
            result = my_lib.selenium_util._get_chrome_version()

            assert result is None


class TestRandomSleep:
    """random_sleep 関数のテスト"""

    def test_sleeps_for_some_time(self):
        """一定時間スリープする"""
        with unittest.mock.patch("time.sleep") as mock_sleep:
            my_lib.selenium_util.random_sleep(1.0)

            mock_sleep.assert_called_once()
            # RATIO=0.8 なので、0.8 〜 1.2 の範囲
            sleep_time = mock_sleep.call_args[0][0]
            assert 0.8 <= sleep_time <= 1.2


class TestCleanDump:
    """clean_dump 関数のテスト"""

    def test_does_nothing_when_path_not_exists(self, temp_dir):
        """パスが存在しない場合は何もしない"""
        dump_path = temp_dir / "nonexistent"

        my_lib.selenium_util.clean_dump(dump_path)

    def test_removes_old_files(self, temp_dir):
        """古いファイルを削除する"""
        import os

        dump_path = temp_dir / "dump"
        dump_path.mkdir()

        old_file = dump_path / "old.png"
        old_file.touch()

        # 2日前の時刻を設定
        old_time = time.time() - (2 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))

        my_lib.selenium_util.clean_dump(dump_path, keep_days=1)

        assert not old_file.exists()

    def test_keeps_recent_files(self, temp_dir):
        """新しいファイルは保持する"""
        dump_path = temp_dir / "dump"
        dump_path.mkdir()

        new_file = dump_path / "new.png"
        new_file.touch()

        my_lib.selenium_util.clean_dump(dump_path, keep_days=1)

        assert new_file.exists()

    def test_skips_directories(self, temp_dir):
        """ディレクトリはスキップする"""
        dump_path = temp_dir / "dump"
        dump_path.mkdir()

        sub_dir = dump_path / "subdir"
        sub_dir.mkdir()

        my_lib.selenium_util.clean_dump(dump_path)

        assert sub_dir.exists()


class TestIsChromeRelatedProcess:
    """_is_chrome_related_process 関数のテスト"""

    def test_returns_true_for_chrome(self):
        """Chrome プロセスで True を返す"""
        mock_process = unittest.mock.MagicMock()
        mock_process.name.return_value = "chrome"

        result = my_lib.selenium_util._is_chrome_related_process(mock_process)

        assert result is True

    def test_returns_true_for_chromium(self):
        """Chromium プロセスで True を返す"""
        mock_process = unittest.mock.MagicMock()
        mock_process.name.return_value = "chromium-browser"

        result = my_lib.selenium_util._is_chrome_related_process(mock_process)

        assert result is True

    def test_returns_false_for_chromedriver(self):
        """Chromedriver プロセスで False を返す"""
        mock_process = unittest.mock.MagicMock()
        mock_process.name.return_value = "chromedriver"

        result = my_lib.selenium_util._is_chrome_related_process(mock_process)

        assert result is False

    def test_returns_false_for_unrelated(self):
        """無関係なプロセスで False を返す"""
        mock_process = unittest.mock.MagicMock()
        mock_process.name.return_value = "python"

        result = my_lib.selenium_util._is_chrome_related_process(mock_process)

        assert result is False

    def test_handles_nosuchprocess(self):
        """NoSuchProcess を処理する"""
        import psutil

        mock_process = unittest.mock.MagicMock()
        mock_process.name.side_effect = psutil.NoSuchProcess(1234)

        result = my_lib.selenium_util._is_chrome_related_process(mock_process)

        assert result is False


class TestBrowserTab:
    """browser_tab クラスのテスト"""

    def test_opens_and_closes_tab(self):
        """タブを開いて閉じる"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.current_window_handle = "original"

        # window_handles を動的に更新するモック
        # close() が呼ばれたらリストから1つ減らす
        window_handles = ["original", "new"]

        def close_side_effect():
            if len(window_handles) > 1:
                window_handles.pop()

        type(mock_driver).window_handles = unittest.mock.PropertyMock(side_effect=lambda: window_handles)
        mock_driver.close.side_effect = close_side_effect

        with my_lib.selenium_util.browser_tab(mock_driver, "http://example.com"):
            mock_driver.execute_script.assert_called_with("window.open('');")
            mock_driver.switch_to.window.assert_called()
            mock_driver.get.assert_called_with("http://example.com")

        mock_driver.close.assert_called_once()

    def test_handles_exception_on_close(self):
        """Close でエラーが発生しても例外を発生させない"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.current_window_handle = "original"

        # close() で例外が発生した場合でも window_handles は減らす必要がある
        # ただし実際のコードでは例外後にループを抜けるので、1回だけのアクセスでOK
        window_handles = ["original", "new"]

        def close_side_effect():
            window_handles.pop()
            raise Exception("Browser crashed")

        type(mock_driver).window_handles = unittest.mock.PropertyMock(side_effect=lambda: window_handles)
        mock_driver.close.side_effect = close_side_effect

        with my_lib.selenium_util.browser_tab(mock_driver, "http://example.com"):
            pass

        # 例外が発生しないことを確認


class TestErrorHandler:
    """error_handler クラスのテスト"""

    def test_no_error_case(self):
        """エラーがない場合"""
        mock_driver = unittest.mock.MagicMock()

        with my_lib.selenium_util.error_handler(mock_driver) as handler:
            pass

        assert handler.exception is None
        assert handler.screenshot is None

    def test_captures_exception(self):
        """例外をキャプチャする"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b""

        captured_handler = None
        with (
            pytest.raises(ValueError, match="Test error"),
            my_lib.selenium_util.error_handler(mock_driver) as handler,
        ):
            captured_handler = handler
            raise ValueError("Test error")

        assert captured_handler is not None
        assert captured_handler.exception is not None
        assert isinstance(captured_handler.exception, ValueError)

    def test_suppresses_exception_when_reraise_false(self):
        """reraise=False で例外を抑制する"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b""

        with my_lib.selenium_util.error_handler(mock_driver, reraise=False) as handler:
            raise ValueError("Test error")

        assert handler.exception is not None

    def test_calls_on_error_callback(self):
        """on_error コールバックを呼び出す"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b""

        callback_called = []

        def on_error(exc, screenshot, page_source):
            callback_called.append((exc, screenshot, page_source))

        with (
            pytest.raises(ValueError, match="Test error"),
            my_lib.selenium_util.error_handler(mock_driver, on_error=on_error),
        ):
            raise ValueError("Test error")

        assert len(callback_called) == 1
        assert isinstance(callback_called[0][0], ValueError)

    def test_skips_screenshot_when_disabled(self):
        """capture_screenshot=False でスクリーンショットをスキップする"""
        mock_driver = unittest.mock.MagicMock()

        captured_handler = None
        with (
            pytest.raises(ValueError, match="Test error"),
            my_lib.selenium_util.error_handler(mock_driver, capture_screenshot=False) as handler,
        ):
            captured_handler = handler
            raise ValueError("Test error")

        mock_driver.get_screenshot_as_png.assert_not_called()
        assert captured_handler is not None
        assert captured_handler.screenshot is None


class TestQuitDriverGracefully:
    """quit_driver_gracefully 関数のテスト"""

    def test_handles_none_driver(self):
        """None ドライバを処理する"""
        my_lib.selenium_util.quit_driver_gracefully(None)

    def test_calls_driver_quit(self):
        """driver.quit を呼び出す"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.service = None

        with (
            unittest.mock.patch.object(
                my_lib.selenium_util, "_get_chrome_related_processes", return_value=[]
            ),
            unittest.mock.patch.object(
                my_lib.selenium_util, "_wait_for_processes_with_check", return_value=[]
            ),
        ):
            my_lib.selenium_util.quit_driver_gracefully(mock_driver, wait_sec=0.1)

        mock_driver.quit.assert_called_once()

    def test_handles_quit_exception(self):
        """Quit 例外を処理する"""
        mock_driver = unittest.mock.MagicMock()
        mock_driver.quit.side_effect = Exception("Quit failed")
        mock_driver.service = None

        with (
            unittest.mock.patch.object(
                my_lib.selenium_util, "_get_chrome_related_processes", return_value=[]
            ),
            unittest.mock.patch.object(
                my_lib.selenium_util, "_wait_for_processes_with_check", return_value=[]
            ),
        ):
            # 例外が発生しないことを確認
            my_lib.selenium_util.quit_driver_gracefully(mock_driver, wait_sec=0.1)


class TestWithSessionRetry:
    """with_session_retry 関数のテスト"""

    def test_success_without_retry(self, temp_dir):
        """正常終了（リトライなし）"""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = my_lib.selenium_util.with_session_retry(
            func,
            driver_name="TestDriver",
            data_dir=temp_dir,
        )

        assert result == "success"
        assert call_count == 1

    def test_retry_on_invalid_session(self, temp_dir):
        """InvalidSessionIdException でリトライ"""
        import selenium.common.exceptions

        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("Session expired")
            return "success"

        with unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete:
            result = my_lib.selenium_util.with_session_retry(
                func,
                driver_name="TestDriver",
                data_dir=temp_dir,
                max_retries=1,
            )

        assert result == "success"
        assert call_count == 2
        mock_delete.assert_called_once_with("TestDriver", temp_dir)

    def test_raises_after_max_retries(self, temp_dir):
        """最大リトライ回数超過で例外"""
        import selenium.common.exceptions

        def func():
            raise selenium.common.exceptions.InvalidSessionIdException("Session expired")

        with (
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
            pytest.raises(
                selenium.common.exceptions.InvalidSessionIdException,
                match="Session expired",
            ),
        ):
            my_lib.selenium_util.with_session_retry(
                func,
                driver_name="TestDriver",
                data_dir=temp_dir,
                max_retries=2,
            )

    def test_clear_profile_on_error_false(self, temp_dir):
        """clear_profile_on_error=False でプロファイル削除をスキップ"""
        import selenium.common.exceptions

        def func():
            raise selenium.common.exceptions.InvalidSessionIdException("Session expired")

        with (
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            pytest.raises(selenium.common.exceptions.InvalidSessionIdException),
        ):
            my_lib.selenium_util.with_session_retry(
                func,
                driver_name="TestDriver",
                data_dir=temp_dir,
                clear_profile_on_error=False,
            )

        mock_delete.assert_not_called()

    def test_on_retry_callback_called(self, temp_dir):
        """on_retry コールバックが呼ばれる"""
        import selenium.common.exceptions

        call_count = 0
        callback_calls = []

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("Session expired")
            return "success"

        def on_retry(attempt, max_retries):
            callback_calls.append((attempt, max_retries))

        with unittest.mock.patch("my_lib.chrome_util.delete_profile"):
            my_lib.selenium_util.with_session_retry(
                func,
                driver_name="TestDriver",
                data_dir=temp_dir,
                max_retries=2,
                on_retry=on_retry,
            )

        assert len(callback_calls) == 1
        assert callback_calls[0] == (1, 2)

    def test_before_retry_callback_called(self, temp_dir):
        """before_retry コールバックが呼ばれる"""
        import selenium.common.exceptions

        call_count = 0
        before_retry_called = []

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("Session expired")
            return "success"

        def before_retry():
            before_retry_called.append(True)

        with unittest.mock.patch("my_lib.chrome_util.delete_profile"):
            my_lib.selenium_util.with_session_retry(
                func,
                driver_name="TestDriver",
                data_dir=temp_dir,
                before_retry=before_retry,
            )

        assert len(before_retry_called) == 1
