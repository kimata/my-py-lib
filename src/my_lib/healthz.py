#!/usr/bin/env python3
import logging

import my_lib.footprint
import requests


def check_liveness(name, liveness_file, interval):
    if not liveness_file.exists():
        logging.warning("%s is not executed.", name)
        return False

    elapsed = my_lib.footprint.elapsed(liveness_file)
    # NOTE: 少なくとも1分は様子を見る
    if elapsed > max(interval * 2, 60):
        logging.warning("Execution interval of %s is too long. %s sec)", name, f"{elapsed:,.1f}")
        return False

    return True


def check_port(port, address="127.0.0.1"):
    try:
        if requests.get(f"http://{address}:{port}/", timeout=5).status_code == 200:
            return True
    except Exception:
        logging.exception("Failed to access Flask web server")

    return False
