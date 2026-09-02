#!/usr/bin/env python3
# ruff: noqa: S101
"""my_lib.browser.backends.patchright.browser のユニットテスト"""

import pathlib
import unittest.mock

import pytest

import my_lib.browser.backends.patchright.browser
from my_lib.browser.exceptions import BrowserError
from my_lib.browser.types import BrowserProfile


@pytest.fixture
def temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path


@pytest.fixture(autouse=True)
def reset_playwright_holder():
    """スレッド共有の Playwright インスタンスをテストごとに初期化する"""
    holder = my_lib.browser.backends.patchright.browser._holder
    holder.playwright = None
    holder.refcount = 0
    yield
    holder.playwright = None
    holder.refcount = 0


def _patch_sync_playwright(mock_playwright: unittest.mock.MagicMock):
    return unittest.mock.patch(
        "patchright.sync_api.sync_playwright",
        return_value=unittest.mock.MagicMock(start=lambda: mock_playwright),
    )


class TestSharedPlaywrightInstance:
    """同一スレッドでの Playwright インスタンス共有のテスト

    Playwright Sync API は 1 スレッドに 1 インスタンスしか起動できない
    （2 つ目の start() は "inside the asyncio loop" エラー）。
    メーカー別プロファイルのように複数ブラウザを同時に保持しても
    インスタンスを共有し、最後のブラウザが閉じるまで stop しないことを検証する。
    """

    def _make_profile(self, temp_dir: pathlib.Path, name: str) -> BrowserProfile:
        return BrowserProfile(name=name, data_dir=temp_dir)

    def test_multiple_launches_share_one_instance(self, temp_dir: pathlib.Path):
        mock_playwright = unittest.mock.MagicMock()

        with _patch_sync_playwright(mock_playwright) as sync_playwright_mock:
            first = my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "A"))
            second = my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "B"))

            assert sync_playwright_mock.call_count == 1
            assert mock_playwright.chromium.launch_persistent_context.call_count == 2

            first.close()
            mock_playwright.stop.assert_not_called()

            second.close()
            mock_playwright.stop.assert_called_once()

            # 全て閉じた後の再起動で新しいインスタンスが作られる
            my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "C"))
            assert sync_playwright_mock.call_count == 2

    def test_double_close_releases_once(self, temp_dir: pathlib.Path):
        mock_playwright = unittest.mock.MagicMock()

        with _patch_sync_playwright(mock_playwright):
            first = my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "A"))
            second = my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "B"))

            first.close()
            first.close()
            # 二重 close で second の分まで解放されないこと
            mock_playwright.stop.assert_not_called()

            second.close()
            mock_playwright.stop.assert_called_once()

    def test_launch_failure_releases_instance(self, temp_dir: pathlib.Path):
        mock_playwright = unittest.mock.MagicMock()
        mock_playwright.chromium.launch_persistent_context.side_effect = RuntimeError("boom")

        with _patch_sync_playwright(mock_playwright), pytest.raises(BrowserError):
            my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "A"))

        # 誰も使っていないので停止される
        mock_playwright.stop.assert_called_once()
        assert my_lib.browser.backends.patchright.browser._holder.playwright is None

    def test_launch_failure_keeps_instance_for_other_browser(self, temp_dir: pathlib.Path):
        mock_playwright = unittest.mock.MagicMock()
        mock_playwright.chromium.launch_persistent_context.side_effect = [
            unittest.mock.MagicMock(),
            RuntimeError("boom"),
        ]

        with _patch_sync_playwright(mock_playwright):
            first = my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "A"))
            with pytest.raises(BrowserError):
                my_lib.browser.backends.patchright.browser.launch(self._make_profile(temp_dir, "B"))

            # 起動中のブラウザが残っている間は停止しない
            mock_playwright.stop.assert_not_called()
            first.close()
            mock_playwright.stop.assert_called_once()


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


class TestWaitVisible:
    """PatchrightPage.wait_visible のテスト（実ブラウザ・headless）"""

    def test_skips_hidden_first_match(self):
        """DOM 先頭のマッチが不可視でも、後方の可視要素を検出できる

        Amazon のページは hidden な rhf-footer が可視の navFooter より前に
        あるため、.first 固定だと可視のフッターがあってもタイムアウトする
        （本番でログインが全滅した実障害の再現）。
        """
        from patchright.sync_api import sync_playwright

        from my_lib.browser import Xpath
        from my_lib.browser.backends.patchright.page import PatchrightPage

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
            try:
                pw_page = browser.new_page()
                pw_page.set_content(
                    '<div class="rhf-footer" style="display:none">hidden</div>'
                    '<div id="navFooter" class="navLeftFooter">visible footer</div>'
                )
                page = PatchrightPage(pw_page)

                element = page.wait_visible(
                    Xpath('//div[contains(@class, "footer") or contains(@class, "Footer")]'),
                    timeout=5.0,
                )

                assert element.attr("id") == "navFooter"
            finally:
                browser.close()
