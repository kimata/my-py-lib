#!/usr/bin/env python3
import pathlib

import flask

import my_lib.flask_util
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp-base", __name__)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@my_lib.flask_util.gzipped
def webapp(filename):
    try:
        static_dir = pathlib.Path(my_lib.webapp.config.STATIC_DIR_PATH).resolve()
        requested_path = (static_dir / filename).resolve()

        if not str(requested_path).startswith(str(static_dir)):
            flask.abort(404)

        return flask.send_from_directory(my_lib.webapp.config.STATIC_DIR_PATH, filename)
    except (ValueError, OSError):
        flask.abort(404)


blueprint_default = flask.Blueprint("webapp-default", __name__)


@blueprint_default.route("/")
@my_lib.flask_util.gzipped
def root():
    return flask.redirect(f"{my_lib.webapp.config.URL_PREFIX}/")
