#!/usr/bin/env python3
"""
ヨドバシ.com 商品ページスクレイピングライブラリ

商品ページから価格、サムネイル画像URL、在庫情報を取得します。

Usage:
  scrape.py [-u URL] [-s DATA_PATH] [-D]

Options:
  -u URL        : 商品ページのURL。
                  [default: https://www.yodobashi.com/product/100000001005876339/]
  -s DATA_PATH  : Selenium で使うブラウザのデータを格納するディレクトリ。
                  [default: data]
  -D            : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support.expected_conditions

import my_lib.selenium_util

if TYPE_CHECKING:
    from typing import Any

    import selenium.webdriver.remote.webdriver
    import selenium.webdriver.support.wait


# XPath 定義
_PRICE_XPATH: str = '//span[@id="js_scl_unitPrice"]'
_THUMBNAIL_XPATH: str = '//input[@class="largeUrl"]'
_OUT_OF_STOCK_XPATH: str = '//p[contains(., "販売休止") or contains(., "販売を終了しました")]'
_TITLE_XPATH: str = '//h1//span[@itemprop="name"]'


@dataclass(frozen=True)
class ProductInfo:
    """商品ページから取得した情報"""

    title: str
    price: int | None
    thumbnail_url: str | None
    in_stock: bool

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        return cls(
            title=data["title"],
            price=data.get("price"),
            thumbnail_url=data.get("thumbnail_url"),
            in_stock=data.get("in_stock", True),
        )


def _wait_for_page_load(
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> None:
    """ページの読み込みを待機する"""
    try:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, "//body")
            )
        )
        time.sleep(1)
    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Yodobashi] 読み込みタイムアウト")
        raise


def _extract_title(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> str:
    """商品タイトルを取得する"""
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        elements = driver.find_elements(by_xpath, _TITLE_XPATH)
        if elements and elements[0].text:
            return elements[0].text.strip()
    except Exception:
        logging.exception("[Yodobashi] タイトル取得失敗")

    msg = "商品タイトルが見つかりません"
    raise ValueError(msg)


def _extract_price(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> int | None:
    """価格を取得する"""
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        elements = driver.find_elements(by_xpath, _PRICE_XPATH)
        if elements and elements[0].text:
            price_text = elements[0].text
            # 「¥31,680」のような形式から数値を抽出
            price_str = re.sub(r"[¥￥,\s円]", "", price_text)
            return int(price_str)
    except (ValueError, IndexError):
        pass
    except Exception:
        logging.exception("[Yodobashi] 価格取得失敗")

    return None


def _extract_thumbnail_url(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> str | None:
    """サムネイル画像のURLを取得する"""
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        elements = driver.find_elements(by_xpath, _THUMBNAIL_XPATH)
        if elements:
            url = elements[0].get_attribute("value")
            if url:
                return url
    except Exception:
        logging.exception("[Yodobashi] サムネイルURL取得失敗")

    return None


def _check_in_stock(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> bool:
    """在庫があるかどうかを確認する"""
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        elements = driver.find_elements(by_xpath, _OUT_OF_STOCK_XPATH)
        # 「販売休止」または「販売を終了しました」が見つかった場合は在庫なし
        return len(elements) == 0
    except Exception:
        logging.exception("[Yodobashi] 在庫確認失敗")
        # エラー時は在庫ありとして扱う（安全側に倒す）
        return True


def scrape(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    url: str,
) -> ProductInfo:
    """商品ページから情報を取得する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス
        url: 商品ページのURL

    Returns:
        商品情報

    """
    logging.info("[Yodobashi] 商品ページ取得開始: %s", url)

    driver.get(url)
    _wait_for_page_load(wait)

    title = _extract_title(driver)
    price = _extract_price(driver)
    thumbnail_url = _extract_thumbnail_url(driver)
    in_stock = _check_in_stock(driver)

    logging.info(
        "[Yodobashi] 商品ページ取得完了: title=%s, price=%s, in_stock=%s",
        title,
        price,
        in_stock,
    )

    return ProductInfo(
        title=title,
        price=price,
        thumbnail_url=thumbnail_url,
        in_stock=in_stock,
    )


if __name__ == "__main__":
    # TEST Code
    import pathlib

    import docopt
    import selenium.webdriver.support.wait

    import my_lib.logger
    import my_lib.selenium_util

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    url = args["-u"]
    data_path = args["-s"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    logging.info("商品URL: %s", url)

    driver = my_lib.selenium_util.create_driver(
        "yodobashi_test",
        pathlib.Path(data_path),
        stealth_mode=True,
    )
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 10)

    try:
        result = scrape(driver, wait, url)

        logging.info("=" * 60)
        logging.info("取得結果")
        logging.info("=" * 60)
        logging.info("タイトル: %s", result.title)
        if result.price:
            logging.info("価格: ¥%s", f"{result.price:,}")
        else:
            logging.info("価格: 取得失敗")
        logging.info("サムネイルURL: %s", result.thumbnail_url or "取得失敗")
        logging.info("在庫: %s", "あり" if result.in_stock else "なし")
    finally:
        my_lib.selenium_util.quit_driver_gracefully(driver)
