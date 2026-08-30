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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import my_lib.browser
from my_lib.browser import Xpath
from my_lib.browser.protocol import Page

if TYPE_CHECKING:
    from typing import Any


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


def _wait_for_page_load(page: Page) -> None:
    """ページの読み込みを待機する"""
    # //body は常に即時存在するため、実際に抽出対象となる商品タイトル要素の
    # 出現を待つ（負荷時の描画遅れによるタイトル取得失敗を防ぐ）
    try:
        page.wait_visible(Xpath(_TITLE_XPATH))
    except my_lib.browser.WaitTimeoutError:
        logging.warning("[Yodobashi] 読み込みタイムアウト")
        raise


def _extract_title(page: Page) -> str:
    """商品タイトルを取得する"""
    try:
        elements = page.find_all(Xpath(_TITLE_XPATH))
        if elements and elements[0].text:
            return elements[0].text
    except Exception:
        logging.exception("[Yodobashi] タイトル取得失敗")

    msg = "商品タイトルが見つかりません"
    raise ValueError(msg)


def _extract_price(page: Page) -> int | None:
    """価格を取得する"""
    try:
        elements = page.find_all(Xpath(_PRICE_XPATH))
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


def _extract_thumbnail_url(page: Page) -> str | None:
    """サムネイル画像のURLを取得する"""
    try:
        elements = page.find_all(Xpath(_THUMBNAIL_XPATH))
        if elements:
            url = elements[0].attr("value")
            if url:
                return url
    except Exception:
        logging.exception("[Yodobashi] サムネイルURL取得失敗")

    return None


def _check_in_stock(page: Page) -> bool:
    """在庫があるかどうかを確認する"""
    try:
        elements = page.find_all(Xpath(_OUT_OF_STOCK_XPATH))
        # 「販売休止」または「販売を終了しました」が見つかった場合は在庫なし
        return len(elements) == 0
    except Exception:
        logging.exception("[Yodobashi] 在庫確認失敗")
        # エラー時は在庫ありとして扱う（安全側に倒す）
        return True


def scrape(page: Page, url: str) -> ProductInfo:
    """商品ページから情報を取得する

    Args:
        page: 操作対象のページ
        url: 商品ページのURL

    Returns:
        商品情報

    """
    logging.info("[Yodobashi] 商品ページ取得開始: %s", url)

    page.goto(url)
    _wait_for_page_load(page)

    title = _extract_title(page)
    price = _extract_price(page)
    thumbnail_url = _extract_thumbnail_url(page)
    in_stock = _check_in_stock(page)

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

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    url = args["-u"]
    data_path = args["-s"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    logging.info("商品URL: %s", url)

    _profile = my_lib.browser.BrowserProfile(
        name="yodobashi_test",
        data_dir=pathlib.Path(data_path),
        stealth=True,
    )
    _manager = my_lib.browser.BrowserManager(_profile)
    _page = _manager.get_page()

    try:
        result = scrape(_page, url)

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
        _manager.quit()
