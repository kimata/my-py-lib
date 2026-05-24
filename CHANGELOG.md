# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.6] - 2026-05-24

### Fixed

- `BP35A1.__parse_pan_desc` が SKSCAN MODE 3 (active scan with IE) の応答をパースできない問題を修正。MODE 3 の応答には `PairID` フィールドが含まれない場合があり、従来は EPANDESC ブロック終了後の `EVENT 22` 行を読み込んで「行がスペース始まりでない」と Exception を投げていた
- `PanDescriptor.pair_id` をオプショナル化 (デフォルト空文字)
- `scan_channel` で PAN 検出後に外側 read ループから即時抜けるよう変更 (`__parse_pan_desc` が `EVENT 22` を消費した場合の無駄な timeout 待ちを回避)

## [0.2.5] - 2026-05-23

### Fixed

- `BP35A1.scan_channel` の検出率を改善:
    - SKSCAN の MODE を 2 (active scan) から 3 (active scan with IE) に変更。IE 付きの方が検出率が高い
    - duration の上限を 7 から 9 に拡張 (各チャネル滞在時間を最大 ~5 秒に)
- メーター側のビーコン送信特性 (送信周期・強度) が経年で変化した場合に、従来 (MODE 2 + duration 上限 7) では PAN ビーコンを拾えなくなるケースに対応

## [0.2.4] - 2026-05-23

### Fixed

- `EchonetEnergy.get_pan_info()` の PAN 情報キャッシュが完全に機能していないバグを修正。`scan_channel()` は `PanDescriptor` (dataclass) を返すのにキャッシュ読込時の判定が `isinstance(pan_info, dict)` のままだったため、永遠に成立せず毎回 scan が走っていた。`isinstance(pan_info, PanDescriptor)` に修正し、`None` (scan 失敗) をキャッシュに書き込まないように変更
- 関連する型注釈 (`get_pan_info`, `_get_pan_info_impl`, `connect` の `pan_info`) を `dict[str, str]` から `PanDescriptor` に揃えた

## [0.2.3] - 2026-05-23

### Fixed

- `EchonetEnergy` を含む 7 つのセンサークラスが `SensorBase` を継承していなかったため、初回計測で失敗した際に `consecutive_fails` 属性の AttributeError でプロセスが死ぬバグを修正 (継承漏れ: `EchonetEnergy`, `FD_Q10C`, `RG_15`, `SM9561`, `LP_PYRA03`, `GROVE_TDS`, `ADSBase`)

### Changed

- センサー基底クラスの継承関係を整理:
    - `ADSBase` を `I2CSensorBase` 継承に変更
    - `SM9561`, `LP_PYRA03`, `GROVE_TDS` を `I2CSensorBase` 継承に変更
    - `EchonetEnergy`, `RG_15` を新設 `UARTSensorBase` 継承に変更
    - `FD_Q10C` を `SensorBase` 継承に変更
- `my_lib.sensor.base` に `UARTSensorBase` を追加 (`I2CSensorBase` と対称な UART/シリアル接続センサー用基底クラス)
- `SensorBase.__init__()` で `required` / `consecutive_fails` をインスタンス変数として明示的に初期化
- `my_lib.sensor.SensorProtocol` (TYPE_CHECKING 内の Protocol) を廃止し、`SensorBase` に統一

## [0.2.2] - 2026-01-25

### Added

- `my_lib.pydantic.base` モジュール（Pydantic ベーススキーマ）
- `my_lib.selenium_util.set_stealth_mode()` 関数（ボット検知回避用）

### Fixed

- PA-API のアウトレット/新品価格取得間に5秒のウェイトを追加
- 本番環境でログが `test_worker_main/` に保存される問題を修正
- Chrome 終了時にロックファイルをクリーンアップ
- `pytest_util.get_path()` の新仕様に合わせてテストを修正

### Changed

- CI ジョブ `test-walk-through` を `test-pytest` に名称変更

## [0.2.1] - 2026-01-24

### Added

- `my_lib.lifecycle` パッケージ（LifecycleManager, GracefulShutdownManager）
- `my_lib.selenium_util.BrowserManager` クラス（起動失敗時のリトライ機能付き）
- `my_lib.cui_progress` モジュール（ProgressManager, NullProgressManager）
- `my_lib.config.ConfigAccessor` と `SafeAccess` ユーティリティ
- `my_lib.pytest_util.get_worker_id()` 関数
- `my_lib.container_util.get_uptime()` 関数
- `my_lib.selenium_util.with_retry()` ヘルパー関数
- `my_lib.selenium_util.with_session_retry()` 関数
- `my_lib.selenium_util.error_handler` に page_source 取得機能
- `my_lib.notify.slack.attach_file()` 関数
- `my_lib.chrome_util` モジュール（Chrome プロファイル関連機能を集約）
- Slack 通知関数で thread_ts を返すように変更
- CDP を使った日本語ロケール強制設定機能
- Chrome プロファイル健全性チェックと自動リカバリ機能
- ty 型チェッカーを開発依存に追加
- Coveralls カバレッジ連携

### Changed

- `my_lib.webapp.log` を LogManager クラスでリファクタリング
- `my_lib.webapp.event` を EventManager クラスでリファクタリング
- `my_lib.webapp.config.init` の引数を dataclass に変更
- ロギングのキュー処理を最適化しブロッキングを回避
- `create_driver` の引数順序を変更し不正な組み合わせを検出
- `datetime.now` を `my_lib.time.now` に統一
- 型安全性向上とコード品質改善（複数回のリファクタリング）
- SQLite 接続設定を永続設定と接続設定に分離
- CephFS 対応のため SQLite のデフォルト設定を変更

### Fixed

- `webapp/log.get_worker_id()` のデフォルト値を "main" に修正
- ログワーカーの DB 接続を各操作ごとに開閉するよう修正
- `cleanup_stale_files` をスレッドセーフにし、プロセス内で1回だけ実行
- SSE 接続確立時に即座にダミーデータを送信してレスポンスヘッダーをフラッシュ
- Chrome service stop 時の ConnectionResetError を適切にハンドリング
- tmux 環境での幅計算を調整
- メルカリログイン時の待機処理を追加
- pydub の SyntaxWarning を抑制
- 多数の pyright/mypy 型エラーを修正

### Documentation

- CLAUDE.md に開発ワークフロー規約を追加
- CLAUDE.md に設定クラスの実装規約を追加
- CLAUDE.md に型チェックポリシーを追加
- CHANGELOG.md 更新ルールを追加

## [0.2.0] - 2024-XX-XX

Initial tracked release.
