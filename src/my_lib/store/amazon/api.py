#!/usr/bin/env python3
"""
Amazon の PA-API 5.0 を使って Amazon の価格情報を取得するライブラリです。

Usage:
  api.py [-c CONFIG] [-t ASIN...] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -t ASIN           : 価格情報を取得する ASIN。[default: B01MUZOWBH]
  -D                : デバッグモードで動作します。
"""

import logging
import re
import time

import paapi5_python_sdk.api.default_api
import paapi5_python_sdk.condition
import paapi5_python_sdk.get_items_request
import paapi5_python_sdk.get_items_resource
import paapi5_python_sdk.merchant
import paapi5_python_sdk.partner_type

PAAPI_SPLIT = 10


def get_paapi(config):
    return paapi5_python_sdk.api.default_api.DefaultApi(
        access_key=config["store"]["amazon"]["access_key"],
        secret_key=config["store"]["amazon"]["secret_key"],
        host=config["store"]["amazon"]["host"],
        region=config["store"]["amazon"]["region"],
    )


def item_prop(item, data):
    try:
        item["category"] = data.item_info.classifications.product_group.display_value
    except Exception:
        logging.warning("Unable to get category of %s.", item["asin"])

    item["thumb_url"] = data.images.primary.medium.url


def fetch_price_outlet(config, asin_list):
    if len(asin_list) == 0:
        return {}

    logging.info("PA-API GetItems: ASIN = [ %s ]", ", ".join(asin_list))

    default_api = get_paapi(config)

    price_map = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : (i + PAAPI_SPLIT)] for i in range(0, len(asin_list), PAAPI_SPLIT)]
    ):
        if i != 0:
            time.sleep(10)

        resp = default_api.get_items(
            paapi5_python_sdk.get_items_request.GetItemsRequest(
                partner_tag=config["store"]["amazon"]["associate"],
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

                item = {}

                # NOTE: Amazonアウトレットのみ対象にする
                for listing in item_data.offers.listings:
                    if listing.merchant_info is None or not re.compile("Amazonアウトレット").search(
                        listing.merchant_info.name
                    ):
                        continue
                    item["price"] = int(listing.price.amount)
                    break

                if "price" not in item:
                    continue

                item_prop(item, item_data)

                price_map[item_data.asin] = item

    return price_map


def fetch_price_new(config, asin_list):  # noqa: C901
    if len(asin_list) == 0:
        return {}

    logging.info("PA-API GetItems: ASIN = [ %s ]", ", ".join(asin_list))

    default_api = paapi5_python_sdk.api.default_api.DefaultApi(
        access_key=config["store"]["amazon"]["access_key"],
        secret_key=config["store"]["amazon"]["secret_key"],
        host=config["store"]["amazon"]["host"],
        region=config["store"]["amazon"]["region"],
    )

    price_map = {}
    for i, asin_sub_list in enumerate(
        [asin_list[i : i + PAAPI_SPLIT] for i in range(0, len(asin_list), PAAPI_SPLIT)]
    ):
        if i != 0:
            time.sleep(10)

        resp = default_api.get_items(
            paapi5_python_sdk.get_items_request.GetItemsRequest(
                partner_tag=config["store"]["amazon"]["associate"],
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

                item = {}

                for offer in item_data.offers.summaries:
                    if offer.condition.value != "New":
                        continue

                    try:
                        price = int(offer.lowest_price.amount)
                        if ("price" not in item) or (price < item["price"]):
                            item["price"] = price
                        break
                    except Exception:
                        logging.exception("Failed to fetch price: %s", item_data.asin)

                if "price" not in item:
                    continue

                item_prop(item, item_data)

                item["thumb_url"] = item_data.images.primary.medium.url

                price_map[item_data.asin] = item

    return price_map


def fetch_price(config, asin_list):
    price_map = fetch_price_outlet(config, asin_list)
    price_map |= fetch_price_new(config, list(set(asin_list) - set(price_map.keys())))

    return price_map


def check_item_list(config, item_list):
    try:
        price_map = fetch_price(config, [item["asin"] for item in item_list])
        for item in item_list:
            if item["asin"] in price_map:
                item["stock"] = 1
                item["price"] = price_map[item["asin"]]["price"]
                item["thumb_url"] = price_map[item["asin"]]["thumb_url"]
            else:
                item["stock"] = 0
        return item_list
    except Exception:
        logging.exception("Failed to fetch price")
        return []


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    asin_list = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    logging.info(
        fetch_price(
            config,
            asin_list,
        )
    )
