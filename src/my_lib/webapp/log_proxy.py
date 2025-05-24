#!/usr/bin/env python3
"""
log.py のプロキシとして動作して、ログを表示します。

Usage:
  log_proxy.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : WEB サーバのポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

import json
import logging
import os
import time
import wsgiref.handlers

import my_lib.flask_util
import my_lib.webapp.config
import requests
import sseclient  # 使うのは sseclient、sseclient-py ではない

import flask

blueprint = flask.Blueprint("webapp-proxy", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

api_base_url = None


def init(api_base_url_):
    global api_base_url  # noqa: PLW0603

    api_base_url = api_base_url_


def get_log():
    global api_base_url

    stop_day = 7 if os.environ.get("DUMMY_MODE", "false") == "true" else 0

    try:
        url = "{base_url}{api_endpoint}".format(base_url=api_base_url, api_endpoint="/api/log_view")

        # NOTE: 簡易リバースプロキシ
        res = requests.get(url, params={"stop_day": stop_day})  # noqa: S113
        res.raise_for_status()

        # NOTE: どのみち、また JSON 文字列に戻すけど...
        return json.loads(res.text)
    except Exception:
        logging.exception("Unable to fetch log from %s", url)
        return {"data": [], "last_time": time.time()}


# NOTE: リバースプロキシの場合は、webapp_event ではなく、
# ここで /api/event をハンドリングする
@blueprint.route("/api/event", methods=["GET"])
def api_event():
    count = flask.request.args.get("count", 0, type=int)

    # NOTE: EventStream を中継する
    def event_stream():
        logging.debug("SSEClient start")

        url = "{base_url}{api_endpoint}".format(base_url=api_base_url, api_endpoint="/api/event")
        sse = sseclient.SSEClient(url)
        i = 0
        try:
            for event in sse:
                yield f"data: {event.data}\n\n"

                i += 1
                if i == count:
                    break
        finally:
            # NOTE: 切断処理
            sse.resp.close()

        logging.debug("SSEClient terminate")  # pragma: no cover

    res = flask.Response(flask.stream_with_context(event_stream()), mimetype="text/event-stream")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res


@blueprint.route("/api/log_view", methods=["GET"])
@my_lib.flask_util.support_jsonp
@my_lib.flask_util.gzipped
def api_log_view():
    # NOTE: @gzipped をつけた場合、キャッシュ用のヘッダを付与しているので、
    # 無効化する。
    flask.g.disable_cache = True
    log = get_log()

    response = flask.jsonify(log)

    response.headers["Last-Modified"] = wsgiref.handlers.format_date_time(log["last_time"])
    response.make_conditional(flask.request)

    return response


def test_run(api_base_url, port, debug_mode):
    import flask_cors

    app = flask.Flask("test")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    init(api_base_url)

    flask_cors.CORS(app)

    app.config["TEST"] = True
    app.json.compat = True

    app.register_blueprint(my_lib.webapp.log_proxy.blueprint)

    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False, debug=debug_mode)  # noqa: S104


if __name__ == "__main__":
    # TEST Code
    import multiprocessing
    import signal

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import requests

    def watch_event(base_url, count):
        sse = sseclient.SSEClient(f"{base_url}/api/event?count={count}")
        i = 0
        try:
            for event in sse:
                logging.info("event: %s", event.data)

                i += 1
                if i == count:
                    break
        finally:
            # NOTE: 切断処理
            sse.resp.close()

        logging.info("Finish watch event")

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = int(args["-p"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/test"
    my_lib.webapp.config.init(config)

    import my_lib.webapp.base
    import my_lib.webapp.log
    import my_lib.webapp.log_proxy

    log_port = port + 1
    base_url = {"log": f"http://127.0.0.1:{log_port}/test", "proxy": f"http://127.0.0.1:{port}/test"}

    log_proc = multiprocessing.Process(
        target=lambda: my_lib.webapp.log.test_run(config, log_port, debug_mode)
    )
    log_proc.start()

    proc = multiprocessing.Process(
        target=lambda: my_lib.webapp.log_proxy.test_run(base_url["log"], port, debug_mode)
    )
    proc.start()

    time.sleep(0.5)

    watch_proc = multiprocessing.Process(target=lambda: watch_event(base_url["proxy"], 3))
    watch_proc.start()

    logging.info(my_lib.pretty.format(requests.get(f'{base_url["log"]}/api/log_clear').text))  # noqa: S113

    my_lib.pretty.format(
        requests.post(f'{base_url["log"]}/api/log_add', data={"message": "Test INFO", "level": "INFO"})  # noqa: S113
    )
    time.sleep(0.5)
    my_lib.pretty.format(
        requests.post(f'{base_url["log"]}/api/log_add', data={"message": "Test WARN", "level": "WARN"})  # noqa: S113
    )
    time.sleep(0.5)
    my_lib.pretty.format(
        requests.post(f'{base_url["log"]}/api/log_add', data={"message": "Test ERROR", "level": "ERROR"})  # noqa: S113
    )

    watch_proc.join()

    logging.info(my_lib.pretty.format(json.loads(requests.get(f'{base_url["proxy"]}/api/log_view').text)))  # noqa: S113

    proc.terminate()
    proc.join()

    os.kill(log_proc.pid, signal.SIGUSR1)
    log_proc.terminate()
    log_proc.join()
