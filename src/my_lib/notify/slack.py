#!/usr/bin/env python3
"""
Slack で通知を行います。

Usage:
  slack.py [-c CONFIG] [-m MESSAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ。[default: TEST]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import collections
import json
import logging
import math
import os
import pathlib
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypedDict, Union

import slack_sdk
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


class FormattedMessage(TypedDict):
    text: str
    json: list[dict[str, Any]]


class AttachImage(TypedDict):
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
    """bot_token を持つことを表す Protocol"""

    @property
    def bot_token(self) -> str: ...


class HasError(HasBotToken, Protocol):
    """error 設定を持つことを表す Protocol"""

    @property
    def error(self) -> SlackErrorConfig: ...


class HasInfo(HasBotToken, Protocol):
    """info 設定を持つことを表す Protocol"""

    @property
    def info(self) -> SlackInfoConfig: ...


class HasCaptcha(HasBotToken, Protocol):
    """captcha 設定を持つことを表す Protocol"""

    @property
    def captcha(self) -> SlackCaptchaConfig: ...


# === 具象クラス ===
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


# 型エイリアス
SlackConfigTypes = Union[SlackConfig, SlackErrorInfoConfig, SlackErrorOnlyConfig, SlackCaptchaOnlyConfig]


# NOTE: テスト用
_thread_local = threading.local()
_notify_hist: collections.defaultdict[str, list[str]] = collections.defaultdict(lambda: [])  # noqa: PIE807
_hist_lock = threading.Lock()  # スレッドセーフティ用ロック


# NOTE: 公開関数のデフォルト引数で参照されるため、公開関数より前に定義
def format_simple(title: str, message: str) -> FormattedMessage:
    return {
        "text": message,
        "json": json.loads(_SIMPLE_TMPL.format(title=title, message=json.dumps(message))),
    }


def info(
    config: HasInfo,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Info: " + title
    _split_send(config.bot_token, config.info.channel.name, title, message, formatter)


def error(
    config: HasError,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Error: " + title

    _hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(_NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    _split_send(config.bot_token, config.error.channel.name, title, message, formatter)

    my_lib.footprint.update(_NOTIFY_FOOTPRINT)


def error_with_image(
    config: HasError,
    title: str,
    message: str,
    attach_img: AttachImage | None,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Error: " + title

    _hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(_NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    thread_ts = _split_send(config.bot_token, config.error.channel.name, title, message, formatter)

    if attach_img is not None:
        ch_id = config.error.channel.id
        if ch_id is None:
            raise ValueError("error channel id is not configured")

        _upload_image(config.bot_token, ch_id, title, attach_img["data"], attach_img["text"], thread_ts)

    my_lib.footprint.update(_NOTIFY_FOOTPRINT)


def parse_config(data: dict[str, Any]) -> SlackConfigTypes:
    """Slack 設定をパースする

    存在するフィールドに応じて適切な Config クラスを返す。
    """
    has_error = "error" in data
    has_info = "info" in data
    has_captcha = "captcha" in data

    bot_token = data["bot_token"]
    from_name = data["from"]

    # 全て揃っている場合
    if has_error and has_info and has_captcha:
        return SlackConfig(
            bot_token=bot_token,
            from_name=from_name,
            info=_parse_slack_info(data["info"]),
            captcha=_parse_slack_captcha(data["captcha"]),
            error=_parse_slack_error(data["error"]),
        )

    # error + info
    if has_error and has_info and not has_captcha:
        return SlackErrorInfoConfig(
            bot_token=bot_token,
            from_name=from_name,
            info=_parse_slack_info(data["info"]),
            error=_parse_slack_error(data["error"]),
        )

    # error のみ
    if has_error and not has_info and not has_captcha:
        return SlackErrorOnlyConfig(
            bot_token=bot_token,
            from_name=from_name,
            error=_parse_slack_error(data["error"]),
        )

    # captcha のみ
    if has_captcha and not has_error and not has_info:
        return SlackCaptchaOnlyConfig(
            bot_token=bot_token,
            from_name=from_name,
            captcha=_parse_slack_captcha(data["captcha"]),
        )

    # 中途半端なパターン: error + captcha (info なし)
    if has_error and has_captcha and not has_info:
        logging.warning(
            "Slack 設定が不完全です。SlackErrorOnlyConfig として処理します。captcha は無視されます。"
        )
        return SlackErrorOnlyConfig(
            bot_token=bot_token,
            from_name=from_name,
            error=_parse_slack_error(data["error"]),
        )

    # 中途半端なパターン: info + captcha (error なし)
    if has_info and has_captcha and not has_error:
        logging.warning(
            "Slack 設定が不完全です。SlackCaptchaOnlyConfig として処理します。info は無視されます。"
        )
        return SlackCaptchaOnlyConfig(
            bot_token=bot_token,
            from_name=from_name,
            captcha=_parse_slack_captcha(data["captcha"]),
        )

    # info のみ、または何もない場合
    raise ValueError("Slack 設定には error または captcha が必要です")


def send(
    config: HasBotToken, ch_name: str, message: FormattedMessage, thread_ts: str | None = None
) -> slack_sdk.web.slack_response.SlackResponse | None:
    return _send(config.bot_token, ch_name, message, thread_ts)


def upload_image(  # noqa: PLR0913
    config: HasBotToken,
    ch_id: str,
    title: str,
    img: Image.Image,
    text: str,
    thread_ts: str | None = None,
) -> str | None:
    return _upload_image(config.bot_token, ch_id, title, img, text, thread_ts)


def _parse_slack_channel(data: dict[str, Any]) -> SlackChannelConfig:
    return SlackChannelConfig(
        name=data["name"],
        id=data.get("id"),
    )


def _parse_slack_info(data: dict[str, Any]) -> SlackInfoConfig:
    return SlackInfoConfig(channel=_parse_slack_channel(data["channel"]))


def _parse_slack_captcha(data: dict[str, Any]) -> SlackCaptchaConfig:
    return SlackCaptchaConfig(channel=_parse_slack_channel(data["channel"]))


def _parse_slack_error(data: dict[str, Any]) -> SlackErrorConfig:
    return SlackErrorConfig(
        channel=_parse_slack_channel(data["channel"]),
        interval_min=data["interval_min"],
    )


def _send(
    token: str, ch_name: str, message: FormattedMessage, thread_ts: str | None = None
) -> slack_sdk.web.slack_response.SlackResponse | None:
    try:
        client = slack_sdk.WebClient(token=token)

        kwargs: dict[str, Any] = {
            "channel": ch_name,
            "text": message["text"],
            "blocks": message["json"],
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
                    text=formatted_msg["text"],
                    blocks=formatted_msg["json"],
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


def _upload_image(  # noqa: PLR0913
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

            resp = client.files_upload_v2(**kwargs)

            return resp["files"][0]["id"]
        except slack_sdk.errors.SlackApiError:
            logging.exception("Failed to send Slack message")

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
                    _thread_local.notify_hist = collections.defaultdict(lambda: [])  # noqa: PIE807

        return _thread_local.notify_hist[worker]
    else:
        return _notify_hist[worker]


if __name__ == "__main__":
    # TEST Code
    import sys

    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    raw_config = my_lib.config.load(config_file)

    if "slack" not in raw_config:
        logging.warning("Slack の設定が記載されていません。")
        sys.exit(-1)

    slack_config = parse_config(raw_config["slack"])

    if isinstance(slack_config, (SlackConfig, SlackErrorInfoConfig)):
        info(slack_config, "Test", "This is test")
    if isinstance(slack_config, (SlackConfig, SlackErrorInfoConfig, SlackErrorOnlyConfig)):
        error(slack_config, "Test", "This is test")
