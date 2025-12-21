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
from typing import Any, TypedDict


@dataclass(frozen=True)
class MailSmtpConfig:
    """SMTP 設定"""

    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class MailConfig:
    """メール設定"""

    smtp: MailSmtpConfig
    from_address: str
    to: str


class ImageAttachment(TypedDict, total=False):
    path: str
    data: bytes
    id: str


def build_message(subject: str, message: str, image: ImageAttachment | None = None) -> str:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject

    msg.attach(email.mime.text.MIMEText(message, "html"))

    if image is not None:
        if "path" in image:
            with pathlib.Path(image["path"]).open("rb") as img:
                mime_img = email.mime.image.MIMEImage(img.read())
        else:
            mime_img = email.mime.image.MIMEImage(image["data"])

        mime_img.add_header("Content-ID", "<" + image["id"] + ">")
        msg.attach(mime_img)

    return msg.as_string()


def send_impl(mail_config: MailConfig | dict[str, Any], message: str) -> None:
    if isinstance(mail_config, MailConfig):
        smtp = smtplib.SMTP(mail_config.smtp.host, mail_config.smtp.port)
        smtp.starttls()
        smtp.login(mail_config.smtp.user, mail_config.smtp.password)
        smtp.sendmail(mail_config.from_address, mail_config.to, message)
    else:
        # 後方互換性のため辞書形式もサポート
        smtp = smtplib.SMTP(mail_config["smtp"]["host"], mail_config["smtp"]["port"])
        smtp.starttls()
        smtp.login(mail_config["user"], mail_config["pass"])
        smtp.sendmail(mail_config["from"], mail_config["to"], message)
    smtp.quit()


def send(mail_config: MailConfig | dict[str, Any], message: str) -> None:
    try:
        send_impl(mail_config, message)
    except Exception:
        logging.exception("Failed to sendo Mail message")


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    send(config, message)
