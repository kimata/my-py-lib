#!/usr/bin/env python3
"""
ラクマ検索ライブラリ

https://fril.jp/s を使用して商品を検索し、
タイトル、URL、価格のリストを取得します。

Usage:
  search.py [-k KEYWORD] [-e EXCLUDE] [-m MIN] [-M MAX] [-c CONDITIONS]
            [-n COUNT] [-s DATA_PATH] [-d DUMP_PATH] [-D]

Options:
  -k KEYWORD      : 検索キーワード。[default: iPhone]
  -e EXCLUDE      : 除外キーワード。
  -m MIN          : 最低価格。
  -M MAX          : 最高価格。
  -c CONDITIONS   : 商品状態（カンマ区切り: 1=新品,2=未使用に近い,
                    3=目立った傷なし,4=やや傷あり,5=傷あり,6=状態悪い）。
  -n COUNT        : 取得する最大件数。[default: 10]
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

# ラクマの商品状態パラメータ名とID対応
# ラクマは独自の状態ID: 5=新品, 4=未使用に近い, 6=目立った傷なし, 3=やや傷あり, 2=傷あり, 1=状態悪い
_CONDITION_PARAM_MAP: dict[my_lib.store.flea_market.ItemCondition, str] = {
    my_lib.store.flea_market.ItemCondition.NEW: "5",
    my_lib.store.flea_market.ItemCondition.LIKE_NEW: "4",
    my_lib.store.flea_market.ItemCondition.GOOD: "6",
    my_lib.store.flea_market.ItemCondition.FAIR: "3",
    my_lib.store.flea_market.ItemCondition.POOR: "2",
    my_lib.store.flea_market.ItemCondition.BAD: "1",
}


_SEARCH_BASE_URL: str = "https://fril.jp/s"
# 商品リストのアイテム要素
_ITEM_LIST_XPATH: str = '//div[contains(@class, "item-box")]'


def build_search_url(condition: my_lib.store.flea_market.SearchCondition) -> str:
    """検索条件から検索 URL を生成する

    Args:
        condition: 検索条件

    Returns:
        検索 URL

    """
    params: dict[str, Any] = {
        "query": condition.keyword,
        "sort": "created_at",
        "order": "desc",
    }

    # 販売状態（None は全て）
    if condition.sale_status == my_lib.store.flea_market.SaleStatus.ON_SALE:
        params["transaction"] = "selling"
    elif condition.sale_status == my_lib.store.flea_market.SaleStatus.SOLD_OUT:
        params["transaction"] = "soldout"

    if condition.exclude_keyword:
        params["excluded_query"] = condition.exclude_keyword

    if condition.price_min is not None:
        params["min"] = condition.price_min

    if condition.price_max is not None:
        params["max"] = condition.price_max

    query_parts: list[str] = []
    for key, value in params.items():
        query_parts.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(str(value))}")

    if condition.condition:
        cond_values = ",".join(_CONDITION_PARAM_MAP[cond] for cond in condition.condition)
        query_parts.append(f"statuses={cond_values}")

    return f"{_SEARCH_BASE_URL}?{'&'.join(query_parts)}"


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
                (selenium.webdriver.common.by.By.XPATH, '//div[contains(@class, "content")]')
            )
        )
        time.sleep(1)

        # 検索結果が0件の場合のチェック
        no_result_xpath = '//p[contains(text(), "見つかりませんでした")]'
        if my_lib.selenium_util.xpath_exists(driver, no_result_xpath):
            logging.info("[Rakuma] 該当なし")
            return False

        return True
    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Rakuma] 読み込みタイムアウト")
        raise


def _parse_search_item(
    item_element: Any,
) -> my_lib.store.flea_market.SearchResult | None:
    """検索結果の1件をパースする

    Args:
        item_element: 商品要素

    Returns:
        パース結果。パースに失敗した場合は None

    """
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        # URL を取得
        # ラクマのリンクは href="https://item.fril.jp/{id}" 形式
        link_elements = item_element.find_elements(by_xpath, './/a[contains(@href, "item.fril.jp")]')
        if not link_elements:
            logging.debug("[Rakuma] パース失敗: リンク要素なし")
            return None
        url_raw = link_elements[0].get_attribute("href")
        if url_raw is None:
            logging.debug("[Rakuma] パース失敗: URL取得失敗")
            return None
        url = url_raw

        # タイトルを取得
        title: str | None = None

        # 方法1: p.item-box__item-name 内の span から取得
        title_elements = item_element.find_elements(
            by_xpath, './/p[contains(@class, "item-box__item-name")]//span'
        )
        if title_elements and title_elements[0].text:
            title = title_elements[0].text

        # 方法2: p.item-box__item-name のテキストから取得
        if not title:
            name_elements = item_element.find_elements(
                by_xpath, './/p[contains(@class, "item-box__item-name")]'
            )
            if name_elements and name_elements[0].text:
                title = name_elements[0].text.strip()

        # 方法3: img の alt 属性から取得
        if not title:
            img_elements = item_element.find_elements(by_xpath, ".//img[@alt]")
            for img in img_elements:
                alt = img.get_attribute("alt")
                if alt and alt.strip():
                    title = alt.strip()
                    break

        # 価格を取得
        price: int | None = None

        # 方法1: p.item-box__item-price 内の data-content 属性から取得（最も正確）
        price_data_elements = item_element.find_elements(
            by_xpath, './/p[contains(@class, "item-box__item-price")]//span[@data-content]'
        )
        for elem in price_data_elements:
            data_content = elem.get_attribute("data-content")
            if data_content and data_content not in ("JPY",):
                with contextlib.suppress(ValueError):
                    price = int(data_content)
                break

        # 方法2: p.item-box__item-price のテキストから取得
        if price is None:
            price_elements = item_element.find_elements(
                by_xpath, './/p[contains(@class, "item-box__item-price")]'
            )
            if price_elements and price_elements[0].text:
                price_text = price_elements[0].text
                price_str = re.sub(r"[¥￥,\s]", "", price_text)
                with contextlib.suppress(ValueError):
                    price = int(price_str)

        # 方法3: テキストから「¥数字」パターンを探す
        if price is None:
            all_text = item_element.text
            price_match = re.search(r"[¥￥]([\d,]+)", all_text)
            if price_match:
                with contextlib.suppress(ValueError):
                    price = int(price_match.group(1).replace(",", ""))

        if not title or price is None:
            logging.debug("[Rakuma] パース失敗: title=%s, price=%s", title, price)
            return None

        return my_lib.store.flea_market.SearchResult(name=title, url=url, price=price)

    except Exception:
        logging.exception("[Rakuma] パース失敗")
        return None


def search(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    condition: my_lib.store.flea_market.SearchCondition,
    max_items: int | None = None,
    scroll_to_load: bool = False,
) -> list[my_lib.store.flea_market.SearchResult]:
    """ラクマで商品を検索する

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
    logging.info("[Rakuma] 検索開始: keyword=%s", condition.keyword)
    logging.debug("[Rakuma] 検索URL: %s", url)

    driver.get(url)

    if not _wait_for_search_results(driver, wait):
        return []

    by_xpath = selenium.webdriver.common.by.By.XPATH

    results: list[my_lib.store.flea_market.SearchResult] = []
    parsed_urls: set[str] = set()

    item_elements = driver.find_elements(by_xpath, _ITEM_LIST_XPATH)
    logging.debug("[Rakuma] ページ解析: %d 件発見", len(item_elements))

    for i, item_element in enumerate(item_elements):
        if max_items is not None and len(results) >= max_items:
            logging.info("[Rakuma] 検索完了: %d 件", len(results))
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
                logging.debug("[Rakuma] 要素 %d がStale、スキップ", i + 1)
                continue

        result = _parse_search_item(item_element)
        if result is not None and result.url not in parsed_urls:
            results.append(result)
            parsed_urls.add(result.url)

    logging.info("[Rakuma] 検索完了: %d 件", len(results))
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
    data_path = args["-s"]
    dump_path_str = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    price_min = int(price_min_str) if price_min_str else None
    price_max = int(price_max_str) if price_max_str else None
    max_count = int(max_count_str) if max_count_str else None
    dump_path = pathlib.Path(dump_path_str) if dump_path_str else None

    item_condition_list: list[my_lib.store.flea_market.ItemCondition] | None = None
    if conditions_str:
        item_condition_list = [
            my_lib.store.flea_market.ItemCondition(int(c.strip())) for c in conditions_str.split(",")
        ]

    condition = my_lib.store.flea_market.SearchCondition(
        keyword=keyword,
        exclude_keyword=exclude_keyword,
        price_min=price_min,
        price_max=price_max,
        condition=item_condition_list,
    )

    logging.info("検索条件: %s", condition)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(data_path))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 10)

    try:
        results = search(driver, wait, condition, max_items=max_count)

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
            logging.info("    価格: ¥%s", f"{result.price:,}")
            logging.info("    URL: %s", result.url)
    finally:
        my_lib.selenium_util.quit_driver_gracefully(driver)
