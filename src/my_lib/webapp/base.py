#!/usr/bin/env python3
import my_lib.flask_util
import my_lib.webapp.config

import flask

_blueprint = None
_blueprint_default = None


def get_blueprint():
    global _blueprint  # noqa: PLW0603
    if _blueprint is None:
        _blueprint = flask.Blueprint("webapp-base", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

        @_blueprint.route("/", defaults={"filename": "index.html"})
        @_blueprint.route("/<path:filename>")
        @my_lib.flask_util.gzipped
        def webapp(filename):
            return flask.send_from_directory(my_lib.webapp.config.STATIC_DIR_PATH, filename)

    return _blueprint


def get_blueprint_default():
    global _blueprint_default  # noqa: PLW0603
    if _blueprint_default is None:
        _blueprint_default = flask.Blueprint("webapp-default", __name__)

        @_blueprint_default.route("/")
        @my_lib.flask_util.gzipped
        def root():
            return flask.redirect(f"{my_lib.webapp.config.URL_PREFIX}/")

    return _blueprint_default


# 後方互換性のためのプロパティ
@property
def blueprint():
    return get_blueprint()


@property
def blueprint_default():
    return get_blueprint_default()
