# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
