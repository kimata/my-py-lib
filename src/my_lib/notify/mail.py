#!/usr/bin/env python3
"""
メールで通知を行います．

Usage:
  mail.py [-c CONFIG] [-D] [-m MESSAGE]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ．[default: TEST]
  -D                : デバッグモードで動作します．
"""

import email.mime.image
import email.mime.multipart
import email.mime.text
import logging
import pathlib
import smtplib


def build_message(subject, message, image=None):
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


def send_impl(config, message):
    smtp = smtplib.SMTP(config["mail"]["smtp"]["host"], config["mail"]["smtp"]["port"])
    smtp.starttls()
    smtp.login(config["mail"]["user"], config["mail"]["pass"])
    smtp.sendmail(config["mail"]["from"], config["mail"]["to"], message)
    smtp.quit()


def send(config, message):
    try:
        send_impl(config, message)
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
