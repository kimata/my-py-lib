# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## 重要な注意事項

### プロジェクト設定ファイルの管理

**pyproject.toml をはじめとする一般的なプロジェクト管理ファイルは `../py-project` で一元管理しています。**

- プロジェクト設定ファイル（pyproject.toml、.gitlab-ci.yml、.pre-commit-config.yaml 等）を直接編集しないでください
- 設定を変更したい場合は、`../py-project` のテンプレートを更新し、このリポジトリに適用してください
- 変更を行う前に、何を変更したいのかを説明し、ユーザーの確認を取ってください

### ドキュメントの更新

コードを更新した際は、以下のドキュメントの更新が必要かどうか検討してください：

- **README.md**: 機能追加・変更、使用方法の変更、依存関係の変更があった場合
- **CLAUDE.md**: アーキテクチャの変更、開発コマンドの変更、重要なパターンの追加があった場合

## 開発コマンド

### 依存関係の管理

- **依存関係のインストール**: `uv sync`（本番・開発両方の依存関係をインストール）
- **新しい依存関係の追加**: `uv add <パッケージ名>`
- **開発用依存関係の追加**: `uv add --dev <パッケージ名>`
- **ロックファイルの更新**: `uv lock`

### テスト

- **全テストの実行**: `uv run pytest`（並列実行はデフォルトで有効）
- **特定テストの実行**: `uv run pytest tests/unit/test_xxx.py::TestClass::test_method`
- **カバレッジレポート**: テスト実行時に自動生成 → `reports/coverage/`
- **HTMLレポート**: `reports/pytest.html`

### コード品質

- **型チェック（pyright）**: `uv run pyright`
- **型チェック（mypy）**: `uv run mypy src/`
- **フォーマット**: `rye fmt`
- **リント**: `rye lint`

### ビルド

- **パッケージビルド**: `rye build`

## アーキテクチャ概要

IoT、自動化、データ収集アプリケーション向けの個人用ユーティリティライブラリです。
特に Raspberry Pi 環境での利用に最適化されています。

### ディレクトリ構造

```
src/my_lib/
├── sensor/              # ハードウェアセンサードライバ（19種類以上）
│   ├── base.py          # SensorBase, I2CSensorBase 抽象クラス
│   ├── exceptions.py    # SensorError, SensorCommunicationError
│   ├── i2cbus.py        # I2C バスラッパー（SMBus2）
│   ├── sht35.py         # 温湿度センサー
│   ├── scd4x.py         # CO2センサー
│   ├── ads1115.py       # 16bit ADC
│   └── ...
│
├── notify/              # 通知システム
│   ├── slack.py         # Slack 通知（WebClient、画像アップロード対応）
│   ├── line.py          # LINE Bot 通知
│   └── mail.py          # メール通知
│
├── webapp/              # Web フレームワークユーティリティ
│   ├── config.py        # グローバル設定
│   ├── base.py          # Flask ブループリント
│   └── log.py           # ロギング
│
├── store/               # E コマーススクレイピング
│   ├── amazon/          # Amazon（API、ログイン、CAPTCHA）
│   └── mercari/         # メルカリ
│
├── config.py            # YAML + JSON Schema 設定管理
├── sensor_data.py       # InfluxDB 時系列データ統合
├── flask_util.py        # Flask デコレータ（gzip、ETag）
├── logger.py            # 構造化ロギング（ローテーション、圧縮）
├── healthz.py           # ヘルスチェックエンドポイント
├── selenium_util.py     # Selenium ヘルパー
├── sqlite_util.py       # SQLite ユーティリティ
├── rpi.py               # Raspberry Pi GPIO ユーティリティ
├── footprint.py         # タイムスタンプベースのマーカー
├── serializer.py        # pickle ベースの状態永続化
└── pytest_util.py       # pytest-xdist 並列実行サポート
```

### テスト構造

```
tests/
├── conftest.py          # 共有フィクスチャ、モック設定
├── unit/                # ユニットテスト（20以上のテストファイル）
├── integration/         # 統合テスト
└── fixtures/
    ├── config.example.yaml  # テスト用設定例
    └── chrome/test/     # Selenium プロファイル

reports/                 # テスト実行時に自動生成（.gitignore 対象）
├── pytest.html          # HTML テストレポート
└── coverage/            # カバレッジレポート
```

## 主要パターン

### センサー管理

統一されたインターフェースを持つ抽象基底クラス：

```python
class SensorBase(ABC):
    def ping(self) -> bool:          # センサー応答確認
    def get_value_map(self) -> dict: # 測定値取得
    def _ping_impl(self) -> bool:    # サブクラス実装
```

### 設定駆動設計

YAML 設定 + JSON Schema バリデーション：

```python
config = my_lib.config.load("config.yaml")  # 読み込み＋検証
slack_config = my_lib.notify.slack.parse_config(config["slack"])
```

環境変数の展開をサポート：
```yaml
influxdb:
    token: "${INFLUXDB_TOKEN}"
```

### 通知システム

レート制限とスロットリング：
- `/dev/shm/notify/` にフットプリントを使用
- 通知間隔の制限（デフォルト60秒）
- 複数チャンネル対応（Slack、LINE、メール）

### Flask デコレータ

```python
@my_lib.flask_util.gzipped              # レスポンス圧縮
@my_lib.flask_util.file_etag(...)       # ETag キャッシュ
@my_lib.flask_util.support_jsonp()      # JSONP サポート
```

### pytest-xdist 対応

並列テスト実行時のファイルパス衝突を回避：

```python
# footprint.py, serializer.py で使用
path = my_lib.pytest_util.get_path(path_str)
# PYTEST_XDIST_WORKER 環境変数でサフィックスを付与
```

テストでファイル存在確認時は `my_lib.footprint.exists()` または
`my_lib.pytest_util.get_path()` を使用すること。

## 例外クラス

### センサー関連
- `SensorError` - 基底例外
- `SensorCommunicationError` - 通信エラー
- `SensorCRCError` - CRC チェックエラー

### 設定関連
- `ConfigValidationError` - スキーマ検証エラー（details 属性あり）
- `ConfigParseError` - YAML パースエラー
- `ConfigFileNotFoundError` - ファイル未発見

### 画像関連（pil_util.py）
- `FontNotFoundError` - フォントファイル未発見
- `ImageNotFoundError` - 画像ファイル未発見

## 開発時の注意

### 型チェック

- mypy と pyright の両方でチェック
- `tests/fixtures/` は除外設定済み

#### 基本方針

**`# type: ignore` コメントは最後の手段とする。** 型エラーが発生した場合は、まずコードを修正して型推論が正しく働くようにする。

対処の優先順位：
1. コードを修正して型推論できるようにする（変数への型注釈、`assert` による型ナローイング等）
2. `Any` 型を明示的に使用する（型情報がないライブラリの場合）
3. `# type: ignore` コメントを使用する（他に手段がない場合のみ）

**例外**: テストコード（`tests/`）では、可読性を優先して `# type: ignore` を許容する。

#### 型スタブがないライブラリへの対処

型スタブが提供されていないライブラリを使用する場合、`# type: ignore` コメントを大量に記述するのではなく、
戻り値を受け取る変数に `Any` 型注釈を付けて対処する：

```python
from typing import Any

# Good: Any 型注釈で型チェッカーに「このライブラリには型情報がない」ことを明示
resp: Any = api.get_items(request)
if resp.items_result is not None:
    for item in resp.items_result.items:
        ...

# Bad: 各行に type: ignore を記述
resp = api.get_items(request)
if resp.items_result is not None:  # type: ignore[union-attr]
    for item in resp.items_result.items:  # type: ignore[union-attr]
        ...
```

#### import 文の書き方

サブモジュールへのアクセスは、明示的な import を使用する：

```python
# Good: 明示的な import
import selenium.webdriver.support.expected_conditions
import urllib.parse
import urllib.error

# Bad: 暗黙的なサブモジュールアクセス
import selenium
selenium.webdriver.support.expected_conditions  # pyright エラー
```

#### docopt の `__doc__` 対応

`docopt` を使用する場合、`__doc__` が `str | None` のため assert で型を絞り込む：

```python
assert __doc__ is not None
args = docopt.docopt(__doc__)
```

### テスト作成

- `@pytest.mark.web` - Web テスト用マーカー（`--run-web` で実行）
- `@pytest.mark.mercari` - メルカリテスト用マーカー
- 一時ファイルは `temp_dir` フィクスチャを使用
- Slack 通知確認は `slack_checker` フィクスチャを使用

### ロギング規約

```python
import logging
logging.debug("詳細情報: %s", value)
logging.info("通常の操作情報")
logging.warning("警告")
logging.error("エラー")
```

## 外部依存

### 主要な依存関係
- **pyyaml** - YAML 設定ファイル
- **jsonschema** - 設定バリデーション
- **slack-sdk** - Slack API
- **line-bot-sdk** - LINE API
- **influxdb-client** - 時系列データベース
- **smbus2** - I2C 通信（Raspberry Pi）
- **selenium** - Web 自動化

### 開発用依存関係
- **pytest**, **pytest-cov**, **pytest-xdist** - テスト
- **mypy**, **pyright** - 型チェック
- **flask** - Web テスト用
- **pillow** - 画像処理テスト用
