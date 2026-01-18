#!/usr/bin/env python3
"""
Slack で通知を行います。

Usage:
  slack.py [-c CONFIG] [-m MESSAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -m MESSAGE        : 送信するメッセージ。[default: TEST]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import collections
import gzip
import json
import logging
import math
import os
import pathlib
import tempfile
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

import dacite
import slack_sdk
import slack_sdk.errors
import slack_sdk.web.slack_response
from PIL import Image

import my_lib.footprint

_NOTIFY_FOOTPRINT: pathlib.Path = pathlib.Path("/dev/shm/notify/slack/error")  # noqa: S108
_INTERVAL_MIN: int = 60

_SIMPLE_TMPL = """\
[
    {{
        "type": "header",
    "text": {{
            "type": "plain_text",
        "text": "{title}",
            "emoji": true
        }}
    }},
    {{
        "type": "section",
        "text": {{
            "type": "mrkdwn",
        "text": {message}
    }}
    }}
]
"""


@dataclass(frozen=True)
class FormattedMessage:
    text: str
    json: list[dict[str, Any]]


@dataclass(frozen=True)
class AttachImage:
    data: Image.Image
    text: str


@dataclass(frozen=True)
class SlackChannelConfig:
    """Slack チャンネル設定"""

    name: str
    id: str | None = None  # info チャンネルでは id は不要


@dataclass(frozen=True)
class SlackInfoConfig:
    """Slack 情報通知設定"""

    channel: SlackChannelConfig


@dataclass(frozen=True)
class SlackCaptchaConfig:
    """Slack CAPTCHA 通知設定"""

    channel: SlackChannelConfig


@dataclass(frozen=True)
class SlackErrorConfig:
    """Slack エラー通知設定"""

    channel: SlackChannelConfig
    interval_min: int


# === Protocol 定義 ===
class HasBotToken(Protocol):
    """Slack bot_token を持つオブジェクトの Protocol"""

    @property
    def bot_token(self) -> str: ...


class HasErrorConfig(HasBotToken, Protocol):
    """Slack エラー通知設定の Protocol"""

    @property
    def error(self) -> SlackErrorConfig: ...

    @property
    def from_name(self) -> str: ...


class HasInfoConfig(HasBotToken, Protocol):
    """Slack 情報通知設定の Protocol"""

    @property
    def info(self) -> SlackInfoConfig: ...


class HasCaptchaConfig(HasBotToken, Protocol):
    """Slack CAPTCHA 通知設定の Protocol"""

    @property
    def captcha(self) -> SlackCaptchaConfig: ...


# === 具象クラス ===
@dataclass(frozen=True)
class SlackEmptyConfig:
    """Slack 設定が存在しない場合のプレースホルダー"""

    pass


@dataclass(frozen=True)
class SlackErrorOnlyConfig:
    """error のみの Slack 設定"""

    bot_token: str
    from_name: str
    error: SlackErrorConfig


@dataclass(frozen=True)
class SlackCaptchaOnlyConfig:
    """captcha のみの Slack 設定"""

    bot_token: str
    from_name: str
    captcha: SlackCaptchaConfig


@dataclass(frozen=True)
class SlackErrorInfoConfig:
    """error + info の Slack 設定"""

    bot_token: str
    from_name: str
    info: SlackInfoConfig
    error: SlackErrorConfig


@dataclass(frozen=True)
class SlackConfig:
    """error + info + captcha 全ての Slack 設定"""

    bot_token: str
    from_name: str
    info: SlackInfoConfig
    captcha: SlackCaptchaConfig
    error: SlackErrorConfig

    @classmethod
    def parse(cls, data: dict[str, Any]) -> SlackConfigTypes:
        """
        Slack 設定をパースする.

        存在するフィールドに応じて適切な Config クラスを返す。
        設定が空または不十分な場合は SlackEmptyConfig を返す。
        dacite を使用して辞書から dataclass への変換を行う。
        """
        # 空の設定の場合
        if not data or "bot_token" not in data:
            return SlackEmptyConfig()

        has_error = "error" in data
        has_info = "info" in data
        has_captcha = "captcha" in data

        # error も captcha もない場合は空として扱う
        if not has_error and not has_captcha:
            return SlackEmptyConfig()

        # 辞書を前処理: "from" → "from_name" にリネーム
        normalized_data = _normalize_slack_data(data)

        # 設定の組み合わせに応じて適切な型を決定
        config_type = _determine_slack_config_type(has_error, has_info, has_captcha)
        if config_type is None:
            return SlackEmptyConfig()

        return dacite.from_dict(
            data_class=config_type,
            data=normalized_data,
            config=dacite.Config(strict=False),
        )


# 型エイリアス
SlackConfigTypes: TypeAlias = (
    SlackConfig | SlackErrorInfoConfig | SlackErrorOnlyConfig | SlackCaptchaOnlyConfig | SlackEmptyConfig
)


# NOTE: テスト用
_thread_local = threading.local()
_notify_hist: collections.defaultdict[str, list[str]] = collections.defaultdict(lambda: [])
_hist_lock = threading.Lock()  # スレッドセーフティ用ロック


# NOTE: 公開関数のデフォルト引数で参照されるため、公開関数より前に定義
def format_simple(title: str, message: str) -> FormattedMessage:
    return FormattedMessage(
        text=message,
        json=json.loads(_SIMPLE_TMPL.format(title=title, message=json.dumps(message))),
    )


def info(
    config: HasInfoConfig | SlackEmptyConfig,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    if isinstance(config, SlackEmptyConfig):
        return None
    title = "Info: " + title
    return _split_send(config.bot_token, config.info.channel.name, title, message, formatter)


def error(
    config: HasErrorConfig | SlackEmptyConfig,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    if isinstance(config, SlackEmptyConfig):
        return None
    title = "Error: " + title

    _hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(_NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return None

    thread_ts = _split_send(config.bot_token, config.error.channel.name, title, message, formatter)

    my_lib.footprint.update(_NOTIFY_FOOTPRINT)

    return thread_ts


def error_with_image(
    config: HasErrorConfig | SlackEmptyConfig,
    title: str,
    message: str,
    attach_img: AttachImage | None,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    if isinstance(config, SlackEmptyConfig):
        return None
    title = "Error: " + title

    _hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(_NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return None

    thread_ts = _split_send(config.bot_token, config.error.channel.name, title, message, formatter)

    if attach_img is not None:
        ch_id = config.error.channel.id
        if ch_id is None:
            raise ValueError("error channel id is not configured")

        _upload_image(config.bot_token, ch_id, title, attach_img.data, attach_img.text, thread_ts)

    my_lib.footprint.update(_NOTIFY_FOOTPRINT)

    return thread_ts


def notify_error_with_page(
    config: HasErrorConfig | SlackEmptyConfig,
    title: str,
    exception: Exception,
    screenshot: Image.Image | None,
    page_source: str | None,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    """エラーをスクリーンショットと page_source 付きで通知する

    例外情報をトレースバック付きで通知し、スクリーンショットを添付する。
    page_source が指定された場合は gzip 圧縮してスレッドに添付する。

    Args:
        config: Slack 設定（error チャンネル設定を含む）
        title: エラータイトル
        exception: 発生した例外
        screenshot: スクリーンショット画像（PIL.Image.Image）
        page_source: ページの HTML ソース
        formatter: メッセージフォーマッタ（デフォルト: format_simple）

    Returns:
        スレッドのタイムスタンプ（通知失敗時は None）

    Examples:
        my_lib.selenium_util.error_handler と組み合わせて使用::

            def on_error(exc, screenshot, page_source):
                my_lib.notify.slack.notify_error_with_page(
                    config, "処理に失敗", exc, screenshot, page_source
                )

            with my_lib.selenium_util.error_handler(driver, on_error=on_error):
                do_something()

    """
    if isinstance(config, SlackEmptyConfig):
        return None

    message = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    attach_img: AttachImage | None = None
    if screenshot is not None:
        attach_img = AttachImage(data=screenshot, text="screenshot")

    thread_ts = error_with_image(config, title, message, attach_img, formatter)

    # page_source を gzip 圧縮してスレッドに添付
    if page_source is not None and thread_ts is not None:
        ch_id = config.error.channel.id
        if ch_id is not None:
            _attach_page_source_gzip(config, ch_id, page_source, thread_ts)

    return thread_ts


def _attach_page_source_gzip(
    config: HasBotToken,
    ch_id: str,
    page_source: str,
    thread_ts: str,
) -> None:
    """page_source を gzip 圧縮してスレッドに添付"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".html.gz", delete=False) as tmp:
            tmp_path = pathlib.Path(tmp.name)

        with gzip.open(tmp_path, "wt", encoding="utf-8") as gz:
            gz.write(page_source)

        _upload_file(config.bot_token, ch_id, tmp_path, "page_source.html.gz", None, thread_ts)

        tmp_path.unlink()
    except Exception:
        logging.debug("Failed to attach page source")


def send(
    config: HasBotToken | SlackEmptyConfig,
    ch_name: str,
    message: FormattedMessage,
    thread_ts: str | None = None,
) -> slack_sdk.web.slack_response.SlackResponse | None:
    if isinstance(config, SlackEmptyConfig):
        return None
    return _send(config.bot_token, ch_name, message, thread_ts)


def upload_image(
    config: HasBotToken | SlackEmptyConfig,
    ch_id: str,
    title: str,
    img: Image.Image,
    text: str,
    thread_ts: str | None = None,
) -> str | None:
    if isinstance(config, SlackEmptyConfig):
        return None
    return _upload_image(config.bot_token, ch_id, title, img, text, thread_ts)


def attach_file(
    config: HasBotToken | SlackEmptyConfig,
    ch_id: str,
    file_path: pathlib.Path,
    title: str | None = None,
    initial_comment: str | None = None,
    thread_ts: str | None = None,
) -> str | None:
    """ファイルを Slack チャンネルに添付する

    Args:
        config: Slack 設定（bot_token を含む）
        ch_id: チャンネル ID
        file_path: 添付するファイルのパス
        title: ファイルのタイトル（省略時はファイル名）
        initial_comment: ファイルに付けるコメント
        thread_ts: スレッドのタイムスタンプ（指定時はスレッドに添付）

    Returns:
        アップロードされたファイルの ID、失敗時は None
    """
    if isinstance(config, SlackEmptyConfig):
        return None
    return _upload_file(config.bot_token, ch_id, file_path, title, initial_comment, thread_ts)


def _normalize_slack_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Slack 設定辞書を正規化する.

    "from" キーを "from_name" にリネームし、
    不要なキー（info, captcha など）を必要に応じて除外する。
    """
    result = dict(data)

    # "from" → "from_name" にリネーム（Python の予約語を回避）
    if "from" in result:
        result["from_name"] = result.pop("from")

    return result


def _determine_slack_config_type(
    has_error: bool, has_info: bool, has_captcha: bool
) -> type[SlackConfig | SlackErrorInfoConfig | SlackErrorOnlyConfig | SlackCaptchaOnlyConfig] | None:
    """
    設定の組み合わせに応じて適切な Slack 設定クラスを返す.

    Returns:
        適切な設定クラス。不正な組み合わせの場合は None。

    """
    # 全て揃っている場合
    if has_error and has_info and has_captcha:
        return SlackConfig

    # error + info
    if has_error and has_info and not has_captcha:
        return SlackErrorInfoConfig

    # error のみ
    if has_error and not has_info and not has_captcha:
        return SlackErrorOnlyConfig

    # captcha のみ
    if has_captcha and not has_error and not has_info:
        return SlackCaptchaOnlyConfig

    # 中途半端なパターン: error + captcha (info なし)
    if has_error and has_captcha and not has_info:
        logging.warning(
            "Slack 設定が不完全です。SlackErrorOnlyConfig として処理します。captcha は無視されます。"
        )
        return SlackErrorOnlyConfig

    # 中途半端なパターン: info + captcha (error なし)
    if has_info and has_captcha and not has_error:
        logging.warning(
            "Slack 設定が不完全です。SlackCaptchaOnlyConfig として処理します。info は無視されます。"
        )
        return SlackCaptchaOnlyConfig

    # info のみ、または何もない場合
    return None


def _send(
    token: str, ch_name: str, message: FormattedMessage, thread_ts: str | None = None
) -> slack_sdk.web.slack_response.SlackResponse | None:
    try:
        client = slack_sdk.WebClient(token=token)

        kwargs: dict[str, Any] = {
            "channel": ch_name,
            "text": message.text,
            "blocks": message.json,
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        return client.chat_postMessage(**kwargs)
    except slack_sdk.errors.SlackClientError:
        logging.exception("Failed to send Slack message")
        return None


def _split_send(
    token: str,
    ch_name: str,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    LINE_SPLIT = 20

    logging.info("Post slack channel: %s", ch_name)

    if not message or not message.strip():
        logging.warning("Empty message, skipping Slack notification")
        return None

    message_lines = message.splitlines()
    total = math.ceil(len(message_lines) / LINE_SPLIT)
    thread_ts: str | None = None

    for i in range(0, len(message_lines), LINE_SPLIT):
        # メッセージ内容を事前に生成
        message_content = "\n".join(message_lines[i : i + LINE_SPLIT])

        # 空のメッセージはスキップ
        if not message_content or not message_content.strip():
            continue

        split_title = title if total == 1 else f"{title} ({(i // LINE_SPLIT) + 1}/{total})"

        # 最初のメッセージを送信
        if i == 0:
            response = _send(
                token,
                ch_name,
                formatter(split_title, message_content),
            )
            # 最初のメッセージのタイムスタンプを保存（スレッドがない場合でも画像投稿で使用）
            if response:
                thread_ts = response.get("ts")
        elif thread_ts:
            # 2つ以上に分割される場合は、2番目以降をスレッドへの返信として送信
            try:
                client = slack_sdk.WebClient(token=token)
                formatted_msg = formatter(split_title, message_content)
                client.chat_postMessage(
                    channel=ch_name,
                    text=formatted_msg.text,
                    blocks=formatted_msg.json,
                    thread_ts=thread_ts,
                )
            except slack_sdk.errors.SlackClientError:
                logging.exception("Failed to send Slack message in thread")
        else:
            # フォールバック: thread_tsが取得できなかった場合は通常通り送信
            _send(
                token,
                ch_name,
                formatter(split_title, message_content),
            )

        time.sleep(1)

    return thread_ts


def _upload_image(
    token: str,
    ch_id: str,
    title: str,
    img: Image.Image,
    text: str,
    thread_ts: str | None = None,
) -> str | None:
    client = slack_sdk.WebClient(token=token)

    with tempfile.TemporaryDirectory() as dname:
        img_path = pathlib.Path(dname) / "image.png"
        img.save(img_path)

        try:
            kwargs: dict[str, Any] = {
                "channel": ch_id,
                "file": str(img_path),
                "title": title,
                "initial_comment": text,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            resp: Any = client.files_upload_v2(**kwargs)

            return resp["files"][0]["id"]
        except slack_sdk.errors.SlackApiError:
            logging.exception("Failed to send Slack message")

            return None


def _upload_file(
    token: str,
    ch_id: str,
    file_path: pathlib.Path,
    title: str | None = None,
    initial_comment: str | None = None,
    thread_ts: str | None = None,
) -> str | None:
    client = slack_sdk.WebClient(token=token)

    try:
        kwargs: dict[str, Any] = {
            "channel": ch_id,
            "file": str(file_path),
        }
        if title:
            kwargs["title"] = title
        else:
            kwargs["title"] = file_path.name
        if initial_comment:
            kwargs["initial_comment"] = initial_comment
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        resp: Any = client.files_upload_v2(**kwargs)

        return resp["files"][0]["id"]
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to upload file to Slack")

        return None


# NOTE: テスト用
def _interval_clear() -> None:
    my_lib.footprint.clear(_NOTIFY_FOOTPRINT)


# NOTE: テスト用
def _hist_clear() -> None:
    _hist_get(True).clear()
    _hist_get(False).clear()


# NOTE: テスト用
def _hist_add(message: str) -> None:
    _hist_get(True).append(message)
    _hist_get(False).append(message)


# NOTE: テスト用
def _hist_get(is_thread_local: bool = True) -> list[str]:
    global _thread_local
    global _notify_hist
    global _hist_lock

    worker = os.environ.get("PYTEST_XDIST_WORKER", "0")

    if is_thread_local:
        # スレッドセーフな初期化（Double-checked locking パターン）
        if not hasattr(_thread_local, "notify_hist"):
            with _hist_lock:
                if not hasattr(_thread_local, "notify_hist"):
                    _thread_local.notify_hist = collections.defaultdict(lambda: [])

        return _thread_local.notify_hist[worker]
    else:
        return _notify_hist[worker]


if __name__ == "__main__":
    # TEST Code
    import sys

    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    raw_config = my_lib.config.load(config_file)

    if "slack" not in raw_config:
        logging.warning("Slack の設定が記載されていません。")
        sys.exit(-1)

    slack_config = SlackConfig.parse(raw_config["slack"])

    if isinstance(slack_config, SlackConfig | SlackErrorInfoConfig):
        info(slack_config, "Test", "This is test")
    if isinstance(slack_config, SlackConfig | SlackErrorInfoConfig | SlackErrorOnlyConfig):
        error(slack_config, "Test", "This is test")
