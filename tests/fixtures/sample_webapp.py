#!/usr/bin/env python3
import os
import time

import flask

import my_lib.flask_util

WEBAPP_URL_PREFIX = "/test"

blueprint = flask.Blueprint("sample", __name__, url_prefix=WEBAPP_URL_PREFIX)


def create_app(config_file):
    os.environ["DUMMY_MODE"] = "true"

    import atexit
    import logging

    import flask
    import flask_cors

    import my_lib.config
    import my_lib.webapp.config

    config = my_lib.config.load(config_file)
    webapp_config = my_lib.webapp.config.WebappConfig.parse(config["webapp"])
    environment = my_lib.webapp.config.build_environment(webapp_config, url_prefix=WEBAPP_URL_PREFIX)

    import data.sample_webapp  # ty: ignore[unresolved-import]
    import my_lib.notify.slack
    import my_lib.webapp.base
    import my_lib.webapp.event
    import my_lib.webapp.log
    import my_lib.webapp.util

    app = flask.Flask("rasp-shutter")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        slack_config = my_lib.notify.slack.SlackConfig.parse(config.get("slack", {}))
        if environment.log_file_path is None:
            raise RuntimeError("webapp.data.log_file_path is required")
        my_lib.webapp.log.init(slack_config, environment.log_file_path)

        def notify_terminate():  # pragma: no cover
            my_lib.webapp.log.info("🏃 アプリを再起動します．")
            my_lib.webapp.log.term()

        atexit.register(notify_terminate)
    else:  # pragma: no cover
        pass

    flask_cors.CORS(app)

    app.config["CONFIG"] = config
    app.config["DUMMY_MODE"] = True

    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

    app.register_blueprint(my_lib.webapp.base.create_static_blueprint(environment=environment))
    app.register_blueprint(my_lib.webapp.base.create_root_redirect_blueprint(url_prefix=WEBAPP_URL_PREFIX))
    app.register_blueprint(my_lib.webapp.event.blueprint, url_prefix=WEBAPP_URL_PREFIX)
    app.register_blueprint(my_lib.webapp.log.blueprint, url_prefix=WEBAPP_URL_PREFIX)
    app.register_blueprint(my_lib.webapp.util.blueprint, url_prefix=WEBAPP_URL_PREFIX)

    app.register_blueprint(data.sample_webapp.blueprint, url_prefix=WEBAPP_URL_PREFIX)

    return app


@blueprint.route("/exec/log_write", methods=["GET"])
@my_lib.flask_util.support_jsonp
def exec_log_write():
    my_lib.webapp.log.error("TEST ERROR")
    time.sleep(0.5)
    my_lib.webapp.log.warning("TEST WARN")

    return "OK"


@blueprint.route("/exec/gzipped/through", methods=["GET"])
@my_lib.flask_util.gzipped
def gzipped_through():
    return "GZIPPED", 302


@blueprint.route("/exec/gzipped/disable_cache", methods=["GET"])
@my_lib.flask_util.gzipped
def gzipped_disable_cache():
    flask.g.disable_cache = True
    return "OK"


@blueprint.route("/exec/support_jsonp", methods=["GET"])
@my_lib.flask_util.support_jsonp
def support_jsonp():
    return flask.jsonify({"status": "OK"})


@blueprint.route("/exec/remote_host", methods=["GET"])
@my_lib.flask_util.support_jsonp
def remote_host():
    return f"{my_lib.flask_util.remote_host(flask.request)}, {my_lib.flask_util.auth_user(flask.request)}"
