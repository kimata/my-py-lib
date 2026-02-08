#!/usr/bin/env python3
"""
メルカリ検索ライブラリ

https://jp.mercari.com/search を使用して商品を検索し、
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
import time
import urllib.parse
from typing import TYPE_CHECKING, Any

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.common.keys
import selenium.webdriver.support.expected_conditions

import my_lib.selenium_util

if TYPE_CHECKING:
    import selenium.webdriver.remote.webdriver
    import selenium.webdriver.support.wait


import my_lib.store.flea_market

_SEARCH_BASE_URL: str = "https://jp.mercari.com/search"
_TARGET_DOMAIN: str = "mercari.com"
_SEARCH_KEYWORD: str = "メルカリ"
# item-grid 内のアイテムのみを取得（関連商品やおすすめ商品を除外）
_ITEM_LIST_XPATH: str = '//div[@id="item-grid"]//li[@data-testid="item-cell"]'


def warmup(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> bool:
    """Google検索経由でメルカリにアクセスしてウォームアップする

    bot検出を回避するため、直接アクセスではなくGoogle検索経由でアクセスする。

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス

    Returns:
        ウォームアップが成功した場合 True

    """
    logging.info("[Mercari] ウォームアップ開始")

    try:
        # Googleにアクセス
        driver.get("https://www.google.com/")
        time.sleep(1)

        # 検索ボックスを探して検索
        by_xpath = selenium.webdriver.common.by.By.XPATH
        by_name = selenium.webdriver.common.by.By.NAME

        # 検索ボックスに入力
        search_box = wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located((by_name, "q"))
        )
        search_box.clear()
        search_box.send_keys(_SEARCH_KEYWORD)
        time.sleep(0.5)

        # 検索実行（Enterキー）
        search_box.send_keys(selenium.webdriver.common.keys.Keys.RETURN)
        time.sleep(2)

        # 検索結果からメルカリのリンクを探してクリック
        link_xpath = f'//a[contains(@href, "{_TARGET_DOMAIN}")]'
        link_element = wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located((by_xpath, link_xpath))
        )

        # リンクをクリック
        driver.execute_script("arguments[0].click();", link_element)
        time.sleep(2)

        # メルカリのページが読み込まれたか確認
        if _TARGET_DOMAIN in driver.current_url:
            logging.info("[Mercari] ウォームアップ完了: %s", driver.current_url)
            return True

        logging.warning("[Mercari] ウォームアップ: 予期しないURL: %s", driver.current_url)
        return False

    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Mercari] ウォームアップ: タイムアウト")
        return False
    except Exception:
        logging.exception("[Mercari] ウォームアップ: エラー")
        return False


def build_search_url(condition: my_lib.store.flea_market.SearchCondition) -> str:
    """検索条件から検索 URL を生成する

    Args:
        condition: 検索条件

    Returns:
        検索 URL

    """
    params: dict[str, Any] = {
        "keyword": condition.keyword,
        "order": "created_time",
        "sort": "desc",
    }

    # 販売状態（None は全て）
    if condition.sale_status == my_lib.store.flea_market.SaleStatus.ON_SALE:
        params["status"] = "on_sale"
    elif condition.sale_status == my_lib.store.flea_market.SaleStatus.SOLD_OUT:
        params["status"] = "sold_out"

    if condition.exclude_keyword:
        params["exclude_keyword"] = condition.exclude_keyword

    if condition.price_min is not None:
        params["price_min"] = condition.price_min

    if condition.price_max is not None:
        params["price_max"] = condition.price_max

    # 商品状態は複数指定可能なため、カンマ区切りで追加
    query_parts: list[str] = []
    for key, value in params.items():
        query_parts.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(str(value))}")

    if condition.condition:
        cond_values = ",".join(str(cond.value) for cond in condition.condition)
        query_parts.append(f"item_condition_id={urllib.parse.quote(cond_values)}")

    return f"{_SEARCH_BASE_URL}?{'&'.join(query_parts)}"


def _apply_normal_listing_filter(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> bool:
    """絞り込みUIで出品形式「通常出品」を選択する

    Args:
        driver: WebDriver インスタンス
        wait: WebDriverWait インスタンス

    Returns:
        フィルタ適用に成功した場合は True

    """
    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        # PC版: 左側パネルに直接フィルタが表示されている
        # 「出品形式」セクションを探す
        logging.debug("[Mercari] 出品形式セクションを探索中...")
        listing_type_xpath = '//div[@data-testid="出品形式"]'
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (by_xpath, listing_type_xpath)
            )
        )

        # アコーディオンが閉じていれば展開
        accordion_button_xpath = '//div[@data-testid="出品形式"]//button[@id="accordion_button"]'
        accordion_buttons = driver.find_elements(by_xpath, accordion_button_xpath)
        if accordion_buttons:
            accordion_button = accordion_buttons[0]
            if accordion_button.get_attribute("aria-expanded") == "false":
                accordion_button.click()
                logging.debug("[Mercari] 出品形式セクションを展開")
                time.sleep(0.3)

        # 「通常出品」チェックボックスのラベルをクリック
        logging.debug("[Mercari] 通常出品チェックボックスを探索中...")
        normal_listing_xpath = '//div[@data-testid="出品形式"]//label[.//span[text()="通常出品"]]'
        wait.until(
            selenium.webdriver.support.expected_conditions.element_to_be_clickable(
                (by_xpath, normal_listing_xpath)
            )
        )
        normal_listing_label = driver.find_element(by_xpath, normal_listing_xpath)
        normal_listing_label.click()
        logging.debug("[Mercari] 通常出品をクリック")
        time.sleep(0.5)

        logging.info("[Mercari] 出品形式「通常出品」フィルタを適用")
        return True

    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Mercari] 絞り込みUIの操作に失敗（タイムアウト）")
        return False
    except selenium.common.exceptions.NoSuchElementException:
        logging.warning("[Mercari] 絞り込みUIの要素が見つかりません")
        return False


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
                (selenium.webdriver.common.by.By.XPATH, "//main")
            )
        )
        time.sleep(1)

        # 検索結果が0件の場合のチェック
        no_result_xpath = '//p[contains(text(), "新着のお知らせを受け取る")]'
        if my_lib.selenium_util.xpath_exists(driver, no_result_xpath):
            logging.info("[Mercari] 該当なし")
            return False

        return True
    except selenium.common.exceptions.TimeoutException:
        logging.warning("[Mercari] 読み込みタイムアウト")
        raise


def _parse_search_item(
    item_element: Any,
) -> my_lib.store.flea_market.SearchResult | None:
    """検索結果の1件をパースする

    Args:
        item_element: 商品要素

    Returns:
        パース結果。パースに失敗した場合は None
        PR（広告）アイテムの場合も None を返す

    """
    import re

    by_xpath = selenium.webdriver.common.by.By.XPATH

    try:
        # PR（広告）アイテムをスキップ
        # <p class="merText ...">PR</p> があれば除外
        pr_elements = item_element.find_elements(
            by_xpath, './/p[contains(@class, "merText") and text()="PR"]'
        )
        if pr_elements:
            logging.debug("[Mercari] 広告アイテムをスキップ")
            return None

        # URL を取得
        link_elements = item_element.find_elements(by_xpath, ".//a")
        if not link_elements:
            logging.debug("[Mercari] パース失敗: リンク要素なし")
            return None
        url_raw = link_elements[0].get_attribute("href")
        if url_raw is None:
            logging.debug("[Mercari] パース失敗: URL取得失敗")
            return None
        # 相対パスの場合はフルURLに変換
        url = f"https://jp.mercari.com{url_raw}" if url_raw.startswith("/") else url_raw

        # タイトルを取得
        # 商品名は data-testid="thumbnail-item-name" から取得するのが最も安定
        title: str | None = None
        title_elements = item_element.find_elements(by_xpath, './/span[@data-testid="thumbnail-item-name"]')
        if title_elements and title_elements[0].text:
            title = title_elements[0].text
        else:
            # フォールバック: itemName クラスを持つ span から取得
            title_elements = item_element.find_elements(by_xpath, ".//span[contains(@class, 'itemName')]")
            if title_elements and title_elements[0].text:
                title = title_elements[0].text

        # 価格を取得
        price: int | None = None

        # 方法1: span.number__xxxxx クラスから取得
        price_number_elements = item_element.find_elements(by_xpath, ".//span[contains(@class, 'number__')]")
        if price_number_elements and price_number_elements[0].text:
            price_text = price_number_elements[0].text
            price_str = price_text.replace("¥", "").replace(",", "").strip()
            with contextlib.suppress(ValueError):
                price = int(price_str)

        # 方法2: aria-label 属性から価格とタイトルを取得（lazy loading 対策）
        if price is None or title is None:
            # div[@role="img"] の aria-label から取得
            # 例: "iPad（第9世代）10.2インチ Wi-Fiモデル 64GB スペースグレイの画像 30,000円"
            img_elements = item_element.find_elements(by_xpath, './/div[@role="img"][@aria-label]')
            if img_elements:
                aria_label = img_elements[0].get_attribute("aria-label")
                if aria_label:
                    # 価格を抽出（"30,000円" のような形式）
                    price_match = re.search(r"([\d,]+)円", aria_label)
                    if price_match and price is None:
                        with contextlib.suppress(ValueError):
                            price = int(price_match.group(1).replace(",", ""))

                    # タイトルを抽出（"の画像" の前の部分）
                    if title is None:
                        title_match = re.match(r"(.+?)の画像", aria_label)
                        if title_match:
                            title = title_match.group(1)

        if not title or price is None:
            # デバッグ: aria-label の値を確認
            img_elements = item_element.find_elements(by_xpath, './/div[@role="img"][@aria-label]')
            aria_debug = None
            if img_elements:
                aria_debug = img_elements[0].get_attribute("aria-label")
            logging.debug("[Mercari] パース失敗: title=%s, price=%s, aria_label=%s", title, price, aria_debug)
            return None

        return my_lib.store.flea_market.SearchResult(name=title, url=url, price=price)

    except Exception:
        logging.exception("[Mercari] パース失敗")
        return None


def search(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    condition: my_lib.store.flea_market.SearchCondition,
    max_items: int | None = None,
    scroll_to_load: bool = False,
) -> list[my_lib.store.flea_market.SearchResult]:
    """メルカリで商品を検索する

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
    logging.info("[Mercari] 検索開始: keyword=%s", condition.keyword)
    logging.debug("[Mercari] 検索URL: %s", url)

    driver.get(url)

    if not _wait_for_search_results(driver, wait):
        return []

    # 出品形式「通常出品」に絞り込み
    # フィルタ適用後、検索結果の再読み込みを待機
    if _apply_normal_listing_filter(driver, wait) and not _wait_for_search_results(driver, wait):
        return []

    by_xpath = selenium.webdriver.common.by.By.XPATH

    results: list[my_lib.store.flea_market.SearchResult] = []
    parsed_urls: set[str] = set()  # 重複防止用

    item_elements = driver.find_elements(by_xpath, _ITEM_LIST_XPATH)
    logging.debug("[Mercari] ページ解析: %d 件発見", len(item_elements))

    for i, item_element in enumerate(item_elements):
        if max_items is not None and len(results) >= max_items:
            logging.info("[Mercari] 検索完了: %d 件", len(results))
            return results

        # スクロールが有効な場合、要素をビューポートにスクロールしてコンテンツをロード
        if scroll_to_load or i < 20:  # 最初の20件はスクロール不要なことが多い
            try:
                # 要素をビューポートにスクロール
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
                    item_element,
                )
                # lazy loading のためのコンテンツロード待機
                if i >= 20:  # 最初の20件以降はロードに時間がかかる
                    time.sleep(0.3)
            except selenium.common.exceptions.StaleElementReferenceException:
                logging.debug("[Mercari] 要素 %d がStale、スキップ", i + 1)
                continue

        result = _parse_search_item(item_element)
        if result is not None and result.url not in parsed_urls:
            results.append(result)
            parsed_urls.add(result.url)

    logging.info("[Mercari] 検索完了: %d 件", len(results))
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

    # 検索条件を構築
    price_min = int(price_min_str) if price_min_str else None
    price_max = int(price_max_str) if price_max_str else None
    max_count = int(max_count_str) if max_count_str else None
    dump_path = pathlib.Path(dump_path_str) if dump_path_str else None

    # max_count が 20 を超える場合は自動的にスクロールを有効にする
    if max_count is not None and max_count > 20:
        scroll_to_load = True

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
        results = search(driver, wait, condition, max_items=max_count, scroll_to_load=scroll_to_load)

        # ダンプパスが指定された場合は、検索結果ページをダンプ
        if dump_path:
            dump_path.mkdir(parents=True, exist_ok=True)
            my_lib.selenium_util.dump_page(driver, 0, dump_path)
            logging.info("ページをダンプしました: %s", dump_path)

            # 最初の商品のHTMLを個別にダンプ
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
        # NOTE: undetected_chromedriver の __del__ で ImportError が出ることがあるが、
        # ドライバは正常終了済みのため実害なし（ライブラリ側の既知の問題）
