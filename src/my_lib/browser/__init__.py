"""ブラウザ抽象層。

バックエンド（Patchright / Selenium）非依存の Protocol と、その管理・生成 API を提供する。
呼び出し側（store 層・各プロジェクト）は `selenium.*` / `patchright.*` を一切 import せず、
本パッケージの Protocol と型のみに依存する。

基本的な使い方::

    import my_lib.browser

    profile = my_lib.browser.BrowserProfile(name="Merhist", data_dir=data_dir)
    manager = my_lib.browser.BrowserManager(profile)
    page = manager.get_page()
    page.goto("https://jp.mercari.com")
    page.wait_visible(my_lib.browser.Xpath('//button[contains(text(), "ログイン")]')).click()
"""

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
    BrowserSession,
    Element,
    FrameScope,
    Maintenance,
    Page,
)
from my_lib.browser.types import (
    BrowserBackend,
    BrowserProfile,
    ScreenshotSpec,
    Viewport,
)

__all__ = [
    "Browser",
    "BrowserBackend",
    "BrowserError",
    "BrowserManager",
    "BrowserProfile",
    "BrowserSession",
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
]
