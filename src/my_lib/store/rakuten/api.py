#!/usr/bin/env python3
"""
楽天市場検索ライブラリ

https://webservice.rakuten.co.jp/documentation/ichiba-item-search を使用して商品を検索し、
タイトル、URL、価格のリストを取得します。

Usage:
  api.py [-c CONFIG] [-k KEYWORD] [-e EXCLUDE] [-m MIN] [-M MAX]
         [-n COUNT] [-D]

Options:
  -c CONFIG           : 設定ファイル。[default: config.yaml]
  -k KEYWORD          : 検索キーワード。[default: iPhone]
  -e EXCLUDE          : 除外キーワード。
  -m MIN              : 最低価格。
  -M MAX              : 最高価格。
  -n COUNT            : 取得する最大件数。[default: 10]
  -D                  : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

import requests

from my_lib.store.rakuten.config import RakutenApiConfig, RakutenItem


class SortOrder(Enum):
    """ソート順"""

    STANDARD = "standard"  # 楽天標準ソート（デフォルト）
    PRICE_ASC = "+itemPrice"  # 価格の安い順
    PRICE_DESC = "-itemPrice"  # 価格の高い順
    REVIEW_COUNT_DESC = "-reviewCount"  # レビュー件数順
    REVIEW_AVERAGE_DESC = "-reviewAverage"  # レビュー評価順
    UPDATE_DESC = "-updateTimestamp"  # 更新日時順


@dataclass(frozen=True)
class SearchCondition:
    """検索条件"""

    keyword: str
    exclude_keyword: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    sort: SortOrder = SortOrder.PRICE_ASC
    in_stock: bool = True
    genre_id: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        sort_value = data.get("sort", "+itemPrice")
        sort = SortOrder(sort_value) if sort_value else SortOrder.PRICE_ASC

        return cls(
            keyword=data["keyword"],
            exclude_keyword=data.get("exclude_keyword"),
            price_min=data.get("price_min"),
            price_max=data.get("price_max"),
            sort=sort,
            in_stock=data.get("in_stock", True),
            genre_id=data.get("genre_id"),
        )


_API_ENDPOINT: str = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
_MAX_RESULTS_PER_REQUEST: int = 30
_MAX_PAGE: int = 100
_RATE_LIMIT_WAIT_SEC: float = 1.0


def _build_params(
    config: RakutenApiConfig,
    condition: SearchCondition,
    hits: int,
    page: int,
) -> dict[str, Any]:
    """API リクエストパラメータを構築する

    Args:
        config: API 設定
        condition: 検索条件
        hits: 取得件数
        page: ページ番号

    Returns:
        API パラメータ辞書

    """
    params: dict[str, Any] = {
        "applicationId": config.application_id,
        "keyword": condition.keyword,
        "hits": min(hits, _MAX_RESULTS_PER_REQUEST),
        "page": page,
        "sort": condition.sort.value,
        "formatVersion": 2,
        "imageFlag": 1,
    }

    if config.affiliate_id:
        params["affiliateId"] = config.affiliate_id

    if condition.exclude_keyword:
        params["NGKeyword"] = condition.exclude_keyword

    if condition.price_min is not None:
        params["minPrice"] = condition.price_min

    if condition.price_max is not None:
        params["maxPrice"] = condition.price_max

    if condition.in_stock:
        params["availability"] = 1

    if condition.genre_id:
        params["genreId"] = condition.genre_id

    return params


def _fetch_page(
    config: RakutenApiConfig,
    condition: SearchCondition,
    hits: int,
    page: int,
) -> dict[str, Any]:
    """API を呼び出して1ページ分の結果を取得する

    Args:
        config: API 設定
        condition: 検索条件
        hits: 取得件数
        page: ページ番号

    Returns:
        API レスポンス（JSON）

    Raises:
        requests.RequestException: API 呼び出しに失敗した場合

    """
    params = _build_params(config, condition, hits, page)

    logging.debug("[Rakuten] API リクエスト: %s, params=%s", _API_ENDPOINT, params)

    response = requests.get(_API_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def search(
    config: RakutenApiConfig,
    condition: SearchCondition,
    max_items: int | None = None,
) -> list[RakutenItem]:
    """楽天市場で商品を検索する

    Args:
        config: API 設定
        condition: 検索条件
        max_items: 取得する最大件数（None の場合は 30 件）

    Returns:
        検索結果のリスト

    """
    if max_items is None:
        max_items = _MAX_RESULTS_PER_REQUEST

    logging.info("[Rakuten] 検索開始: keyword=%s", condition.keyword)

    results: list[RakutenItem] = []
    page = 1

    while len(results) < max_items and page <= _MAX_PAGE:
        remaining = max_items - len(results)
        fetch_count = min(remaining, _MAX_RESULTS_PER_REQUEST)

        try:
            response = _fetch_page(config, condition, fetch_count, page)
        except requests.RequestException:
            logging.exception("[Rakuten] API エラー")
            break

        items = response.get("Items", [])
        if not items:
            logging.info("[Rakuten] 該当なし")
            break

        total_count = response.get("count", 0)
        page_count = response.get("pageCount", 0)
        logging.debug(
            "[Rakuten] API応答: %d/%d 件取得 (page %d/%d)",
            len(items),
            total_count,
            page,
            page_count,
        )

        for item_data in items:
            if len(results) >= max_items:
                break
            try:
                item = RakutenItem.parse(item_data)
                results.append(item)
            except (KeyError, ValueError):
                logging.exception("[Rakuten] パース失敗: name=%s", item_data.get("itemName", "unknown"))
                continue

        # 次のページがない場合は終了
        if page >= page_count:
            break

        page += 1

        # レート制限対策
        time.sleep(_RATE_LIMIT_WAIT_SEC)

    logging.info("[Rakuten] 検索完了: %d 件", len(results))
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
    exclude_keyword = args["-e"]
    price_min_str = args["-m"]
    price_max_str = args["-M"]
    max_count_str = args["-n"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)

    price_min = int(price_min_str) if price_min_str else None
    price_max = int(price_max_str) if price_max_str else None
    max_count = int(max_count_str) if max_count_str else 10

    search_condition = SearchCondition(
        keyword=keyword,
        exclude_keyword=exclude_keyword,
        price_min=price_min,
        price_max=price_max,
    )

    logging.info("検索条件: %s", search_condition)

    results = search(
        RakutenApiConfig.parse(config["store"]["rakuten"]),
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
        if item.shop_name:
            logging.info("    店舗: %s", item.shop_name)
