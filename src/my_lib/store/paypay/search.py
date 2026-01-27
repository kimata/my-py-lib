#!/usr/bin/env python3
"""
PayPayフリマ検索ライブラリ

https://paypayfleamarket.yahoo.co.jp/search/ を使用して商品を検索し、
タイトル、URL、価格のリストを取得します。

Usage:
  search.py [-k KEYWORD] [-e EXCLUDE] [-m MIN] [-M MAX] [-c CONDITIONS]
            [-n COUNT] [-S] [-s DATA_PATH] [-d DUMP_PATH] [-D]

Options:
  -k KEYWORD      : 検索キーワード。[default: iPhone]
  -e EXCLUDE      : 除外キーワード。
  -m MIN          : 最低価格。
  -M MAX          : 最高価格。
  -c CONDITIONS   : 商品状態（カンマ区切り: 1=新品,2=未使用に近い,
                    3=目立った傷なし,4=やや傷あり,5=傷あり,6=状態悪い）。
  -n COUNT        : 取得する最大件数。[default: 10]
  -S              : スクロールして追加の商品を読み込む。
  -s DATA_PATH    : Selenium で使うブラウザのデータを格納するディレクトリ。
                    [default: data]
  -d DUMP_PATH    : ページのHTMLをダンプするディレクトリ。
  -D              : デバッグモードで動作します。
"""

from __future__ import annotations

import contextlib
import logging
import re
import time
import urllib.parse
from typing import TYPE_CHECKING, Any

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support.expected_conditions

import my_lib.selenium_util

if TYPE_CHECKING:
    import selenium.webdriver.remote.webdriver
    import selenium.webdriver.support.wait


import my_lib.store.flea_market

# PayPayフリマの商品状態パラメータ対応
_CONDITION_PARAM_MAP: dict[my_lib.store.flea_market.ItemCondition, str] = {
    my_lib.store.flea_market.ItemCondition.NEW: "1",
    my_lib.store.flea_market.ItemCondition.LIKE_NEW: "2",
    my_lib.store.flea_market.ItemCondition.GOOD: "3",
    my_lib.store.flea_market.ItemCondition.FAIR: "4",
    my_lib.store.flea_market.ItemCondition.POOR: "5",
    my_lib.store.flea_market.ItemCondition.BAD: "6",
}


_SEARCH_BASE_URL: str = "https://paypayfleamarket.yahoo.co.jp/search"
# 商品リストのアイテム要素
# div#itm 内の <a href="/item/z..."> を直接取得
_ITEM_LIST_XPATH: str = '//div[@id="itm"]//a[contains(@href, "/item/")]'


def build_search_url(condition: my_lib.store.flea_market.SearchCondition) -> str:
    """検索条件から検索 URL を生成する

    Args:
        condition: 検索条件

    Returns:
        検索 URL

    """
    # PayPayフリマはキーワードをパスに含める形式
    keyword = condition.keyword
    if condition.exclude_keyword:
        keyword = f"{keyword} -{condition.exclude_keyword}"

    encoded_keyword = urllib.parse.quote(keyword)
    url = f"{_SEARCH_BASE_URL}/{encoded_keyword}"

    params: dict[str, str] = {
        "open": "1",  # 販売中のみ
    }

    if condition.price_min is not None:
        params["price_min"] = str(condition.price_min)

    if condition.price_max is not None:
        params["price_max"] = str(condition.price_max)

    if condition.item_conditions:
        for cond in condition.item_conditions:
            params[f"conditions[{_CONDITION_PARAM_MAP[cond]}]"] = "1"

    if params:
        query_parts = [f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}" for k, v in params.items()]
        url = f"{url}?{'&'.join(query_parts)}"

    return url


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
        # React アプリのため、メインコンテンツの描画を待機
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, "//main | //div[@id='root']//ul")
            )
        )
        time.sleep(2)  # React の描画完了を待つ

        # 検索結果が0件の場合のチェック
        no_result_xpath = '//p[contains(text(), "見つかりません")] | //p[contains(text(), "0件")]'
        if my_lib.selenium_util.xpath_exists(driver, no_result_xpath):
            logging.info("[PayPay] 該当なし")
            return False

        # 並び順を新着順に変更（URL パラメータでは反映されないため select 操作で切り替え）
        _select_sort_order(driver, wait)

        return True
    except selenium.common.exceptions.TimeoutException:
        logging.warning("[PayPay] 読み込みタイムアウト")
        return False


def _select_sort_order(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> None:
    """並び順を新着順に変更する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス

    """
    import selenium.webdriver.support.select

    by_xpath = selenium.webdriver.common.by.By.XPATH
    select_xpath = '//select[option[@value="newer"]]'

    try:
        select_elements = driver.find_elements(by_xpath, select_xpath)
        if not select_elements:
            logging.warning("[PayPay] 並び替えセレクトボックスが見つかりません")
            return

        select_obj = selenium.webdriver.support.select.Select(select_elements[0])
        select_obj.select_by_value("newer")
        logging.debug("[PayPay] 新着順に切り替え")

        # 再描画を待機
        time.sleep(2)

        # 商品リストが更新されるのを待つ
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (by_xpath, _ITEM_LIST_XPATH)
            )
        )
        time.sleep(1)

    except selenium.common.exceptions.TimeoutException:
        logging.warning("[PayPay] 新着順への切り替え後のタイムアウト")
    except Exception:
        logging.exception("[PayPay] 並び替え切り替え失敗")


def _parse_search_item(
    item_element: Any,
) -> my_lib.store.flea_market.SearchResult | None:
    """検索結果の1件をパースする

    Args:
        item_element: 商品のリンク要素（<a> タグ）

    Returns:
        パース結果。パースに失敗した場合は None

    """
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        # URL を取得（item_element 自体が <a> タグ）
        url_raw = item_element.get_attribute("href")
        if url_raw is None:
            logging.debug("[PayPay] パース失敗: URL取得失敗")
            return None
        url = f"https://paypayfleamarket.yahoo.co.jp{url_raw}" if url_raw.startswith("/") else url_raw

        # タイトルを取得
        title: str | None = None

        # 方法1: img の alt 属性から取得（最も安定）
        img_elements = item_element.find_elements(by_xpath, ".//img[@alt]")
        for img in img_elements:
            alt = img.get_attribute("alt")
            if alt and alt.strip():
                title = alt.strip()
                break

        # 方法2: テキスト行から商品名を探す（価格行でない行）
        if not title:
            all_text = item_element.text
            if all_text:
                lines = [line.strip() for line in all_text.strip().split("\n") if line.strip()]
                for line in lines:
                    if not re.match(r"^[\d,]+円$", line) and line != "いいね！":
                        title = line
                        break

        # 価格を取得
        price: int | None = None

        # 方法1: <p> 要素のテキストから「数字円」パターンを探す
        p_elements = item_element.find_elements(by_xpath, ".//p")
        for p_elem in p_elements:
            p_text = p_elem.text
            if p_text:
                price_match = re.match(r"^([\d,]+)円$", p_text.strip())
                if price_match:
                    with contextlib.suppress(ValueError):
                        price = int(price_match.group(1).replace(",", ""))
                    break

        # 方法2: 要素全体のテキストから価格パターンを探す
        if price is None:
            all_text = item_element.text or ""
            price_match = re.search(r"([\d,]+)円", all_text)
            if price_match:
                with contextlib.suppress(ValueError):
                    price = int(price_match.group(1).replace(",", ""))

        if not title or price is None:
            debug_text = (item_element.text or "")[:100]
            logging.debug("[PayPay] パース失敗: title=%s, price=%s, text=%s", title, price, debug_text)
            return None

        return my_lib.store.flea_market.SearchResult(title=title, url=url, price=price)

    except Exception:
        logging.exception("[PayPay] パース失敗")
        return None


def search(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    condition: my_lib.store.flea_market.SearchCondition,
    max_items: int | None = None,
    scroll_to_load: bool = False,
) -> list[my_lib.store.flea_market.SearchResult]:
    """PayPayフリマで商品を検索する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス
        condition: 検索条件
        max_items: 取得する最大件数（None の場合は制限なし）
        scroll_to_load: スクロールして追加の商品を読み込むか

    Returns:
        検索結果のリスト

    """
    url = build_search_url(condition)
    logging.info("[PayPay] 検索開始: keyword=%s", condition.keyword)
    logging.debug("[PayPay] 検索URL: %s", url)

    driver.get(url)

    if not _wait_for_search_results(driver, wait):
        return []

    by_xpath = selenium.webdriver.common.by.By.XPATH

    results: list[my_lib.store.flea_market.SearchResult] = []
    parsed_urls: set[str] = set()

    item_elements = driver.find_elements(by_xpath, _ITEM_LIST_XPATH)
    logging.debug("[PayPay] ページ解析: %d 件発見", len(item_elements))

    for i, item_element in enumerate(item_elements):
        if max_items is not None and len(results) >= max_items:
            logging.info("[PayPay] 検索完了: %d 件", len(results))
            return results

        if scroll_to_load or i < 20:
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
                    item_element,
                )
                if i >= 20:
                    time.sleep(0.3)
            except selenium.common.exceptions.StaleElementReferenceException:
                logging.debug("[PayPay] 要素 %d がStale、スキップ", i + 1)
                continue

        result = _parse_search_item(item_element)
        if result is not None and result.url not in parsed_urls:
            results.append(result)
            parsed_urls.add(result.url)

    logging.info("[PayPay] 検索完了: %d 件", len(results))
    return results


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
    exclude_keyword = args["-e"]
    price_min_str = args["-m"]
    price_max_str = args["-M"]
    conditions_str = args["-c"]
    max_count_str = args["-n"]
    scroll_to_load = args["-S"]
    data_path = args["-s"]
    dump_path_str = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    price_min = int(price_min_str) if price_min_str else None
    price_max = int(price_max_str) if price_max_str else None
    max_count = int(max_count_str) if max_count_str else None
    dump_path = pathlib.Path(dump_path_str) if dump_path_str else None

    if max_count is not None and max_count > 20:
        scroll_to_load = True

    item_conditions: list[my_lib.store.flea_market.ItemCondition] | None = None
    if conditions_str:
        item_conditions = [
            my_lib.store.flea_market.ItemCondition(int(c.strip())) for c in conditions_str.split(",")
        ]

    condition = my_lib.store.flea_market.SearchCondition(
        keyword=keyword,
        exclude_keyword=exclude_keyword,
        price_min=price_min,
        price_max=price_max,
        item_conditions=item_conditions,
    )

    logging.info("検索条件: %s", condition)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(data_path))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 15)

    try:
        results = search(driver, wait, condition, max_items=max_count, scroll_to_load=scroll_to_load)

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
            logging.info("[%d] %s", i, result.title)
            logging.info("    価格: ¥%s", f"{result.price:,}")
            logging.info("    URL: %s", result.url)
    finally:
        my_lib.selenium_util.quit_driver_gracefully(driver)
