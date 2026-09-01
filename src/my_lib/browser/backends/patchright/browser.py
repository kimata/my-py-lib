"""Patchright バックエンドの Browser 実装と launch。

素の Chrome を Patchright（自動化痕跡除去済み Playwright）で起動する。
bot 検出回避のため既定は headful（Xvfb 上での実行を想定）。stealth は Patchright 内蔵。
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from my_lib.browser.backends.patchright.maintenance import PatchrightMaintenance
from my_lib.browser.backends.patchright.page import PatchrightPage
from my_lib.browser.exceptions import BrowserError
from my_lib.browser.types import BrowserProfile

if TYPE_CHECKING:
    from patchright.sync_api import BrowserContext as PwContext
    from patchright.sync_api import Page as PwPage


class PatchrightBrowser:
    """永続コンテキストを 1 つ束ねる Browser 実装。"""

    def __init__(self, playwright: object, context: PwContext, profile: BrowserProfile) -> None:
        self._pw = playwright
        self._context = context
        self._profile = profile
        pages = context.pages
        pw_page = pages[0] if pages else context.new_page()
        self._apply_stealth_ua(pw_page)
        self._default_page = PatchrightPage(pw_page)

    def _apply_stealth_ua(self, pw_page: PwPage) -> None:
        """headless 時に UA から "HeadlessChrome" 痕跡を除去する。

        Patchright は headless で navigator.userAgent に "HeadlessChrome" を残す。
        ヨドバシ等の anti-bot はこれを検知して接続を拒否する（ERR_HTTP2_PROTOCOL_ERROR）。
        明示 UA 未指定のページ生成ごとに CDP で "HeadlessChrome"→"Chrome" 補正した UA を
        適用する（ページ生成経路が限られるため context の page イベントに頼らず明示的に呼ぶ）。
        headful では UA に痕跡が無いため no-op。
        """
        if self._profile.user_agent is not None:
            # 明示指定 UA は launch 時に context 全体へ適用済み。
            return
        try:
            ua = pw_page.evaluate("() => navigator.userAgent")
        except Exception:
            logging.debug("Failed to read UA for stealth override")
            return
        if not isinstance(ua, str) or "HeadlessChrome" not in ua:
            return
        modified = ua.replace("HeadlessChrome", "Chrome")
        try:
            cdp = self._context.new_cdp_session(pw_page)
            cdp.send("Network.setUserAgentOverride", {"userAgent": modified})
        except Exception:
            logging.debug("Failed to override UA via CDP")

    @property
    def default_page(self) -> PatchrightPage:
        return self._default_page

    def new_page(self) -> PatchrightPage:
        pw_page = self._context.new_page()
        self._apply_stealth_ua(pw_page)
        return PatchrightPage(pw_page)

    @contextlib.contextmanager
    def tab(self, url: str) -> Iterator[PatchrightPage]:
        pw_page = self._context.new_page()
        self._apply_stealth_ua(pw_page)
        page = PatchrightPage(pw_page)
        try:
            page.goto(url)
            yield page
        finally:
            with contextlib.suppress(Exception):
                pw_page.close()

    def pages(self) -> list[PatchrightPage]:
        return [PatchrightPage(p) for p in self._context.pages]

    @property
    def maintenance(self) -> PatchrightMaintenance:
        return PatchrightMaintenance(self._context, self._default_page.raw)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._context.close()
        with contextlib.suppress(Exception):
            self._pw.stop()  # type: ignore[attr-defined]


def launch(profile: BrowserProfile) -> PatchrightBrowser:
    """Patchright で永続コンテキストを起動して Browser を返す。"""
    from patchright.sync_api import sync_playwright

    playwright = sync_playwright().start()

    args = ["--no-sandbox", "--disable-dev-shm-usage", f"--lang={profile.locale}"]

    launch_kwargs: dict = {
        # NOTE: 既存 Selenium 実装・chrome_util.delete_profile と同じ data_dir/chrome/<name> 配下に置く。
        "user_data_dir": str(profile.data_dir / "chrome" / profile.name),
        "headless": profile.headless,
        "locale": profile.locale,
        "viewport": {"width": profile.viewport.width, "height": profile.viewport.height},
        "device_scale_factor": profile.device_scale_factor,
        "args": args,
    }
    if profile.chrome_path is not None:
        launch_kwargs["executable_path"] = profile.chrome_path
    else:
        # NOTE: システムの通常版 Chrome を使う（Chrome for Testing ではなく）。
        launch_kwargs["channel"] = "chrome"
    if profile.user_agent is not None:
        launch_kwargs["user_agent"] = profile.user_agent

    logging.info("Launching Patchright (headless=%s, profile=%s)", profile.headless, profile.name)
    try:
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception as e:
        # NOTE: 起動失敗（XServer 無し等）を BrowserError に正規化して原因を明示する。
        #       headful なのに X ディスプレイが無い場合は xvfb-run 経由での実行が必要。
        with contextlib.suppress(Exception):
            playwright.stop()
        message = str(e)
        if not profile.headless and "XServer" in message:
            message += "（headful 起動には X ディスプレイが必要です。xvfb-run 経由で実行してください）"
        raise BrowserError(message) from e
    return PatchrightBrowser(playwright, context, profile)
