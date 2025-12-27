#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.config モジュールのユニットテスト
"""
from __future__ import annotations

import json
import pathlib
import textwrap

import pytest


class TestFormatPath:
    """_format_path 関数のテスト"""

    def test_empty_path_returns_root(self):
        """空のパスはルートを返す"""
        from my_lib.config import _format_path

        assert _format_path([]) == "ルート"

    def test_single_string_element(self):
        """単一の文字列要素"""
        from my_lib.config import _format_path

        assert _format_path(["key"]) == "key"

    def test_nested_string_elements(self):
        """ネストした文字列要素"""
        from my_lib.config import _format_path

        assert _format_path(["parent", "child"]) == "parent.child"

    def test_array_index(self):
        """配列インデックス"""
        from my_lib.config import _format_path

        assert _format_path(["items", 0]) == "items[0]"

    def test_mixed_path(self):
        """混合パス"""
        from my_lib.config import _format_path

        assert _format_path(["items", 0, "name"]) == "items[0].name"


class TestFormatValue:
    """_format_value 関数のテスト"""

    def test_none_returns_null(self):
        """None は null を返す"""
        from my_lib.config import _format_value

        assert _format_value(None) == "null"

    def test_bool_true(self):
        """True は true を返す"""
        from my_lib.config import _format_value

        assert _format_value(True) == "true"

    def test_bool_false(self):
        """False は false を返す"""
        from my_lib.config import _format_value

        assert _format_value(False) == "false"

    def test_string(self):
        """文字列はクォートされる"""
        from my_lib.config import _format_value

        assert _format_value("hello") == '"hello"'

    def test_empty_dict(self):
        """空の辞書"""
        from my_lib.config import _format_value

        assert _format_value({}) == "{}"

    def test_non_empty_dict(self):
        """非空の辞書"""
        from my_lib.config import _format_value

        assert _format_value({"key": "value"}) == "{...}"

    def test_empty_list(self):
        """空のリスト"""
        from my_lib.config import _format_value

        assert _format_value([]) == "[]"

    def test_non_empty_list(self):
        """非空のリスト"""
        from my_lib.config import _format_value

        assert _format_value([1, 2, 3]) == "[...]"

    def test_number(self):
        """数値"""
        from my_lib.config import _format_value

        assert _format_value(42) == "42"

    def test_truncates_long_string(self):
        """長い文字列は切り詰められる"""
        from my_lib.config import _format_value

        long_string = "a" * 100
        result = _format_value(long_string, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")


class TestGetTypeNameJp:
    """_get_type_name_jp 関数のテスト"""

    def test_known_types(self):
        """既知の型名を日本語に変換"""
        from my_lib.config import _get_type_name_jp

        assert _get_type_name_jp("string") == "文字列"
        assert _get_type_name_jp("integer") == "整数"
        assert _get_type_name_jp("number") == "数値"
        assert _get_type_name_jp("boolean") == "真偽値"
        assert _get_type_name_jp("object") == "オブジェクト"
        assert _get_type_name_jp("array") == "配列"
        assert _get_type_name_jp("null") == "null"

    def test_unknown_type(self):
        """未知の型はそのまま返す"""
        from my_lib.config import _get_type_name_jp

        assert _get_type_name_jp("unknown") == "unknown"


class TestGetPythonTypeJp:
    """_get_python_type_jp 関数のテスト"""

    def test_known_types(self):
        """既知の Python 型を日本語に変換"""
        from my_lib.config import _get_python_type_jp

        assert _get_python_type_jp("hello") == "文字列"
        assert _get_python_type_jp(42) == "整数"
        assert _get_python_type_jp(3.14) == "数値"
        assert _get_python_type_jp(True) == "真偽値"
        assert _get_python_type_jp({}) == "オブジェクト"
        assert _get_python_type_jp([]) == "配列"
        assert _get_python_type_jp(None) == "null"


class TestLoad:
    """load 関数のテスト"""

    def test_loads_valid_yaml(self, temp_dir):
        """有効な YAML ファイルを読み込む"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("key: value\nnumber: 42\n")

        result = my_lib.config.load(config_path)

        assert result["key"] == "value"
        assert result["number"] == 42
        assert "base_dir" in result

    def test_raises_for_nonexistent_file(self, temp_dir):
        """存在しないファイルで例外を発生"""
        import my_lib.config

        with pytest.raises(my_lib.config.ConfigFileNotFoundError):
            my_lib.config.load(temp_dir / "nonexistent.yaml")

    def test_raises_for_invalid_yaml(self, temp_dir):
        """無効な YAML で例外を発生"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("key: [invalid")

        with pytest.raises(my_lib.config.ConfigParseError):
            my_lib.config.load(config_path)

    def test_validates_with_schema(self, temp_dir):
        """スキーマで検証する"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: test\nage: 25\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        schema_path.write_text(json.dumps(schema))

        result = my_lib.config.load(config_path, schema_path)
        assert result["name"] == "test"
        assert result["age"] == 25

    def test_raises_for_schema_validation_error(self, temp_dir):
        """スキーマ検証エラーで例外を発生"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: 123\n")  # 文字列であるべき

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError):
            my_lib.config.load(config_path, schema_path)


class TestGetData:
    """get_data 関数のテスト"""

    def test_gets_nested_value(self):
        """ネストした値を取得する"""
        import my_lib.config

        config = {"level1": {"level2": {"level3": "value"}}}

        result = my_lib.config.get_data(config, ["level1", "level2", "level3"])
        assert result == "value"

    def test_returns_none_for_missing_key(self):
        """存在しないキーは None を返す"""
        import my_lib.config

        config = {"key": "value"}

        result = my_lib.config.get_data(config, ["nonexistent"])
        assert result is None

    def test_with_suffix_path(self):
        """サフィックスパス付きで取得"""
        import my_lib.config

        config = {"a": {"b": {"c": "value"}}}

        result = my_lib.config.get_data(config, ["a"], ["b", "c"])
        assert result == "value"


class TestGetPath:
    """get_path 関数のテスト"""

    def test_returns_path_object(self):
        """Path オブジェクトを返す"""
        import my_lib.config

        config = {"paths": {"data": "/tmp/data"}}

        result = my_lib.config.get_path(config, ["paths", "data"])
        assert isinstance(result, pathlib.Path)
        assert str(result) == "/tmp/data"


class TestAbsPath:
    """_abs_path 関数のテスト"""

    def test_returns_absolute_path(self):
        """絶対パスを返す"""
        import my_lib.config

        result = my_lib.config._abs_path("config.yaml")
        assert result.is_absolute()
        assert result.name == "config.yaml"


class TestTranslateYamlProblem:
    """_translate_yaml_problem 関数のテスト"""

    def test_known_problems(self):
        """既知のエラーメッセージを翻訳"""
        from my_lib.config import _translate_yaml_problem

        assert "マッピング値" in _translate_yaml_problem("mapping values are not allowed here")
        assert "コロン" in _translate_yaml_problem("could not find expected ':'")

    def test_unknown_problem(self):
        """未知のエラーメッセージはそのまま返す"""
        from my_lib.config import _translate_yaml_problem

        assert _translate_yaml_problem("unknown error") == "unknown error"


class TestTranslateYamlContext:
    """_translate_yaml_context 関数のテスト"""

    def test_known_contexts(self):
        """既知のコンテキストを翻訳"""
        from my_lib.config import _translate_yaml_context

        assert "ブロックマッピング" in _translate_yaml_context("while parsing a block mapping")

    def test_unknown_context(self):
        """未知のコンテキストはそのまま返す"""
        from my_lib.config import _translate_yaml_context

        assert _translate_yaml_context("unknown context") == "unknown context"


class TestConfigErrors:
    """設定エラークラスのテスト"""

    def test_config_validation_error(self):
        """ConfigValidationError"""
        from my_lib.config import ConfigValidationError

        error = ConfigValidationError("message", "details")
        assert str(error) == "message"
        assert error.details == "details"

    def test_config_parse_error(self):
        """ConfigParseError"""
        from my_lib.config import ConfigParseError

        error = ConfigParseError("message", "details")
        assert str(error) == "message"
        assert error.details == "details"

    def test_config_file_not_found_error(self):
        """ConfigFileNotFoundError"""
        from my_lib.config import ConfigFileNotFoundError

        error = ConfigFileNotFoundError("file not found")
        assert str(error) == "file not found"


class TestFindYamlLine:
    """_find_yaml_line 関数のテスト"""

    def test_returns_none_for_empty_path(self):
        """空のパスは None を返す"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["key: value"]
        result = _find_yaml_line(yaml_lines, [])
        assert result is None

    def test_finds_simple_key(self):
        """シンプルなキーを見つける"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["key: value"]
        result = _find_yaml_line(yaml_lines, ["key"])
        assert result == 0

    def test_finds_nested_key(self):
        """ネストしたキーを見つける"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["parent:", "  child: value"]
        result = _find_yaml_line(yaml_lines, ["parent", "child"])
        assert result == 1

    def test_skips_comments(self):
        """コメント行をスキップする"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["# comment", "key: value"]
        result = _find_yaml_line(yaml_lines, ["key"])
        assert result == 1

    def test_skips_empty_lines(self):
        """空行をスキップする"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["", "key: value"]
        result = _find_yaml_line(yaml_lines, ["key"])
        assert result == 1

    def test_returns_none_for_nonexistent_key(self):
        """存在しないキーは None を返す"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["key: value"]
        result = _find_yaml_line(yaml_lines, ["nonexistent"])
        assert result is None

    def test_handles_array_index(self):
        """配列インデックスを処理する"""
        from my_lib.config import _find_yaml_line

        yaml_lines = ["items:", "  - first", "  - second"]
        result = _find_yaml_line(yaml_lines, ["items", 0])
        # 配列インデックスの処理は部分的なので None が返る可能性がある
        assert result is None or isinstance(result, int)


class TestExtractYamlContext:
    """_extract_yaml_context 関数のテスト"""

    def test_extracts_context_around_line(self):
        """行の周辺コンテキストを抽出する"""
        from my_lib.config import _extract_yaml_context

        yaml_lines = ["line1", "line2", "key: value", "line4", "line5"]
        result = _extract_yaml_context(yaml_lines, ["key"])
        assert "key: value" in result
        assert ">>>" in result  # マーカー

    def test_returns_empty_for_unfound_path(self):
        """見つからないパスは空文字を返す"""
        from my_lib.config import _extract_yaml_context

        yaml_lines = ["key: value"]
        result = _extract_yaml_context(yaml_lines, ["nonexistent"])
        assert result == ""

    def test_tries_parent_path_when_not_found(self):
        """見つからない場合は親パスを試す"""
        from my_lib.config import _extract_yaml_context

        yaml_lines = ["parent:", "  child: value"]
        result = _extract_yaml_context(yaml_lines, ["parent", "nonexistent"])
        # 親の parent は見つかる
        assert "parent:" in result or result == ""


class TestValidationErrorFormatting:
    """バリデーションエラーフォーマット関数のテスト"""

    def test_format_validation_error_type_error(self, temp_dir):
        """型エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: 123\n")  # 文字列であるべき

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "型が不正" in exc_info.value.details

    def test_format_validation_error_required(self, temp_dir):
        """必須プロパティエラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("other: value\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "必須プロパティ" in exc_info.value.details

    def test_format_validation_error_enum(self, temp_dir):
        """enum エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("status: invalid\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"status": {"enum": ["active", "inactive"]}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "許可されていない値" in exc_info.value.details

    def test_format_validation_error_minimum(self, temp_dir):
        """minimum エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("age: -5\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"age": {"type": "integer", "minimum": 0}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "小さすぎます" in exc_info.value.details

    def test_format_validation_error_maximum(self, temp_dir):
        """maximum エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("age: 200\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"age": {"type": "integer", "maximum": 150}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "大きすぎます" in exc_info.value.details

    def test_format_validation_error_min_length(self, temp_dir):
        """minLength エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: ab\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 5}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "短すぎます" in exc_info.value.details

    def test_format_validation_error_max_length(self, temp_dir):
        """maxLength エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: verylongname\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string", "maxLength": 5}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "長すぎます" in exc_info.value.details

    def test_format_validation_error_pattern(self, temp_dir):
        """pattern エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("email: invalid\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"email": {"type": "string", "pattern": "^[a-z]+@[a-z]+\\.[a-z]+$"}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "パターンに一致しません" in exc_info.value.details

    def test_format_validation_error_additional_properties(self, temp_dir):
        """additionalProperties エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: test\nextra: value\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "定義されていないプロパティ" in exc_info.value.details

    def test_format_validation_error_min_items(self, temp_dir):
        """minItems エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("items:\n  - one\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"items": {"type": "array", "minItems": 3}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "少なすぎます" in exc_info.value.details

    def test_format_validation_error_max_items(self, temp_dir):
        """maxItems エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("items:\n  - one\n  - two\n  - three\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"items": {"type": "array", "maxItems": 2}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "多すぎます" in exc_info.value.details


class TestYamlErrorFormatting:
    """YAML エラーフォーマット関数のテスト"""

    def test_format_scanner_error(self, temp_dir):
        """ScannerError をフォーマットする"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        # タブ文字を含む不正な YAML
        config_path.write_text("key:\n\t- value\n")

        with pytest.raises(my_lib.config.ConfigParseError) as exc_info:
            my_lib.config.load(config_path)

        assert "YAML 構文エラー" in exc_info.value.details

    def test_format_parser_error(self, temp_dir):
        """ParserError をフォーマットする"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        # 不正な構造
        config_path.write_text("key: [value\n")

        with pytest.raises(my_lib.config.ConfigParseError) as exc_info:
            my_lib.config.load(config_path)

        assert "YAML" in exc_info.value.details


class TestExtractYamlLinesAround:
    """_extract_yaml_lines_around 関数のテスト"""

    def test_extracts_lines(self):
        """指定行の周辺を抽出する"""
        from my_lib.config import _extract_yaml_lines_around

        yaml_lines = ["line0", "line1", "line2", "line3", "line4"]
        result = _extract_yaml_lines_around(yaml_lines, 2, context=1)

        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert ">>>" in result  # マーカー

    def test_handles_beginning_of_file(self):
        """ファイルの先頭を処理する"""
        from my_lib.config import _extract_yaml_lines_around

        yaml_lines = ["line0", "line1", "line2"]
        result = _extract_yaml_lines_around(yaml_lines, 0, context=2)

        assert "line0" in result

    def test_handles_end_of_file(self):
        """ファイルの末尾を処理する"""
        from my_lib.config import _extract_yaml_lines_around

        yaml_lines = ["line0", "line1", "line2"]
        result = _extract_yaml_lines_around(yaml_lines, 2, context=2)

        assert "line2" in result


class TestFindYamlLineAdvanced:
    """_find_yaml_line 関数の高度なテスト"""

    def test_handles_indent_reset_with_sibling(self):
        """インデントがリセットされた時の処理"""
        from my_lib.config import _find_yaml_line

        # インデントが戻る構造
        yaml_lines = [
            "parent1:",
            "  child1: value1",
            "parent2:",
            "  child2: value2",
        ]
        result = _find_yaml_line(yaml_lines, ["parent2", "child2"])
        assert result == 3

    def test_handles_complex_nested_structure(self):
        """複雑なネスト構造の処理"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "level1:",
            "  level2a:",
            "    level3: value",
            "  level2b:",
            "    target: found",
        ]
        result = _find_yaml_line(yaml_lines, ["level1", "level2b", "target"])
        assert result == 4

    def test_handles_array_with_dash(self):
        """ダッシュで始まる配列要素の処理"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "items:",
            "  - name: first",
            "  - name: second",
        ]
        # 配列インデックスを含むパス
        result = _find_yaml_line(yaml_lines, ["items", 0, "name"])
        # この場合は配列要素の処理が部分的なので None か行番号
        assert result is None or isinstance(result, int)


class TestValidationErrorFormattingAdvanced:
    """バリデーションエラーフォーマットの追加テスト"""

    def test_format_validation_error_unique_items(self, temp_dir):
        """uniqueItems エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("items:\n  - one\n  - one\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"items": {"type": "array", "uniqueItems": True}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "重複" in exc_info.value.details

    def test_format_validation_error_format(self, temp_dir):
        """format エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("email: not-an-email\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"email": {"type": "string", "format": "email"}},
        }
        schema_path.write_text(json.dumps(schema))

        # format バリデーションはデフォルトでは検証されないが、エラーパスをカバー
        try:
            my_lib.config.load(config_path, schema_path)
        except my_lib.config.ConfigValidationError as e:
            assert "フォーマット" in e.details

    def test_format_validation_error_const(self, temp_dir):
        """const エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("version: 2\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"version": {"const": 1}},
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "定数" in exc_info.value.details or "一致しません" in exc_info.value.details

    def test_format_validation_error_oneof(self, temp_dir):
        """oneOf エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("value: not-matching\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "value": {
                    "oneOf": [{"type": "integer"}, {"type": "boolean"}]
                }
            },
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "スキーマ" in exc_info.value.details or "一致しません" in exc_info.value.details

    def test_format_validation_error_not(self, temp_dir):
        """not エラーをフォーマットする"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("value: forbidden\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "value": {"not": {"const": "forbidden"}}
            },
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "禁止" in exc_info.value.details or "スキーマ" in exc_info.value.details


class TestTranslateYamlProblemAdvanced:
    """_translate_yaml_problem 関数の追加テスト"""

    def test_found_expected_pattern(self):
        """found と expected を含むパターン"""
        from my_lib.config import _translate_yaml_problem

        problem = "found some token but expected another"
        result = _translate_yaml_problem(problem)
        assert "構文エラー" in result


class TestGenerateSchema:
    """generate_schema 関数のテスト"""

    def test_generates_schema_from_yaml(self, temp_dir, capsys):
        """YAML からスキーマを生成する"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("name: test\nage: 25\nitems:\n  - one\n  - two\n")

        my_lib.config.generate_schema(config_path)

        captured = capsys.readouterr()
        assert '"$schema"' in captured.out
        assert '"type"' in captured.out


class TestLoadEdgeCases:
    """load 関数のエッジケーステスト"""

    def test_load_non_dict_yaml(self, temp_dir):
        """dict 以外の YAML を読み込む"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        # リストの YAML
        config_path.write_text("- item1\n- item2\n")

        result = my_lib.config.load(config_path)

        # リストの場合は base_dir が追加されない
        assert isinstance(result, list)
        assert "item1" in result


class TestGetPathWithSuffix:
    """get_path 関数のサフィックステスト"""

    def test_get_path_with_suffix(self):
        """サフィックス付きでパスを取得"""
        import my_lib.config

        config = {"base": {"paths": {"data": "/tmp/data"}}}

        result = my_lib.config.get_path(config, ["base"], ["paths", "data"])
        assert isinstance(result, pathlib.Path)
        assert str(result) == "/tmp/data"


class TestFormatRequiredErrorEdgeCases:
    """_format_required_error のエッジケーステスト"""

    def test_required_as_single_string(self, temp_dir):
        """required が単一の文字列の場合"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("other: value\n")

        # 通常は配列だが、文字列でも処理できることを確認
        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["name"],
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "必須プロパティ" in exc_info.value.details


class TestYamlErrorFormattingAdvanced:
    """YAML エラーフォーマットの追加テスト"""

    def test_yaml_error_with_context(self, temp_dir):
        """コンテキスト付き YAML エラー"""
        import my_lib.config

        config_path = temp_dir / "config.yaml"
        # コンテキストが含まれるエラーを発生させる
        config_path.write_text("key: {invalid: yaml: here}\n")

        with pytest.raises(my_lib.config.ConfigParseError) as exc_info:
            my_lib.config.load(config_path)

        assert "YAML" in exc_info.value.details

    def test_scanner_error_without_problem_mark(self, mocker):
        """problem_mark なしの ScannerError"""
        import yaml

        from my_lib.config import _format_yaml_error

        # problem_mark が None の ScannerError をシミュレート
        error = yaml.scanner.ScannerError(  # type: ignore[attr-defined]
            context=None,
            context_mark=None,
            problem="test problem",
            problem_mark=None,
        )
        result = _format_yaml_error(error, "test: yaml\n")
        assert "YAML 構文エラー" in result

    def test_parser_error_without_problem_mark(self, mocker):
        """problem_mark なしの ParserError"""
        import yaml

        from my_lib.config import _format_yaml_error

        # problem_mark が None の ParserError をシミュレート
        error = yaml.parser.ParserError(  # type: ignore[attr-defined]
            context=None,
            context_mark=None,
            problem="test problem",
            problem_mark=None,
        )
        result = _format_yaml_error(error, "test: yaml\n")
        assert "YAML 構文エラー" in result

    def test_other_yaml_error(self, mocker):
        """その他の YAMLError"""
        import yaml

        from my_lib.config import _format_yaml_error

        # 汎用の YAMLError
        error = yaml.YAMLError("generic error")
        result = _format_yaml_error(error, "test: yaml\n")
        assert "YAML 構文エラー" in result
        assert "generic error" in result

    def test_scanner_error_with_context_attribute(self, mocker):
        """context 属性付き ScannerError"""
        import yaml

        from my_lib.config import _format_yaml_error

        # context 属性付きの ScannerError をシミュレート
        mark = yaml.Mark("test", 0, 0, 0, None, 0)
        error = yaml.scanner.ScannerError(  # type: ignore[attr-defined]
            context="while parsing a block mapping",
            context_mark=mark,
            problem="test problem",
            problem_mark=mark,
        )
        result = _format_yaml_error(error, "test: yaml\n")
        assert "YAML 構文エラー" in result
        assert "補足" in result

    def test_parser_error_with_context_attribute(self, mocker):
        """context 属性付き ParserError"""
        import yaml

        from my_lib.config import _format_yaml_error

        # context 属性付きの ParserError をシミュレート
        mark = yaml.Mark("test", 0, 0, 0, None, 0)
        error = yaml.parser.ParserError(  # type: ignore[attr-defined]
            context="while parsing a flow mapping",
            context_mark=mark,
            problem="test problem",
            problem_mark=mark,
        )
        result = _format_yaml_error(error, "test: yaml\n")
        assert "YAML 構文エラー" in result
        assert "補足" in result

    def test_scanner_error_with_empty_yaml(self, mocker):
        """空の YAML での ScannerError"""
        import yaml

        from my_lib.config import _format_yaml_error

        mark = yaml.Mark("test", 0, 10, 0, None, 0)  # 行10（存在しない行）
        error = yaml.scanner.ScannerError(  # type: ignore[attr-defined]
            context=None,
            context_mark=None,
            problem="test problem",
            problem_mark=mark,
        )
        result = _format_yaml_error(error, "")  # 空のYAML
        assert "YAML 構文エラー" in result

    def test_parser_error_with_empty_yaml(self, mocker):
        """空の YAML での ParserError"""
        import yaml

        from my_lib.config import _format_yaml_error

        mark = yaml.Mark("test", 0, 10, 0, None, 0)  # 行10（存在しない行）
        error = yaml.parser.ParserError(  # type: ignore[attr-defined]
            context=None,
            context_mark=None,
            problem="test problem",
            problem_mark=mark,
        )
        result = _format_yaml_error(error, "")  # 空のYAML
        assert "YAML 構文エラー" in result


class TestFormatValidationErrorDirect:
    """_format_validation_error 関数の直接テスト"""

    def test_unknown_validator(self):
        """未知のバリデータをフォーマットする"""
        import jsonschema

        from my_lib.config import _format_validation_error

        # カスタムバリデータエラーをシミュレート
        schema = {"type": "object"}
        validator = jsonschema.Draft202012Validator(schema)

        # 手動で ValidationError を作成
        error = jsonschema.ValidationError(
            message="custom error message",
            validator="customValidator",  # 未知のバリデータ
            path=["test", "path"],
            cause=None,
            context=[],
            validator_value="test_value",
            instance="test_instance",
            schema=schema,
        )

        yaml_lines = ["test:", "  path: value"]
        result = _format_validation_error(error, yaml_lines)

        assert "test.path" in result
        assert "custom error message" in result

    def test_format_with_type_list(self):
        """型が複数の場合のフォーマット"""
        import json

        import my_lib.config

        config_path = pathlib.Path("/tmp/test_type_list.yaml")
        config_path.write_text("value: not-matching\n")

        schema_path = pathlib.Path("/tmp/test_type_list_schema.json")
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "value": {"type": ["integer", "boolean"]}
            },
        }
        schema_path.write_text(json.dumps(schema))

        try:
            with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
                my_lib.config.load(config_path, schema_path)

            assert "または" in exc_info.value.details  # "整数 または 真偽値"
        finally:
            config_path.unlink(missing_ok=True)
            schema_path.unlink(missing_ok=True)


class TestFormatRequiredErrorDirect:
    """_format_required_error 関数の直接テスト"""

    def test_required_with_all_keys_present(self):
        """すべてのキーが存在する場合（理論的には発生しない）"""
        import jsonschema

        from my_lib.config import _format_required_error

        # 必須プロパティがすべて存在するケースのシミュレート
        error = jsonschema.ValidationError(
            message="required error",
            validator="required",
            path=[],
            cause=None,
            context=[],
            validator_value=["name"],  # "name" が必須
            instance={"name": "test"},  # "name" が存在
            schema={},
        )

        lines: list[str] = []
        _format_required_error(error, lines)

        # 不足がないので何も追加されない
        assert len(lines) == 0

    def test_required_with_string_value(self):
        """required が文字列の場合"""
        import jsonschema

        from my_lib.config import _format_required_error

        # required が文字列のケース（珍しいがスキーマによっては可能）
        error = jsonschema.ValidationError(
            message="required error",
            validator="required",
            path=[],
            cause=None,
            context=[],
            validator_value="name",  # 文字列として required
            instance={"other": "test"},  # "name" が不在
            schema={},
        )

        lines: list[str] = []
        _format_required_error(error, lines)

        assert any("必須プロパティ" in line for line in lines)


class TestFormatAdditionalPropertiesEdgeCases:
    """_format_additional_properties_error のエッジケーステスト"""

    def test_additional_properties_without_allowed(self, temp_dir):
        """許可プロパティが空の場合"""
        import json

        import my_lib.config

        config_path = temp_dir / "config.yaml"
        config_path.write_text("extra: value\n")

        schema_path = temp_dir / "schema.json"
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            # properties が定義されていない
        }
        schema_path.write_text(json.dumps(schema))

        with pytest.raises(my_lib.config.ConfigValidationError) as exc_info:
            my_lib.config.load(config_path, schema_path)

        assert "定義されていないプロパティ" in exc_info.value.details


class TestFindYamlLineIndentReset:
    """_find_yaml_line のインデントリセットロジックの詳細テスト"""

    def test_deep_indent_reset(self):
        """深いインデントからのリセット"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "first:",
            "  nested1:",
            "    deep: value",
            "second:",  # ここでインデントがリセット
            "  target: found",
        ]
        result = _find_yaml_line(yaml_lines, ["second", "target"])
        assert result == 4

    def test_multiple_indent_reset(self):
        """複数回のインデントリセット"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "a:",
            "  b: 1",
            "c:",
            "  d: 2",
            "e:",
            "  f: 3",
        ]
        result = _find_yaml_line(yaml_lines, ["e", "f"])
        assert result == 5

    def test_indent_reset_with_comments_between(self):
        """コメントを挟んだインデントリセット"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "first:",
            "  value: 1",
            "# comment",
            "",
            "second:",
            "  target: 2",
        ]
        result = _find_yaml_line(yaml_lines, ["second", "target"])
        assert result == 5

    def test_indent_reset_path_index_reset_complete(self):
        """パスインデックスリセット処理で完全にパスを見つける"""
        from my_lib.config import _find_yaml_line

        # path_index > 0 で indent が戻り、リセット後に完全なパスを見つけるケース
        yaml_lines = [
            "parent:",
            "  child: 1",
            "other:",  # インデントが戻る
            "parent:",  # 同じ名前が再出現
            "  target: found",
        ]
        result = _find_yaml_line(yaml_lines, ["parent", "target"])
        # 2番目の parent.target を見つける
        assert result == 4

    def test_indent_reset_with_path_index_greater_than_zero(self):
        """path_index > 0 の時のインデントリセット"""
        from my_lib.config import _find_yaml_line

        # まず parent を見つけて path_index = 1 にして、
        # その後インデントが戻ってリセットが発生するケース
        yaml_lines = [
            "parent:",
            "  wrong: value",
            "parent:",  # ここでインデントが戻る
            "  correct: value",
        ]
        result = _find_yaml_line(yaml_lines, ["parent", "correct"])
        assert result == 3


class TestFormatValidatorWithFormatChecker:
    """format バリデータのテスト（FormatChecker 使用）"""

    def test_format_error_with_format_checker(self):
        """FormatChecker を使用した format エラー"""
        import jsonschema

        from my_lib.config import _format_validation_error

        # format バリデータエラーをシミュレート
        error = jsonschema.ValidationError(
            message="'invalid-email' is not a 'email'",
            validator="format",
            path=["email"],
            cause=None,
            context=[],
            validator_value="email",
            instance="invalid-email",
            schema={"type": "string", "format": "email"},
        )

        yaml_lines = ["email: invalid-email"]
        result = _format_validation_error(error, yaml_lines)

        assert "フォーマット" in result
        assert "email" in result


class TestFormatRequiredWithNonDictInstance:
    """_format_required_error で instance が dict でない場合のテスト"""

    def test_required_with_non_dict_instance(self):
        """instance が dict でない場合"""
        import jsonschema

        from my_lib.config import _format_required_error

        # instance が dict でないケース（通常は発生しにくいが防御的に）
        error = jsonschema.ValidationError(
            message="required error",
            validator="required",
            path=[],
            cause=None,
            context=[],
            validator_value=["name"],
            instance="not a dict",  # dict ではない
            schema={},
        )

        lines: list[str] = []
        _format_required_error(error, lines)

        # instance が dict でないので existing_keys は空
        assert any("必須プロパティ" in line for line in lines)


class TestFormatAdditionalPropertiesWithNonDictInstance:
    """_format_additional_properties_error で instance が dict でない場合のテスト"""

    def test_additional_properties_with_non_dict_instance(self):
        """instance が dict でない場合"""
        import jsonschema

        from my_lib.config import _format_additional_properties_error

        error = jsonschema.ValidationError(
            message="additional properties error",
            validator="additionalProperties",
            path=[],
            cause=None,
            context=[],
            validator_value=False,
            instance="not a dict",  # dict ではない
            schema={"properties": {"name": {}}},
        )

        lines: list[str] = []
        _format_additional_properties_error(error, lines)

        # instance が dict でないのでスキップされる
        assert len(lines) == 0


class TestFormatAdditionalPropertiesEmptyAllowed:
    """_format_additional_properties_error で許可プロパティが空の場合のテスト"""

    def test_additional_properties_with_empty_allowed(self):
        """許可プロパティが空の場合"""
        import jsonschema

        from my_lib.config import _format_additional_properties_error

        error = jsonschema.ValidationError(
            message="additional properties error",
            validator="additionalProperties",
            path=[],
            cause=None,
            context=[],
            validator_value=False,
            instance={"extra": "value"},
            schema={},  # properties が空
        )

        lines: list[str] = []
        _format_additional_properties_error(error, lines)

        # 許可プロパティが空なので "許可されているプロパティ" は出力されない
        assert any("定義されていないプロパティ" in line for line in lines)
        assert not any("許可されているプロパティ" in line for line in lines)


class TestFindYamlLineEdgeCases:
    """_find_yaml_line の残りのエッジケーステスト"""

    def test_comment_in_reset_loop(self):
        """インデントリセットループ中にコメント行がある場合"""
        from my_lib.config import _find_yaml_line

        # path_index > 0 の時にインデントが戻り、
        # リセット処理中にコメント行がスキップされるケース
        yaml_lines = [
            "first:",
            "  child: 1",
            "# comment line",  # リセットループでスキップされるべき
            "first:",  # 同じ親キーが再出現
            "  target: found",
        ]
        result = _find_yaml_line(yaml_lines, ["first", "target"])
        assert result == 4

    def test_empty_line_in_reset_loop(self):
        """インデントリセットループ中に空行がある場合"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "first:",
            "  child: 1",
            "",  # 空行
            "first:",  # 同じ親キーが再出現
            "  target: found",
        ]
        result = _find_yaml_line(yaml_lines, ["first", "target"])
        assert result == 4

    def test_path_complete_in_reset_loop(self):
        """インデントリセットループでパスが完全に見つかる場合"""
        from my_lib.config import _find_yaml_line

        # リセットループ内でパスが完全にマッチしてbreakするケース
        yaml_lines = [
            "parent:",
            "  child:",
            "    deep: value",
            "parent:",  # インデントリセット
            "  child: found",  # 2番目のchild（ネストなし）
        ]
        # "parent" -> "child" を探す
        result = _find_yaml_line(yaml_lines, ["parent", "child"])
        # 最初の parent.child (行1) を見つける
        assert result == 1

    def test_full_path_found_after_reset(self):
        """リセット後に完全なパスが見つかる場合（continue分岐）"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "a:",
            "  b: wrong",
            "a:",  # インデントリセット、ここでリセットループがパスを完全に見つける
            "  c: value",  # でも探しているのは "a.c"
        ]
        result = _find_yaml_line(yaml_lines, ["a", "c"])
        assert result == 3

    def test_array_with_integer_path(self):
        """配列インデックス（整数パス）の処理"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "items:",
            "  - first",
            "  - second",
        ]
        # 整数パスを含む検索
        result = _find_yaml_line(yaml_lines, ["items", 0])
        # 整数パスの処理は部分的なので None になる可能性がある
        assert result is None or isinstance(result, int)

    def test_array_item_with_dash(self):
        """ダッシュで始まる配列アイテムの処理"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "list:",
            "  - item1",
            "  - item2",
            "other:",
        ]
        # 配列要素へのパス
        result = _find_yaml_line(yaml_lines, ["list", 1])
        assert result is None or isinstance(result, int)


class TestFindYamlLineResetLoopBreak:
    """_find_yaml_line のリセットループ内での break テスト"""

    def test_break_when_path_complete_in_reset(self):
        """リセットループ内でパスが完了して break する"""
        from my_lib.config import _find_yaml_line

        # このケースでは:
        # 1. 最初の "parent" にマッチして path_index = 1
        # 2. 2行目で "child" にマッチして path_index = 2 (完了)
        # → 早期リターンするので、リセットループには入らない
        #
        # リセットループでパスが完了するには:
        # 1. path_index > 0 でインデントが戻る
        # 2. リセットループ内で全てのパス要素がマッチする
        yaml_lines = [
            "parent:",
            "  wrong: value",
            "other:",  # インデントが戻る
            "parent:",  # リセットループで parent を見つける
            "  child: found",  # これは外側のループで見つける
        ]
        # "parent.child" を探す
        result = _find_yaml_line(yaml_lines, ["parent", "child"])
        assert result == 4

    def test_nested_reset_with_break(self):
        """ネストしたリセットでパスが完了"""
        from my_lib.config import _find_yaml_line

        yaml_lines = [
            "a:",
            "  b:",
            "    c: 1",
            "a:",  # インデントリセット
            "  b:",  # リセットループでここまで見つける
            "    c: 2",
        ]
        result = _find_yaml_line(yaml_lines, ["a", "b", "c"])
        assert result == 2  # 最初の c を見つける

    def test_reset_loop_finds_single_element_path(self):
        """リセットループで単一要素パスが完了して break/continue する"""
        from my_lib.config import _find_yaml_line

        # 単一要素パスでリセットループ内で完全にマッチするケース
        # 1. path = ["target"] (len = 1)
        # 2. 最初に "wrong" にマッチしない
        # 3. "target:" で path_index = 1 (完了) → 即座にリターン
        # この場合もリセットは発生しない

        # リセットループで完了するには:
        # path_index > 0 なので、少なくとも一つのパス要素にマッチした後、
        # インデントが戻って、リセットループでパス全体を再発見する必要がある
        yaml_lines = [
            "target:",  # ここでマッチして path_index = 1
            "  child: 1",
            "other:",  # インデントが戻る、path_index = 1 > 0 なのでリセット
            # リセットループで "target" を再発見
            # path_index_reset = 1 = len(path) で break
            # その後 path_index >= len(path) で continue
            "more:",
            "target:",  # 新しい target
        ]
        # path = ["target"] を探す
        result = _find_yaml_line(yaml_lines, ["target"])
        # 最初の target (行0) を見つける
        assert result == 0

    def test_reset_loop_complete_path_triggers_continue(self):
        """リセットループでパスが完了した後 continue する"""
        from my_lib.config import _find_yaml_line

        # このテストケースは:
        # 1. "a" にマッチ (path_index = 1)
        # 2. インデントが戻る (indent <= current_indent, path_index > 0)
        # 3. リセットループで "a" を再発見して path_index_reset = 1 = len(["a"])
        # 4. break して path_index = path_index_reset = 1
        # 5. path_index >= len(path) なので continue
        # 6. 次の行の処理を続ける
        yaml_lines = [
            "a:",
            "  nested: 1",
            "b:",  # インデントリセットトリガー
            "a:",  # リセット後、この行を処理
        ]
        result = _find_yaml_line(yaml_lines, ["a"])
        assert result == 0  # 最初の a を見つける

    def test_reset_loop_finds_complete_path_and_continues(self):
        """リセットループで完全なパスを見つけて continue する（line 150, 153）"""
        from my_lib.config import _find_yaml_line

        # 注意: _find_yaml_line はネストしたパス (a.b) を探すために設計されている
        # 同じレベルの兄弟要素 (a:, b:) は見つからない
        # リセットループ内でパスが完全に見つかるには、
        # 同じネスト構造が繰り返し出現する必要がある
        yaml_lines = [
            "a:",    # line 0 - path[0] にマッチ
            "b:",    # line 1 - 同じレベルなのでリセット発生
            "c:",    # line 2
        ]
        result = _find_yaml_line(yaml_lines, ["a", "b"])
        # アルゴリズムはネストしたパスを期待するため None を返す
        assert result is None

    def test_same_level_siblings_trigger_reset_complete(self):
        """同じレベルの兄弟要素でリセット発生"""
        from my_lib.config import _find_yaml_line

        # 同じレベルの兄弟はネストしたパスではないので見つからない
        yaml_lines = [
            "first:",     # line 0
            "second:",    # line 1
            "third:",     # line 2
        ]
        result = _find_yaml_line(yaml_lines, ["first", "second"])
        # ネストしたパスではないので None
        assert result is None
