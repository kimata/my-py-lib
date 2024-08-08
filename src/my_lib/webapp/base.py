#!/usr/bin/env python3
import my_lib.flask_util
import my_lib.webapp.config
from flask import Blueprint, redirect, send_from_directory

blueprint = Blueprint("webapp-base", __name__, url_prefix=my_lib.webapp.config.APP_URL_PREFIX)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@my_lib.flask_util.gzipped
def webapp(filename):
    return send_from_directory(my_lib.webapp.config.STATIC_FILE_PATH, filename)


blueprint_default = Blueprint("webapp-default", __name__)


@blueprint_default.route("/")
@my_lib.flask_util.gzipped
def root():
    return redirect(f"{my_lib.webapp.config.APP_URL_PREFIX}/")
