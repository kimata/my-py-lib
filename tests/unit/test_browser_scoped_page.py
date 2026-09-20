#!/usr/bin/env python3
# ruff: noqa: S101
"""Page のスコープ API（Browser.page / tab, BrowserManager.page）のユニットテスト

Page はスコープ内でのみ存在し、with を抜けるとタブごと閉じられることを検証する。
タブの寿命を作業単位に限定することがリーク対策の本体（Patchright の RouteImpl リスナー
未解除や detach 済み Frame の蓄積は、タブを閉じることでしか解放されない）。
"""

from __future__ import annotations

import logging
import pathlib
import unittest.mock

import pytest

import my_lib.browser
import my_lib.browser.backends.patchright.browser
import my_lib.browser.backends.patchright.page
import my_lib.browser.backends.selenium.browser
from my_lib.browser.types import BrowserProfile


@pytest.fixture
def temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path


def _make_context(headless_ua: bool = False) -> unittest.mock.MagicMock:
    """Playwright BrowserContext のモック（初期タブ 1 つ付き）"""
    context = unittest.mock.MagicMock()
    keeper = unittest.mock.MagicMock(name="keeper")
    context.pages = [keeper]

    def new_page():
        page = unittest.mock.MagicMock(name="page")
        page.evaluate.return_value = (
            "Mozilla/5.0 HeadlessChrome/153.0" if headless_ua else "Mozilla/5.0 Chrome/153.0"
        )
        return page

    context.new_page.side_effect = new_page
    return context


class TestPatchrightBrowserPageScope:
    """PatchrightBrowser.page / tab のテスト"""

    def _browser(self, temp_dir: pathlib.Path, context, **profile_kwargs):
        profile = BrowserProfile(name="Test", data_dir=temp_dir, **profile_kwargs)
        return my_lib.browser.backends.patchright.browser.PatchrightBrowser(object(), context, profile)

    def test_page_opens_new_tab_and_closes_on_exit(self, temp_dir: pathlib.Path):
        context = _make_context()
        browser = self._browser(temp_dir, context)

        with browser.page() as page:
            raw = page.raw
            assert raw is not context.pages[0]  # 番人タブは外に出さない
            raw.close.assert_not_called()

        raw.close.assert_called_once()

    def test_page_closes_on_exception(self, temp_dir: pathlib.Path):
        context = _make_context()
        browser = self._browser(temp_dir, context)

        raw = None
        with pytest.raises(ValueError, match="boom"), browser.page() as page:
            raw = page.raw
            raise ValueError("boom")

        assert raw is not None
        raw.close.assert_called_once()

    def test_each_scope_gets_fresh_tab(self, temp_dir: pathlib.Path):
        context = _make_context()
        browser = self._browser(temp_dir, context)

        with browser.page() as first:
            first_raw = first.raw
        with browser.page() as second:
            assert second.raw is not first_raw

        assert context.new_page.call_count == 2

    def test_tab_navigates_then_closes(self, temp_dir: pathlib.Path):
        context = _make_context()
        browser = self._browser(temp_dir, context)

        with browser.tab("https://example.com/") as page:
            page.raw.goto.assert_called_once_with("https://example.com/", wait_until="domcontentloaded")
            raw = page.raw

        raw.close.assert_called_once()

    def test_keeper_tab_is_reused_from_context(self, temp_dir: pathlib.Path):
        context = _make_context()
        browser = self._browser(temp_dir, context)

        assert browser._keeper is context.pages[0]
        context.new_page.assert_not_called()

    def test_headless_ua_override_is_owned_by_page_and_detached_on_close(self, temp_dir: pathlib.Path):
        context = _make_context(headless_ua=True)
        cdp = unittest.mock.MagicMock(name="cdp")
        context.new_cdp_session.return_value = cdp
        browser = self._browser(temp_dir, context, headless=True)

        with browser.page() as page:
            context.new_cdp_session.assert_called_once_with(page.raw)
            cdp.send.assert_called_once_with(
                "Network.setUserAgentOverride", {"userAgent": "Mozilla/5.0 Chrome/153.0"}
            )
            cdp.detach.assert_not_called()  # 上書きはセッションが生きている間だけ有効

        cdp.detach.assert_called_once()

    def test_no_ua_override_when_not_headless_ua(self, temp_dir: pathlib.Path):
        context = _make_context(headless_ua=False)
        browser = self._browser(temp_dir, context)

        with browser.page():
            pass

        context.new_cdp_session.assert_not_called()

    def test_no_ua_override_when_explicit_user_agent(self, temp_dir: pathlib.Path):
        context = _make_context(headless_ua=True)
        browser = self._browser(temp_dir, context, user_agent="Custom UA")

        with browser.page():
            pass

        context.new_cdp_session.assert_not_called()


class TestPatchrightMaintenanceSession:
    """保守操作の一時 CDP セッションが detach されるテスト"""

    def test_temporary_session_is_detached(self, temp_dir: pathlib.Path):
        context = _make_context()
        cdp = unittest.mock.MagicMock(name="cdp")
        context.new_cdp_session.return_value = cdp
        profile = BrowserProfile(name="Test", data_dir=temp_dir)
        browser = my_lib.browser.backends.patchright.browser.PatchrightBrowser(object(), context, profile)

        browser.maintenance.clear_cache()

        context.new_cdp_session.assert_called_once_with(browser._keeper)
        cdp.send.assert_called_once_with("Network.clearBrowserCache")
        cdp.detach.assert_called_once()

    def test_session_is_detached_even_if_send_fails(self, temp_dir: pathlib.Path):
        context = _make_context()
        cdp = unittest.mock.MagicMock(name="cdp")
        cdp.send.side_effect = RuntimeError("boom")
        context.new_cdp_session.return_value = cdp
        profile = BrowserProfile(name="Test", data_dir=temp_dir)
        browser = my_lib.browser.backends.patchright.browser.PatchrightBrowser(object(), context, profile)

        browser.maintenance.collect_garbage()

        cdp.detach.assert_called_once()


class TestNavigationWarning:
    """1 タブでのナビゲーション回数が多すぎるときの警告テスト"""

    def test_warns_once_at_threshold(self, caplog: pytest.LogCaptureFixture):
        pw_page = unittest.mock.MagicMock()
        page = my_lib.browser.backends.patchright.page.PatchrightPage(pw_page)
        threshold = my_lib.browser.backends.patchright.page.NAVIGATION_WARN_THRESHOLD

        with caplog.at_level(logging.WARNING):
            for _ in range(threshold + 5):
                page.goto("https://example.com/")

        warnings = [r for r in caplog.records if "スコープが広すぎる" in r.getMessage()]
        assert len(warnings) == 1


class TestSeleniumBrowserPageScope:
    """SeleniumBrowser.page / tab のテスト（新しいウィンドウを開き、終了時に元へ戻る）"""

    def _driver(self) -> unittest.mock.MagicMock:
        driver = unittest.mock.MagicMock()
        driver.current_window_handle = "keeper"
        handles = ["keeper"]
        driver.window_handles = handles

        def open_window(_script):
            handles.append(f"w{len(handles)}")

        def close_window():
            handles.pop()

        driver.execute_script.side_effect = open_window
        driver.close.side_effect = close_window
        return driver

    def test_page_opens_window_and_returns_to_original(self):
        driver = self._driver()
        browser = my_lib.browser.backends.selenium.browser.SeleniumBrowser(driver)

        with unittest.mock.patch("time.sleep"), browser.page():
            driver.switch_to.window.assert_called_with("w1")

        assert driver.window_handles == ["keeper"]
        driver.switch_to.window.assert_called_with("keeper")

    def test_tab_navigates(self):
        driver = self._driver()
        browser = my_lib.browser.backends.selenium.browser.SeleniumBrowser(driver)

        with unittest.mock.patch("time.sleep"), browser.tab("https://example.com/"):
            driver.get.assert_called_once_with("https://example.com/")


class TestBrowserManagerPageScope:
    """BrowserManager.page / tab のテスト"""

    def test_page_launches_lazily_and_yields_scoped_page(self, temp_dir: pathlib.Path):
        browser = unittest.mock.MagicMock()
        page = unittest.mock.MagicMock(name="page")
        browser.page.return_value.__enter__.return_value = page
        manager = my_lib.browser.BrowserManager(BrowserProfile(name="Test", data_dir=temp_dir))

        with unittest.mock.patch("my_lib.browser.factory.launch", return_value=browser) as launch:
            assert manager.has_browser() is False
            with manager.page() as scoped:
                assert scoped is page
                assert manager.has_browser() is True
            with manager.page():
                pass

            launch.assert_called_once()
            assert browser.page.call_count == 2

    def test_tab_delegates_to_browser(self, temp_dir: pathlib.Path):
        browser = unittest.mock.MagicMock()
        manager = my_lib.browser.BrowserManager(BrowserProfile(name="Test", data_dir=temp_dir))

        with (
            unittest.mock.patch("my_lib.browser.factory.launch", return_value=browser),
            manager.tab("https://example.com/"),
        ):
            browser.tab.assert_called_once_with("https://example.com/")

    def test_run_with_session_retry_reopens_scope_on_new_browser(self, temp_dir: pathlib.Path):
        first = unittest.mock.MagicMock(name="first")
        second = unittest.mock.MagicMock(name="second")
        browsers = iter([first, second])
        manager = my_lib.browser.BrowserManager(BrowserProfile(name="Test", data_dir=temp_dir))
        seen = []

        def work():
            with manager.page() as page:
                seen.append(page)
                if len(seen) == 1:
                    raise my_lib.browser.SessionError("lost")
                return "ok"

        with (
            unittest.mock.patch(
                "my_lib.browser.factory.launch", side_effect=lambda *_a, **_k: next(browsers)
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile"),
        ):
            assert manager.run_with_session_retry(work) == "ok"

        first.close.assert_called_once()
        assert seen[0] is first.page.return_value.__enter__.return_value
        assert seen[1] is second.page.return_value.__enter__.return_value


class TestRealBrowserScope:
    """実ブラウザ（headless）でスコープ終了後にタブが残らないことを検証する"""

    def test_context_has_only_keeper_after_scope(self, temp_dir: pathlib.Path):
        profile = BrowserProfile(name="Scoped", data_dir=temp_dir, headless=True)
        browser = my_lib.browser.backends.patchright.browser.launch(profile)
        try:
            with browser.page() as page:
                page.raw.set_content("<html><body><p id='x'>hello</p></body></html>")
                assert page.find(my_lib.browser.Css("#x")) is not None
                assert len(browser._context.pages) == 2
            assert len(browser._context.pages) == 1
            assert browser._context.pages[0] is browser._keeper
        finally:
            browser.close()
