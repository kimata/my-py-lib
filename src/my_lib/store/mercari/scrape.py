#!/usr/bin/env python3
"""メルカリの出品一覧を巡回し、各アイテムに対して処理を実行する。

ブラウザ操作は `my_lib.browser.Page` 抽象のみに依存する（Selenium / Patchright 非依存）。
呼び出し側は `page()` スコープ内で得た Page を渡し、`item_func_list` の各関数は
``func(page, item, debug_mode)`` の形で呼ばれる。
"""

from __future__ import annotations

import contextlib
import logging
import random
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import my_lib.browser
import my_lib.store.mercari.config
from my_lib.browser import Xpath

if TYPE_CHECKING:
    import my_lib.store.mercari.progress
    from my_lib.browser import Element, Page

_TRY_COUNT: int = 3
_LOAD_URL_TIMEOUT_SEC: int = 30
_ITEM_LIST_XPATH: str = '//ul[@data-testid="listed-item-list"]//li'
_POPUP_CLOSE_XPATHS: list[str] = [
    # NOTE: 右上のポップアップの閉じるボタン（オークション案内など）
    '//div[contains(@class, "merIconButton")][@aria-label="close"]/button',
    # NOTE: モーダルダイアログのキャンセルボタン（アンバサダーツールバー非表示確認など）
    '//button[contains(text(), "キャンセル")]',
]
_DIALOG_XPATH: str = '//*[@role="dialog" and @aria-modal="true"]'
_ACCOUNT_BUTTON_XPATH: str = '//button[@data-testid="account-button"]'
_MORE_BUTTON_XPATH: str = '//div[contains(@class, "merButton")]/button[contains(text(), "もっと見る")]'
_PAGE_ERROR_XPATH: str = '//div[contains(@class, "titleContainer")]/p[text()="エラーが発生しました"]'

ItemFunc = Callable[["Page", my_lib.store.mercari.config.MercariItem, bool], Any]


def random_sleep(sec: float) -> None:
    """検知回避のため、指定秒数の 0.8〜1.2 倍のランダムな時間スリープする。"""
    ratio = 0.8
    time.sleep((sec * ratio) + (sec * (1 - ratio) * 2) * random.random())  # noqa: S311


def iter_items_on_display(
    page: Page,
    debug_mode: bool,
    item_func_list: list[ItemFunc],
    progress_observer: my_lib.store.mercari.progress.ProgressObserver | None = None,
    max_consecutive_failures: int | None = None,
) -> None:
    """出品中の全アイテムに対して item_func_list の処理を実行する。

    Args:
        page: ログイン済みのページ。
        debug_mode: True なら最初のアイテムだけ処理する。
        item_func_list: ``func(page, item, debug_mode)`` の形で呼ばれる処理のリスト。
        progress_observer: 進捗通知先。
        max_consecutive_failures: アイテム単位の処理が連続して失敗した場合に中断する閾値。
            None の場合は最初の失敗で即座に例外を送出する（従来動作）。
            指定した場合、失敗したアイテムはスキップして次に進み、
            連続失敗数が閾値に達した時点で最後の例外を送出する。

    """
    # NOTE: ログイン直後にキャンペーン用のモーダルダイアログが表示され、account-button への
    # クリックが遮断されることがあるため、先にポップアップを閉じる。
    close_popup(page)

    _click_account_button_with_retry(page)
    page.wait_clickable(Xpath('//a[contains(text(), "出品した商品")]')).click()

    page.wait_present(Xpath(_ITEM_LIST_XPATH))

    time.sleep(1)

    list_url = page.url

    # NOTE: リトライ付きでアイテムを列挙させたいので、_load_url を使う。
    _load_url(page, list_url)

    item_count = len(page.find_all(Xpath(_ITEM_LIST_XPATH)))

    logging.info("%d 個の出品があります。", item_count)

    if progress_observer is not None:
        progress_observer.on_total_count(item_count)

    consecutive_failures = 0
    for i in range(1, item_count + 1):
        try:
            _execute_item_with_retry(
                page, debug_mode, item_count, i, item_func_list, progress_observer, list_url
            )
            consecutive_failures = 0
        except Exception:
            if max_consecutive_failures is None:
                raise

            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                logging.error("%d アイテム連続で処理に失敗したため、中断します。", consecutive_failures)
                raise

            logging.warning(
                "アイテムの処理に失敗しましたが、次のアイテムに進みます。(連続失敗: %d/%d)",
                consecutive_failures,
                max_consecutive_failures,
            )

        if debug_mode:
            break

        random_sleep(10)

        # NOTE: _load_url は内部的でリトライ処理が入っているので、try では囲わない。
        _load_url(page, list_url)


def _execute_item_with_retry(
    page: Page,
    debug_mode: bool,
    item_count: int,
    index: int,
    item_func_list: list[ItemFunc],
    progress_observer: my_lib.store.mercari.progress.ProgressObserver | None,
    list_url: str,
) -> None:
    for retry in range(_TRY_COUNT):
        try:
            item = _execute_item(page, debug_mode, item_count, index, item_func_list, progress_observer)
            if progress_observer is not None and item is not None:
                progress_observer.on_item_complete(index, item_count, item)
            return
        except Exception:
            logging.exception("エラーが発生しました。")
            if retry == _TRY_COUNT - 1:
                raise

            logging.warning("リトライします。(retry=%d)", retry + 1)
            random_sleep(10)
            _load_url(page, list_url)


def _load_url(page: Page, url: str) -> None:
    for retry in range(_TRY_COUNT):
        try:
            page.goto(url)
            page.wait_present(Xpath(_ITEM_LIST_XPATH), timeout=_LOAD_URL_TIMEOUT_SEC)
            _expand_all(page)
            return
        except (my_lib.browser.WaitTimeoutError, my_lib.browser.NavigationError):
            logging.exception("エラーが発生しました。")

            if retry == _TRY_COUNT - 1:
                logging.warning("エラーが %d 回続いたので諦めます。", retry + 1)
                raise

            logging.warning("リトライします。(retry=%d)", retry + 1)
            random_sleep(10)


def _expand_all(page: Page) -> None:
    while page.exists(Xpath(_MORE_BUTTON_XPATH), visible=False):
        page.wait_clickable(Xpath(_MORE_BUTTON_XPATH)).click()

        page.wait_present(Xpath("//body"))
        time.sleep(2)


def _execute_item(
    page: Page,
    debug_mode: bool,
    item_count: int,
    index: int,
    item_func_list: list[ItemFunc],
    progress_observer: my_lib.store.mercari.progress.ProgressObserver | None = None,
) -> my_lib.store.mercari.config.MercariItem:
    item, item_link = _parse_item(page, index)

    logging.info(
        "[%d/%d] %s [%s] [%s円] [%s view] [%s favorite] を処理します。",
        index,
        item_count,
        item.name,
        item.id,
        f"{item.price:,}",
        f"{item.view:,}",
        f"{item.favorite:,}",
    )

    if progress_observer is not None:
        progress_observer.on_item_start(index, item_count, item)

    if item.is_stop != 0:
        logging.info("公開停止中のため、詳細ページへの遷移をスキップします。")
        return item

    # NOTE: ポップアップがリンクを覆い隠す場合があるため、先に閉じる
    close_popup(page)

    page.evaluate("() => window.scrollTo(0, 0)")
    # NOTE: アイテムにスクロールしてから、ヘッダーに隠れないようちょっと前に戻す
    item_link.scroll_into_view()
    page.evaluate("() => window.scrollTo(0, window.pageYOffset - 200)")
    item_link.click()

    _auto_reload(page)

    try:
        page.wait_text(Xpath("//h1"), re.sub(" +", " ", item.name))
    except my_lib.browser.WaitTimeoutError:
        logging.exception("Invalid title: %s", page.title)
        raise

    item_url = page.url

    fail_count = 0
    for item_func in item_func_list:
        while True:
            try:
                item_func(page, item, debug_mode)
                fail_count = 0
                break
            except (my_lib.browser.WaitTimeoutError, my_lib.browser.ElementNotFoundError):
                logging.exception("エラーが発生しました")
                fail_count += 1

                if fail_count >= _TRY_COUNT:
                    logging.warning("エラーが %d 回続いたので諦めます。", fail_count)
                    raise

                if page.url != item_url:
                    page.goto(item_url)

                random_sleep(10)

        time.sleep(10)

    return item


def _auto_reload(page: Page) -> None:
    page.wait_present(Xpath("//body"))

    if page.exists(Xpath(_PAGE_ERROR_XPATH), visible=False):
        logging.warning("ページの表示でエラーが発生したのでリロードします。")
        page.refresh()


def _parse_item(page: Page, index: int) -> tuple[my_lib.store.mercari.config.MercariItem, Element]:
    """一覧の index 番目（1 始まり）のアイテムを解析し、アイテムと詳細ページへのリンク要素を返す。"""
    time.sleep(5)
    item_xpath = f"{_ITEM_LIST_XPATH}[{index}]"

    item_element = page.find(Xpath(item_xpath))
    link = item_element.find(Xpath(".//a[@data-testid='listed-item']")) if item_element is not None else None
    name_element = (
        item_element.find(Xpath(".//p[@data-testid='item-label']")) if item_element is not None else None
    )
    price_elements = (
        item_element.find_all(Xpath(".//span[@data-testid='price']/span[2]"))
        if item_element is not None
        else []
    )

    if item_element is None or link is None or name_element is None or not price_elements:
        # NOTE: 一覧の描画が終わっていないと要素が欠けるため、リロードして取り直す
        page.refresh()
        time.sleep(5)
        return _parse_item(page, index)

    favorite_elements = item_element.find_all(
        Xpath(".//span[@data-testid='price']/following-sibling::div/div[1]/span")
    )
    view_elements = item_element.find_all(
        Xpath(".//span[@data-testid='price']/following-sibling::div/div[3]/span")
    )
    private_elements = item_element.find_all(Xpath(".//span[contains(text(), '公開停止中')]"))

    item_url = link.attr("href")
    if item_url is None:
        raise RuntimeError("Failed to get item URL")
    item_id = item_url.split("/")[-1]
    name = name_element.text
    price = int(price_elements[0].text.replace(",", ""))

    view = 0
    favorite = 0

    if view_elements:
        with contextlib.suppress(ValueError, AttributeError):
            view = int(view_elements[0].text)

    if favorite_elements:
        with contextlib.suppress(ValueError, AttributeError):
            favorite = int(favorite_elements[0].text)

    is_stop = 1 if private_elements else 0

    item = my_lib.store.mercari.config.MercariItem(
        id=item_id,
        url=item_url,
        name=name,
        price=price,
        view=view,
        favorite=favorite,
        is_stop=is_stop,
    )

    return item, link


def close_popup(page: Page) -> None:
    """ページ上に表示されているポップアップ・ダイアログを閉じる。

    既知の閉じるボタンの XPath に加え、ARIA 属性ベースの汎用判定と
    Escape キーのフォールバックを持つ。表示されていない場合は何もしない。
    """
    # NOTE: 既知のポップアップ閉じるボタン（互換維持）
    for xpath in _POPUP_CLOSE_XPATHS:
        for button in page.find_all(Xpath(xpath)):
            with contextlib.suppress(Exception):
                if button.is_visible():
                    button.click()
                    time.sleep(0.5)

    # NOTE: 汎用パターン: role=dialog かつ aria-modal=true なモーダルを汎用的に閉じる。
    # メルカリは React のスタイル付きコンポーネントで class 名がハッシュ化されるため、
    # ARIA 属性ベースで判定することで将来のキャンペーン用ダイアログにも追従できる。
    for dialog in page.find_all(Xpath(_DIALOG_XPATH)):
        if not dialog.is_visible():
            continue
        _close_dialog(page, dialog)

    # NOTE: コーチマーク型のポップアップ（「¥300オークションで注目を集めませんか？」等）は
    # role=dialog を持たず、全画面のオーバーレイでクリックを遮る。閉じるボタンは
    # aria-labelledby で非表示 span「閉じる」を参照する実装なので、ページ全体から探す。
    for button in page.find_all(Xpath("//button[@aria-labelledby]")):
        with contextlib.suppress(Exception):
            if button.is_visible() and _is_close_button(page, button):
                logging.info("ポップアップの閉じるボタンをクリックします。")
                button.click()
                time.sleep(0.5)


def _is_close_button(page: Page, button: Element) -> bool:
    """aria-labelledby が指す要素のテキストが「閉じる」/「Close」なら True。

    メルカリは非表示 span で閉じるラベルを提供し aria-labelledby で参照する実装が多い。
    非表示要素のテキストなので textContent で読む（text は可視テキストのみ）。
    """
    labelledby = button.attr("aria-labelledby")
    if not labelledby:
        return False
    label_elements = page.find_all(Xpath(f'//*[@id="{labelledby}"]'))
    if not label_elements:
        return False
    label_text = str(label_elements[0].evaluate("(el) => el.textContent") or "")
    return "閉じる" in label_text or "Close" in label_text


def _close_dialog(page: Page, dialog: Element) -> None:
    close_buttons = list(
        dialog.find_all(
            Xpath('.//button[@aria-label="閉じる" or @aria-label="close" or @aria-label="Close"]')
        )
    )

    if not close_buttons:
        for button in dialog.find_all(Xpath(".//button[@aria-labelledby]")):
            if _is_close_button(page, button):
                close_buttons.append(button)
                break

    for button in close_buttons:
        with contextlib.suppress(Exception):
            if button.is_visible():
                logging.info("ダイアログの閉じるボタンをクリックします。")
                button.click()
                time.sleep(0.5)
                return

    # NOTE: フォールバック: モーダルは Escape で閉じるのが Web 標準。
    # 閉じるボタンが特定できなかった場合の最終手段。
    with contextlib.suppress(Exception):
        logging.info("ダイアログを Escape キーで閉じます。")
        dialog.press("Escape")
        time.sleep(0.5)


def _click_account_button_with_retry(page: Page) -> None:
    try:
        page.wait_clickable(Xpath(_ACCOUNT_BUTTON_XPATH)).click()
    except Exception:  # NOTE: クリック遮断はバックエンド固有の例外で届くため広く捕捉する
        logging.warning("account-button のクリックが遮断されました。ポップアップを閉じてリトライします。")
        close_popup(page)
        time.sleep(0.5)
        page.wait_clickable(Xpath(_ACCOUNT_BUTTON_XPATH)).click()
