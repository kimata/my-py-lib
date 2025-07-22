#!/usr/bin/env python3
import logging
import socket

import requests

import my_lib.footprint


def check_liveness(name, liveness_file, interval):
    if not my_lib.footprint.exists(liveness_file):
        logging.warning("%s is not executed.", name)
        return False

    elapsed = my_lib.footprint.elapsed(liveness_file)
    # NOTE: 少なくとも1分は様子を見る
    if elapsed > max(interval * 2, 60):
        logging.warning("Execution interval of %s is too long. %s sec)", name, f"{elapsed:,.1f}")
        return False
    else:
        logging.debug("Execution interval of %s: %s sec)", name, f"{elapsed:,.1f}")
        return True


def check_tcp_port(port, address="127.0.0.1"):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((address, port))
        sock.close()
        return result == 0
    except Exception:
        logging.exception("Failed to check TCP port")
        return False


def check_http_port(port, address="127.0.0.1"):
    try:
        if requests.get(f"http://{address}:{port}/", timeout=5).status_code == 200:
            return True
    except Exception:
        logging.exception("Failed to access Web server")

    return False
