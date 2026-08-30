#!/usr/bin/env python3
"""
Amazon へのログインをを行います。

ブラウザ操作はバックエンド非依存の my_lib.browser.Page 越しに行う
（Selenium / Patchright を問わない）。

Usage:
  login.py [-c CONFIG] [-t TARGET] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import io
import logging
import pathlib
import random
import time
from typing import TYPE_CHECKING

import PIL.Image

import my_lib.browser
import my_lib.browser.helpers
import my_lib.notify.slack
import my_lib.store.amazon.captcha
import my_lib.store.captcha
from my_lib.browser import Xpath
from my_lib.store.amazon.credentials import AmazonLoginConfig

if TYPE_CHECKING:
    from my_lib.browser import Element, Page

_LOGIN_URL: str = "https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2Fref%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=jpflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"

_LOGIN_MARK_XPATH: str = '//span[contains(text(), "アカウント＆リスト")]'

# NOTE: 認証チャレンジ系ページ（画像クイズ・SMS 認証）の footer は
# <div id="footer" class="a-section"> で class に footer を含まないため、id も見る。
# id を見ないとパスワード送信後にクイズが出た場合ここでタイムアウトし、
# 後段の _handle_quiz / _handle_phone_verification に到達できない。
_FOOTER_XPATH = '//div[@id="footer" or contains(@class, "footer") or contains(@class, "Footer")]'

# 「ショッピングを続ける」ボタン（CAPTCHA 検証ページ）
_CONTINUE_SHOPPING_BUTTON_XPATH = (
    '//span[contains(@class, "a-button")]//button[normalize-space(text()) = "ショッピングを続ける"]'
)

# 503 エラーページ
_503_ERROR_TITLE = "ご迷惑をおかけしています"
_503_CONTINUE_LINK_XPATH = '//a[contains(@href, "ref=cs_503_link")]'

_MAX_ERROR_PAGE_RETRIES = 2


def _find(page: Page, xpath: str) -> Element:
    """要素を 1 つ取得する（存在しなければ例外）。"""
    element = page.find(Xpath(xpath))
    if element is None:
        raise RuntimeError(f"要素が見つかりません: {xpath}")
    return element


def _click_if_present(page: Page, xpath: str) -> bool:
    """指定 XPath の要素が存在すればクリックする（存在しなければ何もしない）。"""
    element = page.find(Xpath(xpath))
    if element is None:
        return False
    try:
        element.click()
    except my_lib.browser.BrowserError:
        return False
    return True


def _wait_for_footer(page: Page, *, _retry_count: int = 0) -> None:
    """フッターが表示されるまで待機（エラーページ自動対応付き）

    Amazon がボット検出や一時エラーで「ショッピングを続ける」ページを返す場合、
    自動でボタン/リンクをクリックしてリトライする。
    """
    try:
        page.wait_visible(Xpath(_FOOTER_XPATH))
    except my_lib.browser.WaitTimeoutError:
        if _retry_count >= _MAX_ERROR_PAGE_RETRIES:
            raise

        # パターン1: CAPTCHA 検証ページの「ショッピングを続ける」ボタン
        if _click_if_present(page, _CONTINUE_SHOPPING_BUTTON_XPATH):
            logging.warning("CAPTCHA 検証ページを検出、「ショッピングを続ける」をクリック: %s", page.url)
            _wait_for_footer(page, _retry_count=_retry_count + 1)
            return

        # パターン2: 503 エラーページの「ショッピングを続ける」リンク
        if _503_ERROR_TITLE in page.title:
            logging.warning("503 エラーページを検出、「ショッピングを続ける」をクリック: %s", page.url)
            _click_if_present(page, _503_CONTINUE_LINK_XPATH)
            time.sleep(3)
            _wait_for_footer(page, _retry_count=_retry_count + 1)
            return

        raise


def _resolve_puzzle(
    page: Page,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
) -> None:
    logging.info("Try to resolve PUZZLE")

    my_lib.store.amazon.captcha.resolve(
        page,
        slack_config,
        {"image": '//img[@alt="captcha"]', "text": '//input[@name="cvf_captcha_input"]'},
    )

    _find(page, '//input[@name="cvf_captcha_captcha_action"]').click()

    _wait_for_footer(page)
    time.sleep(0.1)


def _handle_email_input(
    page: Page,
    login_config: AmazonLoginConfig,
) -> None:
    """メールアドレス入力処理"""
    email_xpath = '//input[@type="email" and (@id="ap_email_login" or @id="ap_email")]'
    if page.exists(Xpath(email_xpath), visible=False):
        logging.debug("Input email")
        email_input = _find(page, email_xpath)
        email_input.clear()
        email_input.type(login_config.user)

        logging.debug("Click continue")
        if page.exists(Xpath('//input[@type="submit"]'), visible=False):
            _find(page, '//input[@type="submit"]').click()
            time.sleep(3)


def _handle_password_input(
    page: Page,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
) -> None:
    """パスワード入力処理"""
    if not page.exists(Xpath('//input[@id="ap_password"]'), visible=False):
        return

    logging.debug("Input password")
    pass_input = page.wait_clickable(Xpath('//input[@id="ap_password"]'))
    pass_input.evaluate("(el, value) => { el.value = value; }", login_config.password)

    if page.exists(Xpath('//input[@name="rememberMe"]'), visible=False):
        remember_checkbox = _find(page, '//input[@name="rememberMe"]')
        if not remember_checkbox.evaluate("el => el.checked"):
            logging.debug("Check remember")
            remember_checkbox.click()

    if page.exists(Xpath('//input[@id="auth-captcha-guess"]'), visible=False):
        if slack_config is None:
            raise ValueError("captcha 設定がありません")
        my_lib.store.amazon.captcha.resolve(
            page,
            slack_config,
            {
                "image": '//img[@id="auth-captcha-image"]',
                "text": '//input[@id="auth-captcha-guess"]',
            },
        )

    time.sleep(0.1)

    logging.debug("Click submit")
    _find(page, '//input[@id="signInSubmit"]').click()

    _wait_for_footer(page)


def _handle_quiz(
    page: Page,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    dump_path: pathlib.Path,
) -> None:
    if not page.exists(Xpath('//h1[contains(normalize-space(.), "クイズ")]'), visible=False):
        return

    file_id = my_lib.store.captcha.send_challenge_image_slack(
        slack_config,
        "Amazon Login",
        PIL.Image.open(io.BytesIO(_find(page, '//div[contains(@class, "amzn-captcha-modal")]').screenshot())),
        "画像クイズ",
    )

    if file_id is None:
        raise RuntimeError("Failed to send challenge image to Slack")
    captcha = my_lib.store.captcha.recv_response_image_slack(slack_config, file_id)

    if captcha is None:
        raise RuntimeError("クイズを解決できませんでした。")

    digits = [int(ch) for ch in captcha if ch.isdigit()]
    for digit in digits:
        xpath = f'//canvas/button[normalize-space(text())="{digit}"]'
        _find(page, xpath).click()
        time.sleep(0.2)

    my_lib.browser.helpers.dump_page(
        page,
        random.randint(0, 99),  # noqa: S311
        dump_path,
    )

    _find(page, '//button[@id="amzn-btn-verify-internal"]').click()
    time.sleep(2)


def _handle_phone_verification(
    page: Page,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    dump_path: pathlib.Path,
) -> None:
    """携帯電話番号確認画面の処理（SMS認証）"""
    phone_verify_xpath = '//h1[contains(., "携帯電話番号を確認する")]'
    if not page.exists(Xpath(phone_verify_xpath), visible=False):
        return

    logging.info("SMS認証が要求されました。")

    my_lib.browser.helpers.dump_page(
        page,
        random.randint(0, 99),  # noqa: S311
        dump_path,
    )

    logging.info("Slack に SMS で送られてきた認証番号を入力してください")
    ts = my_lib.store.captcha.send_request_text_slack(
        slack_config,
        "Amazon",
        "📱 SMS で送られてきた認証番号を入力してください",
    )
    if ts is None:
        raise RuntimeError("Failed to send request text to Slack")

    code = my_lib.store.captcha.recv_response_text_slack(slack_config, ts)
    if code is None:
        raise RuntimeError("Failed to receive authentication code")

    logging.info("認証番号を入力します。")
    _find(page, '//input[@id="cvf-input-code"]').type(code)

    logging.info("「携帯電話番号を確認する」ボタンをクリックします。")
    _find(page, '//span[@id="cvf-submit-otp-button"]//input[@type="submit"]').click()

    time.sleep(0.5)

    _wait_for_footer(page)

    my_lib.browser.helpers.dump_page(
        page,
        random.randint(0, 99),  # noqa: S311
        dump_path,
    )

    my_lib.notify.slack.send(
        slack_config,
        slack_config.captcha.channel.name,
        my_lib.notify.slack.format_simple("CAPTCHA", "🎉 成功しました"),
        thread_ts=ts,
    )

    logging.info("SMS認証が完了しました。")


def _execute_impl(
    page: Page,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    login_mark_xpath: str,
) -> None:
    _wait_for_footer(page)

    if page.exists(Xpath(login_mark_xpath), visible=False):
        logging.info("Login succeeded")
        return

    if page.exists(Xpath('//input[@name="cvf_captcha_input"]'), visible=False):
        _resolve_puzzle(page, slack_config)

    _handle_email_input(page, login_config)
    _handle_password_input(page, login_config, slack_config)

    _handle_quiz(page, slack_config, login_config.dump_path)
    _handle_phone_verification(page, slack_config, login_config.dump_path)

    _wait_for_footer(page)
    time.sleep(0.1)


def execute(
    page: Page,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    login_url: str = _LOGIN_URL,
    login_mark_xpath: str = _LOGIN_MARK_XPATH,
    retry: int = 2,
) -> bool:
    logging.info("Login start")

    page.goto(login_url)

    for i in range(retry):
        _execute_impl(page, login_config, slack_config, login_mark_xpath)

        if page.exists(Xpath(login_mark_xpath), visible=False):
            logging.info("Login sccessful!")
            return True

        if i != (retry - 1):
            logging.warning("Login retry")

            my_lib.browser.helpers.dump_page(
                page,
                random.randint(0, 99),  # noqa: S311
                login_config.dump_path,
            )

    logging.error("Login fail")

    return False


if __name__ == "__main__":
    # TEST Code
    from typing import Any

    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)
    login_config = AmazonLoginConfig.parse(config["store"]["amazon"], pathlib.Path(config["data"]["dump"]))

    profile = my_lib.browser.BrowserProfile(name="Test", data_dir=pathlib.Path(config["data"]["selenium"]))
    manager = my_lib.browser.BrowserManager(profile)
    page = manager.get_page()

    if "slack" not in config:
        raise ValueError("slack 設定がありません")
    slack_config_parsed = my_lib.notify.slack.SlackConfig.parse(config["slack"])
    if not isinstance(
        slack_config_parsed,
        my_lib.notify.slack.SlackConfig | my_lib.notify.slack.SlackCaptchaOnlyConfig,
    ):
        raise ValueError("slack 設定に captcha の設定がありません")
    slack_config: my_lib.notify.slack.HasCaptchaConfig = slack_config_parsed

    try:
        execute(page, login_config, slack_config)
    except Exception:
        logging.exception("URL: %s", page.url)

        my_lib.browser.helpers.dump_page(
            page,
            random.randint(0, 99),  # noqa: S311
            login_config.dump_path,
        )

    manager.quit()
