"""メルカリ出品アイテム巡回処理のユニットテスト."""

# ruff: noqa: S101

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import my_lib.store.mercari.scrape as mercari_scrape


def _iter_with_mocks(
    item_count: int,
    execute_item_side_effect: Any,
    max_consecutive_failures: int | None,
) -> MagicMock:
    """_execute_item をモックして iter_items_on_display を実行する.

    Returns:
        _execute_item のモック（呼び出し回数の検証用）
    """
    driver = MagicMock()
    driver.find_elements.return_value = [MagicMock() for _ in range(item_count)]
    wait = MagicMock()

    with (
        patch.object(mercari_scrape, "close_popup"),
        patch.object(mercari_scrape, "_click_account_button_with_retry"),
        patch.object(mercari_scrape, "_load_url"),
        patch.object(mercari_scrape, "_execute_item", side_effect=execute_item_side_effect) as mock_item,
        patch.object(mercari_scrape.my_lib.selenium_util, "click_xpath"),
        patch.object(mercari_scrape.my_lib.selenium_util, "random_sleep"),
        patch.object(mercari_scrape.time, "sleep"),
    ):
        mercari_scrape.iter_items_on_display(
            driver,
            wait,
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
