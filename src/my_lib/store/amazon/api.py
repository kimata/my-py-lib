#!/usr/bin/env python3
"""
Amazon の Creators API を使って Amazon の価格情報を取得するライブラリです。

Usage:
  api.py [-c CONFIG] [-t ASIN...] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -t ASIN           : 価格情報を取得する ASIN。[default: B01MUZOWBH]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any

import amazon_creatorsapi
import amazon_creatorsapi.models

from my_lib.store.amazon.config import AmazonApiConfig, AmazonItem, SearchResultItem
from my_lib.store.amazon.util import get_item_url

if TYPE_CHECKING:
    from typing import Any

_API_SPLIT: int = 10

_API_CALL_INTERVAL_SEC: int = 5

_GET_ITEMS_RESOURCES: list[amazon_creatorsapi.models.GetItemsResource] = [
    amazon_creatorsapi.models.GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_PRICE,
    amazon_creatorsapi.models.GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_MERCHANT_INFO,
    amazon_creatorsapi.models.GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_CONDITION,
    amazon_creatorsapi.models.GetItemsResource.ITEM_INFO_DOT_TITLE,
    amazon_creatorsapi.models.GetItemsResource.ITEM_INFO_DOT_CLASSIFICATIONS,
    amazon_creatorsapi.models.GetItemsResource.IMAGES_DOT_PRIMARY_DOT_MEDIUM,
    amazon_creatorsapi.models.GetItemsResource.IMAGES_DOT_PRIMARY_DOT_SMALL,
]


def _get_api(config: AmazonApiConfig) -> amazon_creatorsapi.AmazonCreatorsApi:
    return amazon_creatorsapi.AmazonCreatorsApi(
        credential_id=config.credential_id,
        credential_secret=config.credential_secret,
        version=config.version,
        tag=config.associate,
        country=amazon_creatorsapi.Country.JP,
        throttling=1,
    )


def _set_item_name(item: AmazonItem, data: Any) -> None:
    try:
        item.name = data.item_info.title.display_value
    except Exception:
        logging.warning("[Amazon] 商品名取得失敗: ASIN=%s", item.asin)


def _set_item_category(item: AmazonItem, data: Any) -> None:
    try:
        item.category = data.item_info.classifications.product_group.display_value
    except Exception:
        logging.warning("[Amazon] カテゴリ取得失敗: ASIN=%s", item.asin)


def _format_asin_list(asin_list: list[str], max_display: int = 3) -> str:
    """ASIN リストをログ用にフォーマットする"""
    if len(asin_list) <= max_display:
        return ", ".join(asin_list)
    return ", ".join(asin_list[:max_display]) + f"... (他 {len(asin_list) - max_display} 件)"


def _get_thumb_url(item_data: Any) -> str | None:
    try:
        return item_data.images.primary.medium.url
    except Exception:
        return None


def _fetch_price_outlet(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    """Amazonアウトレットの価格を取得する.

    Creators API には USED condition がないため、ANY で取得し
    listings から「Amazonアウトレット」の出品を探す。
    """
    if len(asin_list) == 0:
        return {}

    logging.info("[Amazon] 検索開始 (アウトレット): ASIN=%s", _format_asin_list(asin_list))

    api = _get_api(config)

    price_map: dict[str, AmazonItem] = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : (i + _API_SPLIT)] for i in range(0, len(asin_list), _API_SPLIT)]
    ):
        if i != 0:
            time.sleep(1)

        items: Any = api.get_items(
            items=asin_sub_list,
            condition=amazon_creatorsapi.models.Condition.ANY,
            resources=_GET_ITEMS_RESOURCES,
        )

        if items is not None:
            for item_data in items:
                asin: Any = item_data.asin
                if asin is None:
                    continue
                if item_data.offers_v2 is None or item_data.offers_v2.listings is None:
                    continue

                price: int | None = None

                # NOTE: Amazonアウトレットのみ対象にする
                for listing in item_data.offers_v2.listings:
                    if listing.merchant_info is None:
                        continue
                    merchant_name: Any = listing.merchant_info.name
                    if merchant_name is None or not re.search("Amazonアウトレット", merchant_name):
                        continue
                    amount: Any = listing.price.money.amount
                    if amount is not None:
                        price = int(amount)
                    break

                if price is None:
                    continue

                item = AmazonItem(
                    asin=asin,
                    url=get_item_url(asin),
                    price=price,
                    thumb_url=_get_thumb_url(item_data),
                )
                _set_item_name(item, item_data)
                _set_item_category(item, item_data)

                price_map[asin] = item

    return price_map


def fetch_price_new(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    if len(asin_list) == 0:
        return {}

    logging.info("[Amazon] 検索開始 (新品): ASIN=%s", _format_asin_list(asin_list))

    api = _get_api(config)

    price_map: dict[str, AmazonItem] = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : i + _API_SPLIT] for i in range(0, len(asin_list), _API_SPLIT)]
    ):
        if i != 0:
            time.sleep(1)

        items: Any = api.get_items(
            items=asin_sub_list,
            condition=amazon_creatorsapi.models.Condition.NEW,
            resources=_GET_ITEMS_RESOURCES,
        )

        if items is not None:
            for item_data in items:
                asin: Any = item_data.asin
                if asin is None:
                    continue
                if item_data.offers_v2 is None or item_data.offers_v2.listings is None:
                    continue

                price: int | None = None

                # listings から新品の最安値を取得
                for listing in item_data.offers_v2.listings:
                    try:
                        amount: Any = listing.price.money.amount
                        if amount is None:
                            continue
                        fetched_price = int(amount)
                        if (price is None) or (fetched_price < price):
                            price = fetched_price
                    except Exception:
                        logging.exception("[Amazon] 価格取得失敗: ASIN=%s", asin)

                if price is None:
                    continue

                item = AmazonItem(
                    asin=asin,
                    url=get_item_url(asin),
                    price=price,
                    thumb_url=_get_thumb_url(item_data),
                )
                _set_item_name(item, item_data)
                _set_item_category(item, item_data)

                price_map[asin] = item

    return price_map


def fetch_price(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    price_map = _fetch_price_outlet(config, asin_list)

    # レート制限対策として呼び出し間隔を確保
    remaining_asin_list = list(set(asin_list) - set(price_map.keys()))
    if remaining_asin_list:
        time.sleep(_API_CALL_INTERVAL_SEC)
        price_map |= fetch_price_new(config, remaining_asin_list)

    if len(price_map) == 0:
        logging.info("[Amazon] 該当なし")
    else:
        logging.info("[Amazon] 検索完了: %d 件", len(price_map))

    return price_map


def check_item_list(config: AmazonApiConfig, item_list: list[AmazonItem]) -> list[AmazonItem]:
    try:
        price_map = fetch_price(config, [item.asin for item in item_list])
        for item in item_list:
            if item.asin in price_map:
                item.stock = 1
                item.name = price_map[item.asin].name
                item.price = price_map[item.asin].price
                item.thumb_url = price_map[item.asin].thumb_url
            else:
                item.stock = 0
        return item_list
    except Exception:
        logging.exception("[Amazon] 価格取得エラー")
        return []


def search_items(
    config: AmazonApiConfig,
    keywords: str,
    item_count: int = 10,
) -> list[SearchResultItem]:
    """キーワードで Amazon 商品を検索する.

    Args:
        config: Creators API 設定
        keywords: 検索キーワード
        item_count: 取得件数（1-10、デフォルト10）

    Returns:
        検索結果リスト
    """
    logging.info("[Amazon] キーワード検索開始: %s", keywords)

    api = _get_api(config)

    results: list[SearchResultItem] = []

    try:
        resp: Any = api.search_items(
            keywords=keywords,
            item_count=item_count,
            resources=[
                amazon_creatorsapi.models.SearchItemsResource.ITEM_INFO_DOT_TITLE,
                amazon_creatorsapi.models.SearchItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_PRICE,
                amazon_creatorsapi.models.SearchItemsResource.IMAGES_DOT_PRIMARY_DOT_SMALL,
            ],
        )

        if resp is not None and resp.items is not None:
            for item_data in resp.items:
                asin: Any = item_data.asin
                if asin is None:
                    continue

                title: str | None = None
                price: int | None = None
                thumb_url: str | None = None

                try:
                    title = item_data.item_info.title.display_value
                except Exception:
                    logging.warning("[Amazon] 商品名取得失敗: ASIN=%s", asin)

                if title is None:
                    continue

                try:
                    if item_data.offers_v2 and item_data.offers_v2.listings:
                        amount: Any = item_data.offers_v2.listings[0].price.money.amount
                        if amount is not None:
                            price = int(amount)
                except Exception:
                    logging.debug("[Amazon] 価格取得失敗: ASIN=%s", asin)

                try:
                    thumb_url = item_data.images.primary.small.url
                except Exception:
                    logging.debug("[Amazon] サムネイル取得失敗: ASIN=%s", asin)

                results.append(
                    SearchResultItem(
                        name=title,
                        asin=asin,
                        price=price,
                        thumb_url=thumb_url,
                    )
                )
    except Exception:
        logging.exception("[Amazon] キーワード検索エラー: %s", keywords)

    logging.info("[Amazon] キーワード検索完了: %d 件", len(results))

    return results


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    asin_list = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)

    logging.info(
        fetch_price(
            AmazonApiConfig.parse(config["store"]["amazon"]),
            asin_list,
        )
    )
