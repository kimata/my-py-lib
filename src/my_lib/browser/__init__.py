"""ブラウザ抽象層。

バックエンド（Patchright / Selenium）非依存の Protocol と、その管理・生成 API を提供する。
呼び出し側（store 層・各プロジェクト）は `selenium.*` / `patchright.*` を一切 import せず、
本パッケージの Protocol と型のみに依存する。

基本的な使い方::

    import my_lib.browser

    profile = my_lib.browser.BrowserProfile(name="Merhist", data_dir=data_dir)
    manager = my_lib.browser.BrowserManager(profile)
    with manager.page() as page:
        page.goto("https://jp.mercari.com")
        page.wait_visible(my_lib.browser.Xpath('//button[contains(text(), "ログイン")]')).click()
    # with を抜けるとタブは閉じられ、タブに紐づくリソースは全て解放される

Page は `page()` / `tab()` のスコープ内でのみ存在する。スコープの単位は「1 つの作業」
（1 商品・1 注文・1 検索）とし、巡回全体を 1 つのスコープで包まないこと。
"""

from typing import Any

from my_lib.browser.exceptions import (
    BrowserError,
    ElementNotFoundError,
    NavigationError,
    SessionError,
    WaitTimeoutError,
)
from my_lib.browser.factory import launch
from my_lib.browser.locator import Css, Locator, Xpath
from my_lib.browser.manager import BrowserManager
from my_lib.browser.protocol import (
    Browser,
    Element,
    FrameScope,
    Maintenance,
    Page,
)
from my_lib.browser.types import (
    BoundingBox,
    BrowserBackend,
    BrowserProfile,
    ScreenshotSpec,
    Viewport,
)


def wrap_selenium_driver(driver: Any) -> Page:
    """既存の Selenium WebDriver を Page として包む（移行期の橋渡し用）。

    まだ Patchright に移行していないプロジェクトが、Page ベースへ移植済みの共有
    store 層（例: mercari のログイン）を、既存の Selenium ドライバのまま呼び出すために使う。
    """
    from my_lib.browser.backends.selenium.page import SeleniumPage

    return SeleniumPage(driver)


__all__ = [
    "BoundingBox",
    "Browser",
    "BrowserBackend",
    "BrowserError",
    "BrowserManager",
    "BrowserProfile",
    "Css",
    "Element",
    "ElementNotFoundError",
    "FrameScope",
    "Locator",
    "Maintenance",
    "NavigationError",
    "Page",
    "ScreenshotSpec",
    "SessionError",
    "Viewport",
    "WaitTimeoutError",
    "Xpath",
    "launch",
    "wrap_selenium_driver",
]
