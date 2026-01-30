#!/usr/bin/env python3
"""
Yahoo!ショッピング検索ライブラリ

https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch を使用して商品を検索し、
タイトル、URL、価格のリストを取得します。

Usage:
  api.py [-c CONFIG] [-k KEYWORD] [-j JAN] [-m MIN] [-M MAX]
         [-n COUNT] [--condition CONDITION] [-D]

Options:
  -c CONFIG           : 設定ファイル。[default: config.yaml]
  -k KEYWORD          : 検索キーワード。[default: iPhone]
  -j JAN              : JANコード。
  -m MIN              : 最低価格。
  -M MAX              : 最高価格。
  -n COUNT            : 取得する最大件数。[default: 10]
  --condition COND    : 商品状態（new, used）。
  -D                  : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

import requests

from my_lib.store.yahoo.config import YahooApiConfig, YahooItem


class SortOrder(Enum):
    """ソート順"""

    SCORE = "-score"  # おすすめ順（デフォルト）
    PRICE_ASC = "+price"  # 価格の安い順
    PRICE_DESC = "-price"  # 価格の高い順
    REVIEW_COUNT = "-review_count"  # レビュー件数順


class Condition(Enum):
    """商品状態"""

    NEW = "new"  # 新品
    USED = "used"  # 中古


@dataclass(frozen=True)
class SearchCondition:
    """検索条件"""

    keyword: str
    jan: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    sort: SortOrder = SortOrder.PRICE_ASC
    in_stock: bool = True
    condition: Condition = Condition.NEW
    genre_category_id: str | None = None
    brand_id: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        sort_value = data.get("sort", "+price")
        sort = SortOrder(sort_value) if sort_value else SortOrder.PRICE_ASC

        condition_value = data.get("condition", "new")
        condition = Condition(condition_value) if condition_value else Condition.NEW

        return cls(
            keyword=data["keyword"],
            jan=data.get("jan"),
            price_min=data.get("price_min"),
            price_max=data.get("price_max"),
            sort=sort,
            in_stock=data.get("in_stock", True),
            condition=condition,
            genre_category_id=data.get("genre_category_id"),
            brand_id=data.get("brand_id"),
        )


_API_ENDPOINT: str = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
_MAX_RESULTS_PER_REQUEST: int = 50
_RATE_LIMIT_WAIT_SEC: float = 1.0


def _build_params(
    config: YahooApiConfig,
    condition: SearchCondition,
    results: int,
    start: int,
) -> dict[str, Any]:
    """API リクエストパラメータを構築する

    Args:
        config: API 設定
        condition: 検索条件
        results: 取得件数
        start: 開始位置

    Returns:
        API パラメータ辞書

    """
    params: dict[str, Any] = {
        "appid": config.client_id,
        "query": condition.keyword,
        "results": min(results, _MAX_RESULTS_PER_REQUEST),
        "start": start,
        "sort": condition.sort.value,
        "image_size": 600,
    }

    if condition.jan:
        params["jan"] = condition.jan

    if condition.price_min is not None:
        params["price_from"] = condition.price_min

    if condition.price_max is not None:
        params["price_to"] = condition.price_max

    if condition.in_stock:
        params["in_stock"] = "true"

    params["condition"] = condition.condition.value

    if condition.genre_category_id:
        params["genre_category_id"] = condition.genre_category_id

    if condition.brand_id:
        params["brand_id"] = condition.brand_id

    return params


def _fetch_page(
    config: YahooApiConfig,
    condition: SearchCondition,
    results: int,
    start: int,
) -> dict[str, Any]:
    """API を呼び出して1ページ分の結果を取得する

    Args:
        config: API 設定
        condition: 検索条件
        results: 取得件数
        start: 開始位置

    Returns:
        API レスポンス（JSON）

    Raises:
        requests.RequestException: API 呼び出しに失敗した場合

    """
    params = _build_params(config, condition, results, start)

    logging.debug("[Yahoo] API リクエスト: %s, params=%s", _API_ENDPOINT, params)

    response = requests.get(_API_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def search(
    config: YahooApiConfig,
    condition: SearchCondition,
    max_items: int | None = None,
) -> list[YahooItem]:
    """Yahoo!ショッピングで商品を検索する

    Args:
        config: API 設定
        condition: 検索条件
        max_items: 取得する最大件数（None の場合は 50 件）

    Returns:
        検索結果のリスト

    """
    if max_items is None:
        max_items = _MAX_RESULTS_PER_REQUEST

    logging.info("[Yahoo] 検索開始: keyword=%s", condition.keyword)

    # API 制限: start + results <= 1000
    max_start = 1000 - _MAX_RESULTS_PER_REQUEST

    results: list[YahooItem] = []
    start = 1

    while len(results) < max_items and start <= max_start:
        remaining = max_items - len(results)
        fetch_count = min(remaining, _MAX_RESULTS_PER_REQUEST)

        try:
            response = _fetch_page(config, condition, fetch_count, start)
        except requests.RequestException:
            logging.exception("[Yahoo] API エラー")
            break

        hits = response.get("hits", [])
        if not hits:
            logging.info("[Yahoo] 該当なし")
            break

        total_results = response.get("totalResultsAvailable", 0)
        logging.debug(
            "[Yahoo] API応答: %d/%d 件取得",
            len(hits),
            total_results,
        )

        for hit in hits:
            if len(results) >= max_items:
                break
            try:
                item = YahooItem.parse(hit)
                results.append(item)
            except (KeyError, ValueError):
                logging.exception("[Yahoo] パース失敗: name=%s", hit.get("name", "unknown"))
                continue

        # 次のページがない場合は終了
        if start + len(hits) > total_results:
            break

        start += len(hits)

        # レート制限対策
        time.sleep(_RATE_LIMIT_WAIT_SEC)

    logging.info("[Yahoo] 検索完了: %d 件", len(results))
    return results


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    keyword = args["-k"]
    jan = args["-j"]
    price_min_str = args["-m"]
    price_max_str = args["-M"]
    max_count_str = args["-n"]
    condition_str = args["--condition"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)

    price_min = int(price_min_str) if price_min_str else None
    price_max = int(price_max_str) if price_max_str else None
    max_count = int(max_count_str) if max_count_str else 10
    condition = Condition(condition_str) if condition_str else Condition.NEW

    search_condition = SearchCondition(
        keyword=keyword,
        jan=jan,
        price_min=price_min,
        price_max=price_max,
        condition=condition,
    )

    logging.info("検索条件: %s", search_condition)

    results = search(
        YahooApiConfig.parse(config["store"]["yahoo"]),
        search_condition,
        max_items=max_count,
    )

    logging.info("=" * 60)
    logging.info("検索結果: %d 件", len(results))
    logging.info("=" * 60)

    for i, item in enumerate(results, 1):
        logging.info("[%d] %s", i, item.name)
        logging.info("    価格: ¥%s", f"{item.price:,}")
        logging.info("    URL: %s", item.url)
        if item.seller_name:
            logging.info("    店舗: %s", item.seller_name)
