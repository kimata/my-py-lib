#!/usr/bin/env python3
"""
プロキシとして動作して、ログを表示します。

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

import requests
import sseclient  # 使うのは sseclient、sseclient-py ではない

import flask
import my_lib.flask_util
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp-proxy", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

api_base_url = None
error_response = None


def init(api_base_url_, error_response_=None):
    global api_base_url  # noqa: PLW0603
    global error_response  # noqa: PLW0603

    api_base_url = api_base_url_
    error_response = error_response_ if error_response_ else {"data": [], "last_time": time.time()}


# NOTE: リバースプロキシの場合は、webapp_event ではなく、
# ここで /api/proxy/event/* をハンドリングする
@blueprint.route("/api/proxy/event/<path:subpath>", methods=["GET", "POST"])
def api_proxy_event(subpath):
    global api_base_url

    # NOTE: EventStream を中継する
    def event_stream():
        logging.debug("SSEClient start")

        url = f"{api_base_url}/{subpath}"

        # リクエストパラメータを構築
        if flask.request.method == "GET":
            # GETの場合はクエリパラメータを転送
            params = dict(flask.request.args)
            sse = sseclient.SSEClient(url, params=params)
        else:
            # POSTの場合はフォームデータを転送
            data = dict(flask.request.form)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            import urllib.parse

            post_data = urllib.parse.urlencode(data)
            full_url = (
                f"{url}?{urllib.parse.urlencode(dict(flask.request.args))}" if flask.request.args else url
            )
            sse = sseclient.SSEClient(full_url, data=post_data, headers=headers)

        i = 0
        count = flask.request.args.get("count", 0, type=int)
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


@blueprint.route("/api/proxy/json/<path:subpath>", methods=["GET", "POST"])
@my_lib.flask_util.support_jsonp
@my_lib.flask_util.gzipped
def api_proxy_json(subpath):
    global api_base_url
    global error_response

    # NOTE: @gzipped をつけた場合、キャッシュ用のヘッダを付与しているので、
    # 無効化する。
    flask.g.disable_cache = True

    try:
        url = f"{api_base_url}/{subpath}"

        if flask.request.method == "GET":
            # GETの場合はクエリパラメータを転送
            params = dict(flask.request.args)
            res = requests.get(url, params=params)  # noqa: S113
        else:
            # POSTの場合はフォームデータとクエリパラメータの両方を転送
            params = dict(flask.request.args)
            data = dict(flask.request.form)
            # JSONデータの場合も対応
            if flask.request.is_json:
                data = flask.request.get_json()
                res = requests.post(url, params=params, json=data)  # noqa: S113
            else:
                res = requests.post(url, params=params, data=data)  # noqa: S113

        res.raise_for_status()

        # NOTE: JSON として解析してから返す
        data = json.loads(res.text)
        response = flask.jsonify(data)

        # last_time フィールドがある場合は Last-Modified ヘッダを設定
        if "last_time" in data:
            response.headers["Last-Modified"] = wsgiref.handlers.format_date_time(data["last_time"])
            response.make_conditional(flask.request)

        return response
    except Exception:
        logging.exception("Unable to fetch data from %s", url)
        return flask.jsonify(error_response if error_response else {"error": "Proxy request failed"}), 500


def test_run(api_base_url, port, debug_mode, error_response):
    import flask_cors

    app = flask.Flask("test")

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    init(api_base_url, error_response)

    flask_cors.CORS(app)

    app.config["TEST"] = True
    app.json.compat = True

    app.register_blueprint(my_lib.webapp.proxy.blueprint)

    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False, debug=debug_mode)  # noqa: S104


if __name__ == "__main__":
    # TEST Code
    import multiprocessing
    import signal

    import docopt
    import requests

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    def watch_event(base_url, count):
        # 新しいプロキシエンドポイントを使用
        sse = sseclient.SSEClient(f"{base_url}/api/proxy/event/api/event?count={count}")
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
    import my_lib.webapp.proxy

    log_port = port + 1
    base_url = {"log": f"http://127.0.0.1:{log_port}/test", "proxy": f"http://127.0.0.1:{port}/test"}

    log_proc = multiprocessing.Process(
        target=lambda: my_lib.webapp.log.test_run(config, log_port, debug_mode)
    )
    log_proc.start()

    proc = multiprocessing.Process(
        target=lambda: my_lib.webapp.proxy.test_run(base_url["log"], port, debug_mode)
    )
    proc.start()

    time.sleep(0.5)

    # 新しいプロキシエンドポイントのテスト
    logging.info("Testing new proxy endpoints...")

    # /api/proxy/json/api/log_view のテスト (GET)
    proxy_json_url = f"{base_url['proxy']}/api/proxy/json/api/log_view"
    logging.info("Testing GET %s", proxy_json_url)
    test_res = requests.get(proxy_json_url, params={"test_param": "value"})  # noqa: S113
    logging.info("Response: %s", my_lib.pretty.format(json.loads(test_res.text)))

    watch_proc = multiprocessing.Process(target=lambda: watch_event(base_url["proxy"], 3))
    watch_proc.start()

    logging.info(my_lib.pretty.format(requests.get(f"{base_url['log']}/api/log_clear").text))  # noqa: S113

    # POSTリクエストのテスト（プロキシ経由）
    proxy_post_url = f"{base_url['proxy']}/api/proxy/json/api/log_add"
    logging.info("Testing POST %s", proxy_post_url)

    my_lib.pretty.format(
        requests.post(proxy_post_url, data={"message": "Test INFO", "level": "INFO"})  # noqa: S113
    )
    time.sleep(0.5)
    my_lib.pretty.format(
        requests.post(proxy_post_url, data={"message": "Test WARN", "level": "WARN"})  # noqa: S113
    )
    time.sleep(0.5)
    my_lib.pretty.format(
        requests.post(proxy_post_url, data={"message": "Test ERROR", "level": "ERROR"})  # noqa: S113
    )

    watch_proc.join()

    # 古いエンドポイントのテスト
    logging.info(my_lib.pretty.format(json.loads(requests.get(f"{base_url['proxy']}/api/log_view").text)))  # noqa: S113

    # 新しいエンドポイントのテスト
    logging.info("Testing new endpoint: %s", proxy_json_url)
    logging.info(my_lib.pretty.format(json.loads(requests.get(proxy_json_url).text)))  # noqa: S113

    proc.terminate()
    proc.join()

    os.kill(log_proc.pid, signal.SIGUSR1)
    log_proc.terminate()
    log_proc.join()
