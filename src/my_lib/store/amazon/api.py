#!/usr/bin/env python3
"""
Amazon の PA-API 5.0 を使って Amazon の価格情報を取得するライブラリです。

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

import paapi5_python_sdk.api.default_api
import paapi5_python_sdk.condition
import paapi5_python_sdk.get_items_request
import paapi5_python_sdk.get_items_resource
import paapi5_python_sdk.merchant
import paapi5_python_sdk.partner_type
import paapi5_python_sdk.search_items_request
import paapi5_python_sdk.search_items_resource

from my_lib.store.amazon.config import AmazonApiConfig, AmazonItem, SearchResultItem
from my_lib.store.amazon.util import get_item_url

if TYPE_CHECKING:
    from typing import Any

_PAAPI_SPLIT: int = 10


def _get_paapi(config: AmazonApiConfig) -> paapi5_python_sdk.api.default_api.DefaultApi:
    return paapi5_python_sdk.api.default_api.DefaultApi(
        access_key=config.access_key,
        secret_key=config.secret_key,
        host=config.host,
        region=config.region,
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


def _fetch_price_outlet(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    if len(asin_list) == 0:
        return {}

    logging.info("[Amazon] 検索開始 (アウトレット): ASIN=%s", _format_asin_list(asin_list))

    default_api = _get_paapi(config)

    price_map: dict[str, AmazonItem] = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : (i + _PAAPI_SPLIT)] for i in range(0, len(asin_list), _PAAPI_SPLIT)]
    ):
        if i != 0:
            time.sleep(1)

        resp: Any = default_api.get_items(
            paapi5_python_sdk.get_items_request.GetItemsRequest(
                partner_tag=config.associate,
                partner_type=paapi5_python_sdk.partner_type.PartnerType.ASSOCIATES,
                marketplace="www.amazon.co.jp",
                # NOTE: listings にアウトレットが表示されるようにする
                # (他に安価な中古品の出品がある場合は表示されない)
                condition=paapi5_python_sdk.condition.Condition.USED,
                merchant=paapi5_python_sdk.merchant.Merchant.ALL,
                item_ids=asin_sub_list,
                resources=[
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_SUMMARIES_LOWESTPRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_SUMMARIES_HIGHESTPRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_LISTINGS_PRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_LISTINGS_MERCHANTINFO,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.ITEMINFO_TITLE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.ITEMINFO_CLASSIFICATIONS,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.IMAGES_PRIMARY_MEDIUM,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.IMAGES_PRIMARY_SMALL,
                ],
            )
        )

        if resp.items_result is not None:
            for item_data in resp.items_result.items:
                if item_data.offers is None:
                    continue

                price: int | None = None

                # NOTE: Amazonアウトレットのみ対象にする
                for listing in item_data.offers.listings:
                    if listing.merchant_info is None or not re.compile("Amazonアウトレット").search(
                        listing.merchant_info.name
                    ):
                        continue
                    price = int(listing.price.amount)
                    break

                if price is None:
                    continue

                item = AmazonItem(
                    asin=item_data.asin,
                    url=get_item_url(item_data.asin),
                    price=price,
                    thumb_url=item_data.images.primary.medium.url,
                )
                _set_item_name(item, item_data)
                _set_item_category(item, item_data)

                price_map[item_data.asin] = item

    return price_map


def fetch_price_new(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    if len(asin_list) == 0:
        return {}

    logging.info("[Amazon] 検索開始 (新品): ASIN=%s", _format_asin_list(asin_list))

    default_api = _get_paapi(config)

    price_map: dict[str, AmazonItem] = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : i + _PAAPI_SPLIT] for i in range(0, len(asin_list), _PAAPI_SPLIT)]
    ):
        if i != 0:
            time.sleep(1)

        resp: Any = default_api.get_items(
            paapi5_python_sdk.get_items_request.GetItemsRequest(
                partner_tag=config.associate,
                partner_type=paapi5_python_sdk.partner_type.PartnerType.ASSOCIATES,
                marketplace="www.amazon.co.jp",
                condition=paapi5_python_sdk.condition.Condition.NEW,
                merchant=paapi5_python_sdk.merchant.Merchant.ALL,
                item_ids=asin_sub_list,
                resources=[
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_SUMMARIES_LOWESTPRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_SUMMARIES_HIGHESTPRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_LISTINGS_PRICE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.OFFERS_LISTINGS_MERCHANTINFO,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.ITEMINFO_TITLE,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.ITEMINFO_CLASSIFICATIONS,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.IMAGES_PRIMARY_MEDIUM,
                    paapi5_python_sdk.get_items_resource.GetItemsResource.IMAGES_PRIMARY_SMALL,
                ],
            )
        )

        if resp.items_result is not None:
            for item_data in resp.items_result.items:
                if item_data.offers is None:
                    continue

                price: int | None = None

                for offer in item_data.offers.summaries:
                    if offer.condition.value != "New":
                        continue

                    try:
                        fetched_price = int(offer.lowest_price.amount)
                        if (price is None) or (fetched_price < price):
                            price = fetched_price
                        break
                    except Exception:
                        logging.exception("[Amazon] 価格取得失敗: ASIN=%s", item_data.asin)

                if price is None:
                    continue

                item = AmazonItem(
                    asin=item_data.asin,
                    url=get_item_url(item_data.asin),
                    price=price,
                    thumb_url=item_data.images.primary.medium.url,
                )
                _set_item_name(item, item_data)
                _set_item_category(item, item_data)

                price_map[item_data.asin] = item

    return price_map


_PAAPI_CALL_INTERVAL_SEC: int = 5


def fetch_price(config: AmazonApiConfig, asin_list: list[str]) -> dict[str, AmazonItem]:
    price_map = _fetch_price_outlet(config, asin_list)

    # PA-API のレート制限対策として呼び出し間隔を確保
    remaining_asin_list = list(set(asin_list) - set(price_map.keys()))
    if remaining_asin_list:
        time.sleep(_PAAPI_CALL_INTERVAL_SEC)
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
        config: PA-API 設定
        keywords: 検索キーワード
        item_count: 取得件数（1-10、デフォルト10）

    Returns:
        検索結果リスト
    """
    logging.info("[Amazon] キーワード検索開始: %s", keywords)

    default_api = _get_paapi(config)

    request = paapi5_python_sdk.search_items_request.SearchItemsRequest(
        partner_tag=config.associate,
        partner_type=paapi5_python_sdk.partner_type.PartnerType.ASSOCIATES,
        keywords=keywords,
        item_count=item_count,
        resources=[
            paapi5_python_sdk.search_items_resource.SearchItemsResource.ITEMINFO_TITLE,
            paapi5_python_sdk.search_items_resource.SearchItemsResource.OFFERS_LISTINGS_PRICE,
            paapi5_python_sdk.search_items_resource.SearchItemsResource.IMAGES_PRIMARY_SMALL,
        ],
    )

    results: list[SearchResultItem] = []

    try:
        resp: Any = default_api.search_items(request)

        if resp.search_result is not None:
            for item_data in resp.search_result.items:
                title: str | None = None
                price: int | None = None
                thumb_url: str | None = None

                try:
                    title = item_data.item_info.title.display_value
                except Exception:
                    logging.warning("[Amazon] 商品名取得失敗: ASIN=%s", item_data.asin)

                if title is None:
                    continue

                try:
                    if item_data.offers and item_data.offers.listings:
                        price = int(item_data.offers.listings[0].price.amount)
                except Exception:
                    logging.debug("[Amazon] 価格取得失敗: ASIN=%s", item_data.asin)

                try:
                    thumb_url = item_data.images.primary.small.url
                except Exception:
                    logging.debug("[Amazon] サムネイル取得失敗: ASIN=%s", item_data.asin)

                results.append(
                    SearchResultItem(
                        name=title,
                        asin=item_data.asin,
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
