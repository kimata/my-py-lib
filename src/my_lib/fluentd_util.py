#!/usr/bin/env python3
import logging
import fluent.sender

def get_handle(tag, host):
    return fluent.sender.FluentSender(tag, host)

def send(handle, label, data):
    if not handle.emit(label, data):
        logging.error(sender.last_error)
        return False

    return True

