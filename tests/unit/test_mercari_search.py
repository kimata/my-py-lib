"""メルカリ検索のオークション除外ロジックのユニットテスト."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import MagicMock, patch

import lxml.html

import my_lib.browser
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

    page = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", side_effect=[all_items, auction_only]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=True),
    ):
        results = mercari_search.search(page, condition)

    assert len(results) == 2
    urls = {r.url for r in results}
    assert normal_item.url in urls, "通常出品が結果に含まれるべき"
    assert shops_item.url in urls, "Shops 出品が結果に含まれるべき"
    assert auction_item.url not in urls, "オークション出品は除外されるべき"


def test_search_returns_all_when_no_auctions() -> None:
    """オークション出品がない場合は全結果がそのまま返される."""
    item1 = _make_result("https://jp.mercari.com/item/m111", "通常出品", 1000)
    item2 = _make_result("https://jp.mercari.com/shops/product/abc", "Shops出品", 2000)

    page = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", side_effect=[[item1, item2], []]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=True),
    ):
        results = mercari_search.search(page, condition)

    assert len(results) == 2


def test_search_returns_all_when_filter_fails() -> None:
    """フィルタ UI の操作に失敗した場合は全結果がそのまま返される."""
    item1 = _make_result("https://jp.mercari.com/item/m111")
    item2 = _make_result("https://jp.mercari.com/shops/product/abc")

    page = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=True),
        patch.object(mercari_search, "_parse_visible_items", return_value=[item1, item2]),
        patch.object(mercari_search, "_apply_listing_type_filter", return_value=False),
    ):
        results = mercari_search.search(page, condition)

    assert len(results) == 2


def test_search_returns_empty_when_no_results() -> None:
    """検索結果が0件の場合は空リストが返される."""
    page = MagicMock()
    condition = my_lib.store.flea_market.SearchCondition(keyword="test")

    with (
        patch.object(
            mercari_search, "build_search_url", return_value="https://jp.mercari.com/search?keyword=test"
        ),
        patch.object(mercari_search, "_wait_for_search_results", return_value=False),
    ):
        results = mercari_search.search(page, condition)

    assert results == []


# --- _parse_search_item (新旧 UI の DOM 構造) --------------------------------


class _FakeElement:
    """lxml ノードを my_lib.browser.protocol.Element 風に包む最小実装."""

    def __init__(self, node: lxml.html.HtmlElement) -> None:
        self._node = node

    @property
    def text(self) -> str:
        return "".join(self._node.itertext()).strip()

    def attr(self, name: str) -> str | None:
        return self._node.get(name)

    def find_all(self, locator: my_lib.browser.Locator) -> list[_FakeElement]:
        return [_FakeElement(n) for n in self._node.xpath(locator.value)]


def _make_item(html: str) -> _FakeElement:
    return _FakeElement(lxml.html.fragment_fromstring(html))


_NEW_UI_ITEM = """
<li data-testid="item-cell"><div><div><div>
  <a data-testid="thumbnail-link" href="/item/m20977984540">
    <span><picture><img alt="美品 SONY FE 24-70mm F2.8 GM IIのサムネイル 売り切れ"
        src="https://static.mercdn.net/thumb/item/webp/m20977984540_1.jpg"/></picture>
      <div><span data-testid="item-tile-price"><span><span>¥</span><span>255,000</span></span></span></div>
    </span>
    <div><div><p data-testid="thumbnail-item-name">美品 SONY FE 24-70mm F2.8 GM II SEL2470GM2</p></div></div>
  </a>
</div></div></div></li>
"""

_OLD_UI_ITEM = """
<li data-testid="item-cell">
  <a href="/item/m111">
    <div role="img" aria-label="旧UI商品の画像 12,345円"></div>
    <span data-testid="thumbnail-item-name">旧UI商品</span>
    <span class="number__6b270ca7">12,345</span>
    <img srcset="https://example.com/a_240.jpg 240w, https://example.com/a_480.jpg 480w"/>
  </a>
</li>
"""


def test_parse_search_item_new_ui() -> None:
    """2026-09 リニューアル後の DOM（p タグ名 + item-tile-price）をパースできる."""
    result = mercari_search._parse_search_item(_make_item(_NEW_UI_ITEM))  # type: ignore[arg-type]

    assert result is not None
    assert result.name == "美品 SONY FE 24-70mm F2.8 GM II SEL2470GM2"
    assert result.price == 255000
    assert result.url == "https://jp.mercari.com/item/m20977984540"
    assert result.thumb_url == "https://static.mercdn.net/thumb/item/webp/m20977984540_1.jpg"


def test_parse_search_item_old_ui() -> None:
    """リニューアル前の DOM（span タグ名 + number__ クラス）も引き続きパースできる."""
    result = mercari_search._parse_search_item(_make_item(_OLD_UI_ITEM))  # type: ignore[arg-type]

    assert result is not None
    assert result.name == "旧UI商品"
    assert result.price == 12345
    assert result.url == "https://jp.mercari.com/item/m111"
    assert result.thumb_url == "https://example.com/a_480.jpg"


def test_parse_search_item_skips_pr() -> None:
    """PR（広告）アイテムは None を返す."""
    html = '<li data-testid="item-cell"><a href="/item/m1"><p class="merText">PR</p></a></li>'
    assert mercari_search._parse_search_item(_make_item(html)) is None  # type: ignore[arg-type]


def test_item_list_xpath_accepts_both_containers() -> None:
    """アイテム一覧の XPath は新旧どちらのコンテナにもマッチする."""
    doc = lxml.html.fromstring(
        '<main><div id="item-grid"><ul><li data-testid="item-cell">old</li></ul></div>'
        '<div data-testid="search-item-grid"><ul><li data-testid="item-cell">new</li></ul></div>'
        '<div data-testid="recommend"><ul><li data-testid="item-cell">other</li></ul></div></main>'
    )
    matched = [n.text for n in doc.xpath(mercari_search._ITEM_LIST_XPATH)]
    assert matched == ["old", "new"]
