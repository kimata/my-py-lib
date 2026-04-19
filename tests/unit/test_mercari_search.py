"""メルカリ検索のオークション除外ロジックのユニットテスト."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import MagicMock, patch

import my_lib.store.flea_market
import my_lib.store.mercari.search as mercari_search


def _make_result(url: str, name: str = "item", price: int = 1000) -> my_lib.store.flea_market.SearchResult:
    return my_lib.store.flea_market.SearchResult(name=name, url=url, price=price, thumb_url=None)


def test_search_excludes_auction_items_and_keeps_shops() -> None:
    """全結果からオークション出品を引いた結果が返される.

    通常出品・Shops 出品は残り、オークション出品のみ除外される。
    """
    normal_item = _make_result("https://jp.mercari.com/item/m111", "通常出品", 1000)
    shops_item = _make_result("https://jp.mercari.com/shops/product/abc", "Shops出品", 2000)
    auction_item = _make_result("https://jp.mercari.com/item/m222", "オークション出品", 3000)

    all_items = [normal_item, shops_item, auction_item]
    auction_only = [auction_item]

    driver = MagicMock()
    wait = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", side_effect=[all_items, auction_only]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=True),
    ):
        results = mercari_search.search(driver, wait, condition)

    assert len(results) == 2
    urls = {r.url for r in results}
    assert normal_item.url in urls, "通常出品が結果に含まれるべき"
    assert shops_item.url in urls, "Shops 出品が結果に含まれるべき"
    assert auction_item.url not in urls, "オークション出品は除外されるべき"


def test_search_returns_all_when_no_auctions() -> None:
    """オークション出品がない場合は全結果がそのまま返される."""
    item1 = _make_result("https://jp.mercari.com/item/m111", "通常出品", 1000)
    item2 = _make_result("https://jp.mercari.com/shops/product/abc", "Shops出品", 2000)

    driver = MagicMock()
    wait = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", side_effect=[[item1, item2], []]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=True),
    ):
        results = mercari_search.search(driver, wait, condition)

    assert len(results) == 2


def test_search_returns_all_when_filter_fails() -> None:
    """フィルタ UI の操作に失敗した場合は全結果がそのまま返される."""
    item1 = _make_result("https://jp.mercari.com/item/m111")
    item2 = _make_result("https://jp.mercari.com/shops/product/abc")

    driver = MagicMock()
    wait = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", return_value=[item1, item2]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=False),
    ):
        results = mercari_search.search(driver, wait, condition)

    assert len(results) == 2


def test_search_returns_empty_when_no_results() -> None:
    """検索結果が0件の場合は空リストが返される."""
    driver = MagicMock()
    wait = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=False),
    ):
        results = mercari_search.search(driver, wait, condition)

    assert results == []
