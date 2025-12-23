#!/usr/bin/env python3
"""
メールで通知を行います。

Usage:
  mail.py [-c CONFIG] [-D] [-m MESSAGE]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ。[default: TEST]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import email.mime.image
import email.mime.multipart
import email.mime.text
import logging
import pathlib
import smtplib
from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True)
class MailSmtpConfig:
    """SMTP 設定"""

    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class MailEmptyConfig:
    """メール設定が存在しない場合のプレースホルダー"""


@dataclass(frozen=True)
class MailConfig:
    """メール設定"""

    smtp: MailSmtpConfig
    from_address: str
    to: str


# 型エイリアス
MailConfigTypes = Union[MailConfig, MailEmptyConfig]


@dataclass(frozen=True)
class ImageAttachmentFromPath:
    """メール添付画像（ファイルパス指定）"""

    id: str
    path: str


@dataclass(frozen=True)
class ImageAttachmentFromData:
    """メール添付画像（バイナリデータ指定）"""

    id: str
    data: bytes


ImageAttachment = ImageAttachmentFromPath | ImageAttachmentFromData


def send(mail_config: MailConfigTypes, message: str) -> None:
    if isinstance(mail_config, MailEmptyConfig):
        return
    try:
        _send_impl(mail_config, message)
    except Exception:
        logging.exception("Failed to send Mail message")


def build_message(subject: str, message: str, image: ImageAttachment | None = None) -> str:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject

    msg.attach(email.mime.text.MIMEText(message, "html"))

    if image is not None:
        if isinstance(image, ImageAttachmentFromPath):
            with pathlib.Path(image.path).open("rb") as img:
                mime_img = email.mime.image.MIMEImage(img.read())
        else:
            mime_img = email.mime.image.MIMEImage(image.data)

        mime_img.add_header("Content-ID", "<" + image.id + ">")
        msg.attach(mime_img)

    return msg.as_string()


def parse_config(data: dict[str, Any]) -> MailConfigTypes:
    """メール設定をパースする

    存在するフィールドに応じて適切な Config クラスを返す。
    設定が空または不十分な場合は MailEmptyConfig を返す。
    """
    # 空の設定の場合
    if not data or "smtp" not in data:
        return MailEmptyConfig()

    return MailConfig(
        smtp=MailSmtpConfig(
            host=data["smtp"]["host"],
            port=data["smtp"]["port"],
            user=data["user"],
            password=data["pass"],
        ),
        from_address=data["from"],
        to=data["to"],
    )


def _send_impl(mail_config: MailConfig, message: str) -> None:
    smtp = smtplib.SMTP(mail_config.smtp.host, mail_config.smtp.port)
    smtp.starttls()
    smtp.login(mail_config.smtp.user, mail_config.smtp.password)
    smtp.sendmail(mail_config.from_address, mail_config.to, message)
    smtp.quit()


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

    if "mail" not in raw_config:
        logging.warning("メールの設定が記載されていません。")
        sys.exit(-1)

    mail_config = parse_config(raw_config["mail"])

    if isinstance(mail_config, MailEmptyConfig):
        logging.warning("メールの設定が不完全です。")
        sys.exit(-1)

    send(mail_config, message)
