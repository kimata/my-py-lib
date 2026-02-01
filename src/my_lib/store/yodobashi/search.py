#!/usr/bin/env python3
"""
ヨドバシ.com 検索ライブラリ

https://www.yodobashi.com/ で商品を検索し、
商品名、URL、価格のリストを取得します。

Usage:
  search.py [-k KEYWORD] [-n COUNT] [-s DATA_PATH] [-d DUMP_PATH] [-D]

Options:
  -k KEYWORD      : 検索キーワード。[default: Canon RF50mm]
  -n COUNT        : 取得する最大件数。[default: 10]
  -s DATA_PATH    : Selenium で使うブラウザのデータを格納するディレクトリ。
                    [default: data]
  -d DUMP_PATH    : ページのHTMLをダンプするディレクトリ。
  -D              : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support.expected_conditions

import my_lib.selenium_util

if TYPE_CHECKING:
    import selenium.webdriver.remote.webdriver
    import selenium.webdriver.remote.webelement
    import selenium.webdriver.support.wait


_SEARCH_BASE_URL: str = "https://www.yodobashi.com/"
# 商品リンクのみを取得（評価リンク等を除外するため cImg クラスを条件に追加）
_ITEM_LIST_XPATH: str = '//div[contains(@class, "srcResultItem_block")]//a[contains(@class, "cImg")]'


@dataclass(frozen=True)
class SearchResult:
    """検索結果の商品情報"""

    name: str
    url: str
    price: int | None = None


def build_search_url(keyword: str) -> str:
    """検索キーワードから検索 URL を生成する

    Args:
        keyword: 検索キーワード

    Returns:
        検索 URL

    """
    params = {"word": keyword}
    query = urllib.parse.urlencode(params)
    return f"{_SEARCH_BASE_URL}?{query}"


def _clean_url(url: str) -> str:
    """URL からフラグメントを除去する"""
    return url.split("#")[0]


def _is_product_page(url: str) -> bool:
    """商品ページの URL かどうかを判定する"""
    return "/product/" in url and "/ec/product/stock/" not in url


def _wait_for_search_results(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> bool:
    """検索結果の読み込みを待機する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス

    Returns:
        検索結果が存在する場合は True

    """
    try:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, "//body")
            )
        )
        time.sleep(2)

        # 検索結果が0件の場合のチェック
        page_source = driver.page_source
        if "一致する商品はありませんでした" in page_source:
            logging.info("[Yodobashi] 該当なし")
            return False

        return True
    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Yodobashi] 読み込みタイムアウト")
        raise


def _parse_product_page(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
) -> SearchResult | None:
    """商品ページから情報を取得する

    Args:
        driver: WebDriver インスタンス

    Returns:
        商品情報。取得に失敗した場合は None

    """
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        url = _clean_url(driver.current_url)

        # 商品名を取得
        name: str | None = None
        name_selectors = [
            '//h1[contains(@class, "productName")]',
            '//div[contains(@class, "productName")]//h1',
            '//h1[@itemprop="name"]',
            "//h1",
        ]
        for selector in name_selectors:
            elements = driver.find_elements(by_xpath, selector)
            if elements and elements[0].text.strip():
                name = elements[0].text.strip()
                break

        # 価格を取得
        price: int | None = None
        price_selectors = [
            '//span[contains(@class, "productPrice")]',
            '//span[@itemprop="price"]',
            '//span[contains(@class, "salesPrice")]',
        ]
        for selector in price_selectors:
            elements = driver.find_elements(by_xpath, selector)
            if elements and elements[0].text:
                price_text = elements[0].text
                price_str = re.sub(r"[¥￥,\s円]", "", price_text)
                try:
                    price = int(price_str)
                    break
                except ValueError:
                    continue

        if not name:
            logging.debug("[Yodobashi] 商品ページパース失敗: 商品名取得失敗")
            return None

        return SearchResult(name=name, url=url, price=price)

    except Exception:
        logging.exception("[Yodobashi] 商品ページパース失敗")
        return None


def _parse_search_item(
    item_element: selenium.webdriver.remote.webelement.WebElement,
) -> SearchResult | None:
    """検索結果の1件をパースする

    Args:
        item_element: 商品要素

    Returns:
        パース結果。パースに失敗した場合は None

    """
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        # URL を取得
        href = item_element.get_attribute("href")
        if not href or not _is_product_page(href):
            return None
        url = _clean_url(href)

        # 商品名を取得（リンクのテキスト）
        name = item_element.text.strip() if item_element.text else None

        if not name:
            # 親要素から商品名を探す
            try:
                parent = item_element.find_element(by_xpath, "./..")
                name_elements = parent.find_elements(by_xpath, './/p[contains(@class, "pName")]')
                if name_elements and name_elements[0].text:
                    name = name_elements[0].text.strip()
            except selenium.common.exceptions.NoSuchElementException:
                pass

        if not name:
            logging.debug("[Yodobashi] パース失敗: 商品名取得失敗 url=%s", url)
            return None

        return SearchResult(name=name, url=url, price=None)

    except Exception:
        logging.exception("[Yodobashi] パース失敗")
        return None


def search(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    keyword: str,
    max_items: int | None = None,
) -> list[SearchResult]:
    """ヨドバシ.com で商品を検索する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス
        keyword: 検索キーワード
        max_items: 取得する最大件数（None の場合は制限なし）

    Returns:
        検索結果のリスト

    """
    url = build_search_url(keyword)
    logging.info("[Yodobashi] 検索開始: keyword=%s", keyword)
    logging.debug("[Yodobashi] 検索URL: %s", url)

    driver.get(url)

    if not _wait_for_search_results(driver, wait):
        return []

    current_url = driver.current_url

    # 商品ページに直接遷移した場合（1件のみヒット）
    if _is_product_page(current_url):
        logging.info("[Yodobashi] 商品ページに直接遷移")
        result = _parse_product_page(driver)
        if result:
            return [result]
        return []

    # 検索結果一覧から商品を取得
    by_xpath = selenium.webdriver.common.by.By.XPATH

    results: list[SearchResult] = []
    parsed_urls: set[str] = set()

    item_elements = driver.find_elements(by_xpath, _ITEM_LIST_XPATH)
    logging.debug("[Yodobashi] ページ解析: %d 件発見", len(item_elements))

    for item_element in item_elements:
        if max_items is not None and len(results) >= max_items:
            break

        result = _parse_search_item(item_element)
        if result is not None and result.url not in parsed_urls:
            results.append(result)
            parsed_urls.add(result.url)

    logging.info("[Yodobashi] 検索完了: %d 件", len(results))
    return results


def search_by_name(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    brand: str,
    product_name: str,
) -> SearchResult | None:
    """ブランド名と商品名で検索し、最も一致する商品を返す

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス
        brand: ブランド名（例: "Canon", "ソニー", "Nikon"）
        product_name: 商品名

    Returns:
        最も一致する商品。見つからない場合は None

    """
    keyword = f"{brand} {product_name}"
    results = search(driver, wait, keyword, max_items=10)

    if not results:
        return None

    if len(results) == 1:
        return results[0]

    # 商品名との一致度をチェック
    product_name_normalized = _normalize_name(product_name)

    for result in results:
        result_name_normalized = _normalize_name(result.name)
        if product_name_normalized in result_name_normalized:
            return result

    # 一致するものがなければ最初の結果を返す
    return results[0]


def _normalize_name(name: str) -> str:
    """名前を正規化して比較しやすくする"""
    name = name.lower()
    name = re.sub(r"[\s\-\/]+", "", name)
    name = name.replace("ｆ", "f").replace("ｍｍ", "mm")
    return name


if __name__ == "__main__":
    # TEST Code
    import pathlib

    import docopt
    import selenium.webdriver.support.wait

    import my_lib.logger
    import my_lib.selenium_util

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    keyword = args["-k"]
    max_count_str = args["-n"]
    data_path = args["-s"]
    dump_path_str = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    max_count = int(max_count_str) if max_count_str else None
    dump_path = pathlib.Path(dump_path_str) if dump_path_str else None

    logging.info("検索キーワード: %s", keyword)

    driver = my_lib.selenium_util.create_driver(
        "yodobashi_test",
        pathlib.Path(data_path),
        stealth_mode=True,
    )
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 10)

    try:
        results = search(driver, wait, keyword, max_items=max_count)

        if dump_path:
            dump_path.mkdir(parents=True, exist_ok=True)
            my_lib.selenium_util.dump_page(driver, 0, dump_path)
            logging.info("ページをダンプしました: %s", dump_path)

            by_xpath = selenium.webdriver.common.by.By.XPATH
            item_elements = driver.find_elements(by_xpath, _ITEM_LIST_XPATH)
            if item_elements:
                first_item_html = item_elements[0].get_attribute("outerHTML")
                item_html_path = dump_path / "first_item.html"
                with item_html_path.open("w", encoding="utf-8") as f:
                    f.write(first_item_html if first_item_html else "")
                logging.info("最初の商品のHTMLをダンプしました: %s", item_html_path)

        logging.info("=" * 60)
        logging.info("検索結果: %d 件", len(results))
        logging.info("=" * 60)

        for i, result in enumerate(results, 1):
            logging.info("[%d] %s", i, result.name)
            if result.price:
                logging.info("    価格: ¥%s", f"{result.price:,}")
            logging.info("    URL: %s", result.url)
    finally:
        my_lib.selenium_util.quit_driver_gracefully(driver)
