#!/usr/bin/env python3
# ruff: noqa: S101
"""my_lib.store.paypay.search のユニットテスト"""

from unittest.mock import MagicMock, patch

import pytest

import my_lib.store.paypay.search as paypay_search
from my_lib.browser import Xpath

# PayPay が完全一致なしのときに表示する通知文（実ページの DOM を抜粋）
_NEAR_MATCH_NOTICE_HTML = (
    '<div class="sc-b997c0b6-2 fQCSft"><p class="sc-9dbc04ce-0 dVAKVE">'
    "一致する商品が見つからなかったため、検索キーワードに近い商品を表示しています"
    "</p></div>"
)


def _make_page(present_xpaths: set[str]) -> MagicMock:
    page = MagicMock()
    page.exists.side_effect = lambda locator, **_: locator.value in present_xpaths
    return page


class TestWaitForSearchResults:
    """_wait_for_search_results の 0 件判定（モック）"""

    def test_returns_false_on_near_match_notice(self) -> None:
        """完全一致なし（近い商品のみ表示）の通知文があれば 0 件として扱い、並び替えも行わない."""
        page = _make_page({paypay_search._NEAR_MATCH_NOTICE_XPATH})

        with (
            patch.object(paypay_search.time, "sleep"),
            patch.object(paypay_search, "_select_sort_order") as select_sort_order,
        ):
            assert paypay_search._wait_for_search_results(page) is False

        select_sort_order.assert_not_called()

    def test_returns_false_on_no_result_text(self) -> None:
        page = _make_page({paypay_search._NO_RESULT_XPATH})

        with patch.object(paypay_search.time, "sleep"):
            assert paypay_search._wait_for_search_results(page) is False

    def test_returns_true_when_results_exist(self) -> None:
        page = _make_page(set())

        with (
            patch.object(paypay_search.time, "sleep"),
            patch.object(paypay_search, "_select_sort_order") as select_sort_order,
        ):
            assert paypay_search._wait_for_search_results(page) is True

        select_sort_order.assert_called_once_with(page)


class TestNearMatchNoticeXpath:
    """通知文の XPath が実ページの DOM に一致するテスト（実ブラウザ・headless）"""

    @pytest.fixture
    def pw_page(self):
        from patchright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
            try:
                yield browser.new_page()
            finally:
                browser.close()

    def test_xpath_matches_real_notice_markup(self, pw_page) -> None:
        from my_lib.browser.backends.patchright.page import PatchrightPage

        pw_page.set_content(
            f"<html><body><main>{_NEAR_MATCH_NOTICE_HTML}<ul><li>近い商品</li></ul></main></body></html>"
        )
        page = PatchrightPage(pw_page)

        assert page.exists(Xpath(paypay_search._NEAR_MATCH_NOTICE_XPATH), visible=False)
        assert not page.exists(Xpath(paypay_search._NO_RESULT_XPATH), visible=False)

    def test_xpath_does_not_match_normal_result_page(self, pw_page) -> None:
        from my_lib.browser.backends.patchright.page import PatchrightPage

        pw_page.set_content(
            "<html><body><main><h1>RF50mm F1.2 L USMの検索結果</h1><p>条件を保存</p>"
            "<ul><li>商品</li></ul></main></body></html>"
        )
        page = PatchrightPage(pw_page)

        assert not page.exists(Xpath(paypay_search._NEAR_MATCH_NOTICE_XPATH), visible=False)
