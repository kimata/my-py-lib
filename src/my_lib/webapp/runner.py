#!/usr/bin/env python3
"""webui 起動 CLI の共通ランナー

各アプリの webui エントリポイントが個別に持っていた
docopt → logger 初期化 → 設定読み込み → Flask アプリ生成 → シグナル処理 →
プロセスグループ管理 → app.run の骨格を共通化する。

Flask アプリの組み立て (blueprint 登録・初期化処理) はプロジェクト固有性が
高いため共通化せず、app_factory (各プロジェクトの create_app) に委ねる。
アプリ側では should_init() / silence_werkzeug_log() を部品として使える。

使用例::

    #!/usr/bin/env python3
    \"\"\"
    Web UI サーバです。

    Usage:
      app-webui [-c CONFIG] [-p PORT] [-D]

    Options:
      -c CONFIG         : 設定ファイルを指定します。[default: config.yaml]
      -p PORT           : WEB サーバのポートを指定します。[default: 5000]
      -D                : デバッグモードで動作します。
    \"\"\"

    import my_lib.webapp.runner


    def create_app(config, use_reloader=False):
        ...  # 既存の create_app (テストからも直接使われる)


    SPEC = my_lib.webapp.runner.WebAppSpec(
        logger_name="app",
        app_factory=lambda config, ctx: create_app(config, use_reloader=ctx.use_reloader),
    )

    if __name__ == "__main__":
        my_lib.webapp.runner.run(SPEC, __doc__)
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

import docopt

import my_lib.config
import my_lib.logger
import my_lib.proc_util


@dataclass(frozen=True)
class RunContext:
    """CLI 起動時の実行時情報 (app_factory に渡される)

    Attributes:
        args: docopt の解析結果
        debug_mode: -D が指定されたか
        dummy_mode: -d が指定されたか (オプションが無い CLI では False)
        use_reloader: werkzeug リローダーを使うか

    """

    args: dict[str, Any]
    debug_mode: bool
    dummy_mode: bool
    use_reloader: bool


# 設定読み込み。(config_file, docopt args) を受けて設定オブジェクトを返す
ConfigLoader: TypeAlias = Callable[[str, dict[str, Any]], Any]
# Flask アプリの組み立て。(config, RunContext) を受けて Flask アプリを返す
AppFactory: TypeAlias = Callable[[Any, RunContext], Any]
# リッスンポートの解決。(config, docopt args) を受けてポート番号を返す
PortResolver: TypeAlias = Callable[[Any, dict[str, Any]], int]
# リローダー使用可否の動的判定。docopt args を受ける
ReloaderResolver: TypeAlias = Callable[[dict[str, Any]], bool]
# graceful shutdown フック
TermHook: TypeAlias = Callable[[], None]


@dataclass(frozen=True)
class WebAppSpec:
    """webui CLI の構成定義

    Attributes:
        logger_name: my_lib.logger.init() に渡すロガー名
        app_factory: Flask アプリを組み立てる関数 (各プロジェクトの create_app)
        config_loader: 設定読み込み関数。None なら my_lib.config.load(config_file)
        term_hooks: SIGTERM / SIGINT 受信時に kill_child の前に呼ぶフック
            (ワーカースレッドの停止等)。sys.exit はランナー側が行う
        use_reloader: werkzeug リローダーを使うか。bool または args を受けて
            判定する関数 (テストモードで無効化するアプリ用)
        port_resolver: リッスンポートの解決関数。None なら int(args["-p"])

    """

    logger_name: str
    app_factory: AppFactory
    config_loader: ConfigLoader | None = None
    term_hooks: tuple[TermHook, ...] = ()
    use_reloader: bool | ReloaderResolver = True
    port_resolver: PortResolver | None = None


def should_init(use_reloader: bool) -> bool:
    """バックグラウンド初期化を行うべきかを返す

    werkzeug リローダー使用時は親プロセス (監視側) と子プロセスの2つが起動する。
    初期化は再起動後の子プロセス (WERKZEUG_RUN_MAIN=true) でのみ行い、
    二重初期化を防ぐ。リローダーを使わない場合 (gunicorn 等の WSGI サーバーや
    テスト) は常に初期化する。
    """
    return not use_reloader or os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def silence_werkzeug_log() -> None:
    """werkzeug のアクセスログを無効にする"""
    logging.getLogger("werkzeug").setLevel(logging.ERROR)


def run(spec: WebAppSpec, doc: str) -> None:
    """webui CLI を実行する

    Args:
        spec: CLI の構成定義
        doc: docopt に渡す Usage docstring。少なくとも -c と -D、
            port_resolver を指定しない場合は -p を定義していること

    """
    args = docopt.docopt(doc)
    debug_mode = bool(args.get("-D"))
    dummy_mode = bool(args.get("-d"))

    my_lib.logger.init(spec.logger_name, level=logging.DEBUG if debug_mode else logging.INFO)

    config_file = args["-c"]
    if spec.config_loader is not None:
        config = spec.config_loader(config_file, args)
    else:
        config = my_lib.config.load(config_file)

    use_reloader = spec.use_reloader(args) if callable(spec.use_reloader) else spec.use_reloader

    ctx = RunContext(args=args, debug_mode=debug_mode, dummy_mode=dummy_mode, use_reloader=use_reloader)

    app = spec.app_factory(config, ctx)

    port = spec.port_resolver(config, args) if spec.port_resolver is not None else int(args["-p"])

    _serve(app, spec, port=port, debug_mode=debug_mode, use_reloader=use_reloader)


def _terminate(spec: WebAppSpec) -> None:
    """graceful shutdown を実行してプロセスを終了する"""
    for hook in spec.term_hooks:
        try:
            hook()
        except Exception:
            logging.exception("Error in term hook")

    # 子プロセスを終了
    my_lib.proc_util.kill_child()

    logging.info("Graceful shutdown completed")
    sys.exit(0)


def _kill_own_process_group() -> None:
    """自分がリーダーの場合、プロセスグループ全体に SIGTERM を送る

    werkzeug リローダーの子プロセスも含めて終了させるため。
    """
    try:
        current_pid = os.getpid()
        pgid = os.getpgid(current_pid)
        if current_pid == pgid:
            logging.info("Terminating process group %d", pgid)
            os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        # プロセスグループ操作に失敗した場合は通常の終了処理へ
        pass


def _serve(app: Any, spec: WebAppSpec, *, port: int, debug_mode: bool, use_reloader: bool) -> None:
    # プロセスグループリーダーとして実行 (リローダープロセスの適切な管理のため)
    with contextlib.suppress(PermissionError):
        os.setpgrp()

    # 異常終了時もプロセスグループごと片付ける
    atexit.register(_kill_own_process_group)

    handler_state = {"entered": False}

    def sig_handler(num: int, _frame: Any) -> None:
        if handler_state["entered"]:
            return  # 再入を防止
        handler_state["entered"] = True

        logging.warning("receive signal %d", num)

        if num not in (signal.SIGTERM, signal.SIGINT):
            handler_state["entered"] = False
            return

        # シグナルを無視に設定してからプロセスグループを終了
        # (自プロセスへのシグナルによる再入を防止)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        _kill_own_process_group()
        _terminate(spec)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    try:
        app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=use_reloader, debug=debug_mode)  # noqa: S104
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt, shutting down...")
        sig_handler(signal.SIGINT, None)
