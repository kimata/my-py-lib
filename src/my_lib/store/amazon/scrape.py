#!/usr/bin/env python3
"""
スクレイピングで Amazon の価格情報を取得するライブラリです。

Usage:
  scrape.py [-c CONFIG] [-t ASIN] [-s DATA_PATH] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -t ASIN           : 価格情報を取得する ASIN。[default: B01MUZOWBH]
  -s DATA_PATH      : Selenium で使うブラウザのデータを格納するディレクトリ。[default: data]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import io
import json
import logging
import pathlib
import random
import re
import time
import traceback
from typing import TYPE_CHECKING

import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.amazon.captcha
from my_lib.store.amazon.config import AmazonItem

if TYPE_CHECKING:
    from typing import Any

# デフォルトのSlack設定（空設定）
_DEFAULT_SLACK_CONFIG: my_lib.notify.slack.SlackEmptyConfig = my_lib.notify.slack.SlackEmptyConfig()

# Amazonアウトレット判定用のXPath
# node=2761990051 は Amazonアウトレット専用ページへのリンク
_AMAZON_OUTLET_SELLER_XPATH = '//div[@id="merchant-info"]//a[contains(@href, "node=2761990051")]'

# 価格データJSON用のXPath
_PRICE_DATA_XPATH = '//div[contains(@class, "twister-plus-buying-options-price-data")]'


def _extract_outlet_price_from_json(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> int | None:
    """ページ内のJSON価格データからアウトレット価格（USED）を取得する.

    Returns:
        アウトレット価格。取得できない場合は None
    """
    try:
        elems = driver.find_elements(selenium.webdriver.common.by.By.XPATH, _PRICE_DATA_XPATH)
        if not elems:
            return None

        inner_html = elems[0].get_attribute("innerHTML")
        if not inner_html:
            return None

        data = json.loads(inner_html)
        for item in data.get("desktop_buybox_group_1", []):
            if item.get("buyingOptionType") == "USED":
                return int(item["priceAmount"])
    except (json.JSONDecodeError, KeyError, ValueError):
        logging.debug("Failed to extract outlet price from JSON")
    return None


def _fetch_price_impl(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    slack_config: my_lib.notify.slack.HasErrorConfig | my_lib.notify.slack.SlackEmptyConfig,
    item: AmazonItem,
) -> bool:
    """価格情報を取得して item を更新する.

    Returns:
        True: 正常に処理完了（価格取得成功または在庫切れ）
        False: ページ読み込み失敗
    """
    PRICE_ELEM_LIST: list[dict[str, str]] = [
        {
            "xpath": '//span[contains(@class, "apexPriceToPay")]/span[@aria-hidden]',
            "type": "html",
        },
        {
            "xpath": '//span[contains(@class, "priceToPay")]/span[@aria-hidden]',
            "type": "text",
        },
        {
            "xpath": '//span[contains(@class, "priceBlockBuyingPriceString")]',
            "type": "text",
        },
    ]

    if (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, '//b[@class="h1" and contains(text(), "ご迷惑")]'
            )
        )
        != 0
    ):
        logging.warning("Failed to load page: %s", item.url)
        time.sleep(5)
        return False

    my_lib.selenium_util.click_xpath(driver, '//span[@id="black-curtain-yes-button"]', is_warn=False)
    my_lib.selenium_util.click_xpath(
        driver,
        '//span[contains(@class, "a-button")]//button[normalize-space(text()) = "ショッピングを続ける"]',
        is_warn=False,
    )

    # my_lib.store.amazon.captcha.resolve(driver, wait, config)

    try:
        breadcrumb_list = driver.find_elements(
            selenium.webdriver.common.by.By.XPATH, "//div[contains(@class, 'a-breadcrumb')]//li//a"
        )
        item.category = next(x.text for x in breadcrumb_list)
    except Exception:
        logging.exception("Failed to fetch category")

    price_text = ""
    for price_elem in PRICE_ELEM_LIST:
        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, price_elem["xpath"])) == 0:
            continue

        logging.debug('xpath: "%s', price_elem["xpath"])

        if price_elem["type"] == "html":
            inner_html = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, price_elem["xpath"]
            ).get_attribute("innerHTML")
            if inner_html is not None:
                price_text = inner_html.strip()
        else:
            price_text = driver.find_element(selenium.webdriver.common.by.By.XPATH, price_elem["xpath"]).text
        break

    if price_text == "":
        if (
            len(
                driver.find_elements(
                    selenium.webdriver.common.by.By.XPATH, '//span[contains(@class, "a-color-price")]'
                )
            )
            != 0
        ):
            price_text = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, '//span[contains(@class, "a-color-price")]'
            ).text
            if price_text in {"現在在庫切れです。", "この商品は現在お取り扱いできません。"}:
                logging.warning("Price is NOT displayed: %s", item.url)
                item.price = 0
                return True
        elif (
            len(
                driver.find_elements(
                    selenium.webdriver.common.by.By.XPATH,
                    (
                        '//div[contains(@class, "a-box-inner") and contains(@class, "a-padding-medium")]'
                        '/span[contains(text(), "ありません")]'
                    ),
                )
            )
            != 0
        ):
            item.price = 0
            return True
        else:
            logging.warning("Unable to fetch price: %s", item.url)

            my_lib.notify.slack.error_with_image(
                slack_config,
                "価格取得に失敗",
                f"{item.url}\nprice_text='{price_text}'",
                my_lib.notify.slack.AttachImage(
                    data=PIL.Image.open(io.BytesIO(driver.get_screenshot_as_png())),
                    text="スクリーンショット",
                ),
            )
            item.price = 0
            return True

    try:
        m = re.match(r".*?(\d{1,3}(?:,\d{3})*)", re.sub(r"[^0-9][0-9]+個", "", price_text))
        if m is None:
            raise ValueError(f"Failed to parse price: {price_text}")
        item.price = int(m.group(1).replace(",", ""))

        # buybox が Amazonアウトレットの場合、outlet_price を取得
        # NOTE: buybox が新品の場合、「その他の出品者」にあるアウトレット価格は取得されない
        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, _AMAZON_OUTLET_SELLER_XPATH)) > 0:
            # JSONデータから USED 価格を取得（新品とアウトレットが混在する場合に対応）
            outlet_price = _extract_outlet_price_from_json(driver)
            if outlet_price is not None:
                item.outlet_price = outlet_price
                logging.debug("Amazon Outlet price from JSON: %d", item.outlet_price)
            else:
                # JSONデータがない場合はbuybox価格を使用
                item.outlet_price = item.price
                logging.debug("Amazon Outlet price from buybox: %d", item.outlet_price)
    except Exception:
        logging.warning('Unable to parse "%s": %s.', price_text, item.url)

        my_lib.notify.slack.error_with_image(
            slack_config,
            "価格取得に失敗",
            f"{item.url}\n{traceback.format_exc()}",
            my_lib.notify.slack.AttachImage(
                data=PIL.Image.open(io.BytesIO(driver.get_screenshot_as_png())),
                text="スクリーンショット",
            ),
        )
        item.price = 0
        return True

    return True


def fetch_price(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    item: AmazonItem,
    slack_config: my_lib.notify.slack.HasErrorConfig
    | my_lib.notify.slack.SlackEmptyConfig = _DEFAULT_SLACK_CONFIG,
    dump_path: pathlib.Path | None = None,
) -> AmazonItem:
    try:
        with my_lib.selenium_util.browser_tab(driver, item.url):
            wait.until(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (
                        selenium.webdriver.common.by.By.XPATH,
                        '//div[contains(@class, "footer") or contains(@class, "Footer")]',
                    )
                )
            )

            _fetch_price_impl(driver, wait, slack_config, item)

            if dump_path is not None and (item.price is None or item.price == 0):
                my_lib.selenium_util.dump_page(
                    driver,
                    int(random.random() * 100),  # noqa: S311
                    dump_path,
                )
    except Exception:
        logging.exception("Failed to fetch price")

    return item


if __name__ == "__main__":
    # TEST Code
    import docopt
    import selenium.webdriver.support.wait

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import my_lib.selenium_util

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    data_path = args["-s"]
    asin = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(data_path))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 2)

    slack_config_parsed = my_lib.notify.slack.SlackConfig.parse(config.get("slack", {}))
    slack_config: my_lib.notify.slack.HasErrorConfig | my_lib.notify.slack.SlackEmptyConfig = (
        slack_config_parsed
        if isinstance(
            slack_config_parsed,
            my_lib.notify.slack.SlackConfig
            | my_lib.notify.slack.SlackErrorInfoConfig
            | my_lib.notify.slack.SlackErrorOnlyConfig,
        )
        else my_lib.notify.slack.SlackEmptyConfig()
    )

    dump_path = (
        pathlib.Path(config["data"]["dump"]) if "data" in config and "dump" in config["data"] else None
    )

    item = AmazonItem.from_asin(asin)
    logging.info(my_lib.pretty.format(fetch_price(driver, wait, item, slack_config, dump_path).to_dict()))
