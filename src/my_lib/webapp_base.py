#!/usr/bin/env python3
import my_lib.flask_util
from flask import Blueprint, redirect, send_from_directory
from webapp_config import APP_URL_PREFIX, STATIC_FILE_PATH

blueprint = Blueprint("webapp-base", __name__, url_prefix=APP_URL_PREFIX)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@my_lib.flask_util.gzipped
def webapp(filename):
    return send_from_directory(STATIC_FILE_PATH, filename)


blueprint_default = Blueprint("webapp-default", __name__)


@blueprint_default.route("/")
@my_lib.flask_util.gzipped
def root():
    return redirect(f"{APP_URL_PREFIX}/")
