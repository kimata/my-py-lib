"""メルカリ出品アイテム巡回処理のユニットテスト."""

# ruff: noqa: S101

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import my_lib.browser
import my_lib.store.mercari.scrape as mercari_scrape
from my_lib.browser import Xpath


def _iter_with_mocks(
    item_count: int,
    execute_item_side_effect: Any,
    max_consecutive_failures: int | None,
) -> MagicMock:
    """_execute_item をモックして iter_items_on_display を実行する.

    Returns:
        _execute_item のモック（呼び出し回数の検証用）
    """
    page = MagicMock(name="page")
    page.find_all.return_value = [MagicMock() for _ in range(item_count)]
    page.url = "https://jp.mercari.com/mypage/listings"

    with (
        patch.object(mercari_scrape, "close_popup"),
        patch.object(mercari_scrape, "_click_account_button_with_retry"),
        patch.object(mercari_scrape, "_load_url"),
        patch.object(mercari_scrape, "_execute_item", side_effect=execute_item_side_effect) as mock_item,
        patch.object(mercari_scrape, "random_sleep"),
        patch.object(mercari_scrape.time, "sleep"),
    ):
        mercari_scrape.iter_items_on_display(
            page,
            False,
            [MagicMock()],
            max_consecutive_failures=max_consecutive_failures,
        )

    return mock_item


def test_failure_raises_immediately_by_default() -> None:
    """max_consecutive_failures 未指定なら、1 アイテムの失敗で（リトライ後）例外を送出する."""
    with pytest.raises(RuntimeError):
        _iter_with_mocks(
            item_count=3,
            execute_item_side_effect=RuntimeError("parse error"),
            max_consecutive_failures=None,
        )


def test_single_failure_skips_to_next_item() -> None:
    """単発の失敗はスキップして次のアイテムに進む."""
    # アイテム 1 はリトライ 3 回とも失敗、アイテム 2-3 は成功
    side_effect = [RuntimeError("error")] * 3 + [MagicMock(), MagicMock()]

    mock_item = _iter_with_mocks(
        item_count=3,
        execute_item_side_effect=side_effect,
        max_consecutive_failures=2,
    )

    assert mock_item.call_count == 5  # 3 (失敗リトライ) + 2 (成功)


def test_consecutive_failures_abort() -> None:
    """連続 2 アイテムの失敗で例外を送出する."""
    with pytest.raises(RuntimeError):
        _iter_with_mocks(
            item_count=3,
            execute_item_side_effect=RuntimeError("error"),
            max_consecutive_failures=2,
        )


def test_failure_counter_resets_on_success() -> None:
    """失敗カウントは成功で 0 に戻るため、非連続の失敗では中断しない."""
    # アイテム 1 失敗 (3 リトライ) → アイテム 2 成功 → アイテム 3 失敗 (3 リトライ)
    side_effect = [RuntimeError("error")] * 3 + [MagicMock()] + [RuntimeError("error")] * 3

    mock_item = _iter_with_mocks(
        item_count=3,
        execute_item_side_effect=side_effect,
        max_consecutive_failures=2,
    )

    assert mock_item.call_count == 7


class TestLoadUrl:
    """_load_url のテスト（Page API の goto + wait_present でリトライする）."""

    def test_retries_on_timeout_then_succeeds(self) -> None:
        page = MagicMock(name="page")
        page.wait_present.side_effect = [my_lib.browser.WaitTimeoutError("timeout"), None]

        with patch.object(mercari_scrape, "random_sleep"), patch.object(mercari_scrape, "_expand_all"):
            mercari_scrape._load_url(page, "https://example.com/list")

        assert page.goto.call_count == 2
        page.goto.assert_called_with("https://example.com/list")

    def test_gives_up_after_retries(self) -> None:
        page = MagicMock(name="page")
        page.wait_present.side_effect = my_lib.browser.WaitTimeoutError("timeout")

        with (
            patch.object(mercari_scrape, "random_sleep"),
            pytest.raises(my_lib.browser.WaitTimeoutError),
        ):
            mercari_scrape._load_url(page, "https://example.com/list")

        assert page.goto.call_count == mercari_scrape._TRY_COUNT


class TestParseItem:
    """_parse_item のテスト（Element API で一覧行を解析する）."""

    @staticmethod
    def _element(text: str = "", href: str | None = None) -> MagicMock:
        element = MagicMock(name="element")
        element.text = text
        element.attr.return_value = href
        return element

    def test_parses_item_fields(self) -> None:
        link = self._element(href="https://jp.mercari.com/item/m123")
        name = self._element(text="テスト商品")
        price = self._element(text="12,345")
        favorite = self._element(text="7")
        view = self._element(text="42")

        item_element = MagicMock(name="item")
        item_element.find.side_effect = lambda locator: {
            ".//a[@data-testid='listed-item']": link,
            ".//p[@data-testid='item-label']": name,
        }[locator.value]
        item_element.find_all.side_effect = lambda locator: {
            ".//span[@data-testid='price']/span[2]": [price],
            ".//span[@data-testid='price']/following-sibling::div/div[1]/span": [favorite],
            ".//span[@data-testid='price']/following-sibling::div/div[3]/span": [view],
            ".//span[contains(text(), '公開停止中')]": [],
        }[locator.value]

        page = MagicMock(name="page")
        page.find.return_value = item_element

        with patch.object(mercari_scrape.time, "sleep"):
            item, item_link = mercari_scrape._parse_item(page, 2)

        page.find.assert_called_once_with(Xpath(f"{mercari_scrape._ITEM_LIST_XPATH}[2]"))
        assert item_link is link
        assert item.id == "m123"
        assert item.name == "テスト商品"
        assert item.price == 12345
        assert item.favorite == 7
        assert item.view == 42
        assert item.is_stop == 0
        page.refresh.assert_not_called()

    def test_reloads_when_row_is_not_rendered(self) -> None:
        """要素が欠けているときはリロードして取り直す."""
        link = self._element(href="https://jp.mercari.com/item/m1")
        name = self._element(text="商品")
        price = self._element(text="100")

        complete = MagicMock(name="item")
        complete.find.side_effect = lambda locator: {
            ".//a[@data-testid='listed-item']": link,
            ".//p[@data-testid='item-label']": name,
        }[locator.value]
        complete.find_all.side_effect = lambda locator: [price] if "span[2]" in locator.value else []

        page = MagicMock(name="page")
        page.find.side_effect = [None, complete]

        with patch.object(mercari_scrape.time, "sleep"):
            item, _ = mercari_scrape._parse_item(page, 1)

        page.refresh.assert_called_once()
        assert item.id == "m1"


class TestCloseDialog:
    """_close_dialog のテスト."""

    def test_clicks_visible_close_button(self) -> None:
        button = MagicMock(name="button")
        button.is_visible.return_value = True
        dialog = MagicMock(name="dialog")
        dialog.find_all.return_value = [button]

        with patch.object(mercari_scrape.time, "sleep"):
            mercari_scrape._close_dialog(MagicMock(name="page"), dialog)

        button.click.assert_called_once()
        dialog.press.assert_not_called()

    def test_falls_back_to_escape(self) -> None:
        dialog = MagicMock(name="dialog")
        dialog.find_all.return_value = []

        with patch.object(mercari_scrape.time, "sleep"):
            mercari_scrape._close_dialog(MagicMock(name="page"), dialog)

        dialog.press.assert_called_once_with("Escape")

    def test_resolves_aria_labelledby_via_text_content(self) -> None:
        """非表示ラベル（textContent）で「閉じる」を判定する."""
        button = MagicMock(name="button")
        button.is_visible.return_value = True
        button.attr.return_value = "label-id"
        dialog = MagicMock(name="dialog")
        dialog.find_all.side_effect = [[], [button]]
        label = MagicMock(name="label")
        label.evaluate.return_value = "閉じる"
        page = MagicMock(name="page")
        page.find_all.return_value = [label]

        with patch.object(mercari_scrape.time, "sleep"):
            mercari_scrape._close_dialog(page, dialog)

        button.click.assert_called_once()


class TestClosePopupCoachMark:
    """role=dialog を持たないコーチマーク型ポップアップも閉じる."""

    @staticmethod
    def _page(button: MagicMock, label_text: str) -> MagicMock:
        label = MagicMock(name="label")
        label.evaluate.return_value = label_text
        page = MagicMock(name="page")
        page.find_all.side_effect = lambda locator: (
            [button]
            if locator.value == "//button[@aria-labelledby]"
            else [label]
            if locator.value == '//*[@id="_r_d_"]'
            else []
        )
        return page

    def test_clicks_labelledby_close_button_outside_dialog(self) -> None:
        button = MagicMock(name="close")
        button.is_visible.return_value = True
        button.attr.return_value = "_r_d_"

        with patch.object(mercari_scrape.time, "sleep"):
            mercari_scrape.close_popup(self._page(button, "閉じる"))

        button.click.assert_called_once()

    def test_ignores_labelledby_button_with_other_label(self) -> None:
        button = MagicMock(name="button")
        button.is_visible.return_value = True
        button.attr.return_value = "_r_d_"

        with patch.object(mercari_scrape.time, "sleep"):
            mercari_scrape.close_popup(self._page(button, "次へ"))

        button.click.assert_not_called()
