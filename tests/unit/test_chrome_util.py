# ruff: noqa: S101
"""chrome_util.py のテスト"""

from __future__ import annotations

import pathlib
import sqlite3
import unittest.mock

import my_lib.chrome_util


class TestProfileHealthResult:
    """_ProfileHealthResult データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        result = my_lib.chrome_util._ProfileHealthResult(
            is_healthy=True,
            errors=(),
        )

        assert result.is_healthy is True
        assert result.errors == ()
        assert result.has_lock_files is False

    def test_creates_instance_with_errors(self):
        """エラー付きでインスタンスを作成する"""
        result = my_lib.chrome_util._ProfileHealthResult(
            is_healthy=False,
            errors=("Error 1", "Error 2"),
            has_lock_files=True,
            has_corrupted_json=True,
        )

        assert result.is_healthy is False
        assert len(result.errors) == 2
        assert result.has_lock_files is True
        assert result.has_corrupted_json is True


class TestCheckJsonFile:
    """_check_json_file 関数のテスト"""

    def test_returns_none_for_valid_json(self, temp_dir):
        """有効な JSON では None を返す"""
        json_file = temp_dir / "test.json"
        json_file.write_text('{"key": "value"}')

        result = my_lib.chrome_util._check_json_file(json_file)

        assert result is None

    def test_returns_none_for_nonexistent_file(self, temp_dir):
        """存在しないファイルでは None を返す"""
        json_file = temp_dir / "nonexistent.json"

        result = my_lib.chrome_util._check_json_file(json_file)

        assert result is None

    def test_returns_error_for_invalid_json(self, temp_dir):
        """無効な JSON ではエラーを返す"""
        json_file = temp_dir / "invalid.json"
        json_file.write_text("{invalid json}")

        result = my_lib.chrome_util._check_json_file(json_file)

        assert result is not None
        assert "corrupted" in result


class TestCheckSqliteDb:
    """_check_sqlite_db 関数のテスト"""

    def test_returns_none_for_valid_db(self, temp_dir):
        """有効な DB では None を返す"""
        db_file = temp_dir / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        result = my_lib.chrome_util._check_sqlite_db(db_file)

        assert result is None

    def test_returns_none_for_nonexistent_db(self, temp_dir):
        """存在しない DB では None を返す"""
        db_file = temp_dir / "nonexistent.db"

        result = my_lib.chrome_util._check_sqlite_db(db_file)

        assert result is None

    def test_returns_error_for_corrupted_db(self, temp_dir):
        """破損した DB ではエラーを返す"""
        db_file = temp_dir / "corrupted.db"
        db_file.write_bytes(b"This is not a valid SQLite database")

        result = my_lib.chrome_util._check_sqlite_db(db_file)

        assert result is not None
        assert "database" in result.lower()


class TestCleanupBloatedPreferences:
    """_cleanup_bloated_preferences 関数のテスト"""

    def _create_profile(self, temp_dir, preferences_size):
        """指定サイズの Preferences を持つプロファイルを作成する"""
        profile_path = temp_dir / "chrome" / "test_profile"
        default_path = profile_path / "Default"
        default_path.mkdir(parents=True)
        (default_path / "Preferences").write_bytes(b"x" * preferences_size)
        return profile_path

    def test_deletes_bloated_preferences(self, temp_dir):
        """閾値を超えた Preferences を削除する"""
        profile_path = self._create_profile(temp_dir, my_lib.chrome_util.PREFERENCES_SIZE_LIMIT_BYTES + 1)
        # セッション情報（Cookies）は削除されないことを確認するために作成
        cookies_path = profile_path / "Default" / "Cookies"
        cookies_path.write_bytes(b"session data")

        result = my_lib.chrome_util._cleanup_bloated_preferences(profile_path)

        assert result is True
        assert not (profile_path / "Default" / "Preferences").exists()
        assert cookies_path.exists()

    def test_keeps_normal_preferences(self, temp_dir):
        """閾値以下の Preferences は削除しない"""
        profile_path = self._create_profile(temp_dir, 1024)

        result = my_lib.chrome_util._cleanup_bloated_preferences(profile_path)

        assert result is False
        assert (profile_path / "Default" / "Preferences").exists()

    def test_keeps_preferences_at_limit(self, temp_dir):
        """ちょうど閾値の Preferences は削除しない"""
        profile_path = self._create_profile(temp_dir, my_lib.chrome_util.PREFERENCES_SIZE_LIMIT_BYTES)

        result = my_lib.chrome_util._cleanup_bloated_preferences(profile_path)

        assert result is False
        assert (profile_path / "Default" / "Preferences").exists()

    def test_returns_false_for_missing_preferences(self, temp_dir):
        """Preferences が存在しない場合は False を返す"""
        profile_path = temp_dir / "chrome" / "nonexistent_profile"

        result = my_lib.chrome_util._cleanup_bloated_preferences(profile_path)

        assert result is False

    def test_returns_false_when_unlink_fails(self, temp_dir):
        """削除に失敗した場合は False を返す"""
        profile_path = self._create_profile(temp_dir, my_lib.chrome_util.PREFERENCES_SIZE_LIMIT_BYTES + 1)

        with unittest.mock.patch.object(pathlib.Path, "unlink", side_effect=OSError("Permission denied")):
            result = my_lib.chrome_util._cleanup_bloated_preferences(profile_path)

        assert result is False


class TestCheckProfileHealth:
    """_check_profile_health 関数のテスト"""

    def test_returns_healthy_for_nonexistent_profile(self, temp_dir):
        """存在しないプロファイルは健全"""
        profile_path = temp_dir / "nonexistent_profile"

        result = my_lib.chrome_util._check_profile_health(profile_path)

        assert result.is_healthy is True
        assert result.errors == ()

    def test_detects_lock_files(self, temp_dir):
        """ロックファイルを検出する"""
        profile_path = temp_dir / "chrome" / "test_profile"
        profile_path.mkdir(parents=True)
        (profile_path / "SingletonLock").touch()

        result = my_lib.chrome_util._check_profile_health(profile_path)

        assert result.has_lock_files is True
        assert any("Lock file" in error for error in result.errors)

    def test_detects_corrupted_json(self, temp_dir):
        """破損した JSON を検出する"""
        profile_path = temp_dir / "chrome" / "test_profile"
        profile_path.mkdir(parents=True)
        (profile_path / "Local State").write_text("{invalid json")

        result = my_lib.chrome_util._check_profile_health(profile_path)

        assert result.has_corrupted_json is True
        assert not result.is_healthy

    def test_detects_corrupted_db(self, temp_dir):
        """破損した DB を検出する"""
        profile_path = temp_dir / "chrome" / "test_profile"
        default_path = profile_path / "Default"
        default_path.mkdir(parents=True)
        (default_path / "Cookies").write_bytes(b"corrupted data")

        result = my_lib.chrome_util._check_profile_health(profile_path)

        assert result.has_corrupted_db is True
        assert not result.is_healthy


class TestRecoverCorruptedProfile:
    """_recover_corrupted_profile 関数のテスト"""

    def test_returns_true_for_nonexistent_profile(self, temp_dir):
        """存在しないプロファイルでは True を返す"""
        profile_path = temp_dir / "nonexistent_profile"

        result = my_lib.chrome_util._recover_corrupted_profile(profile_path)

        assert result is True

    def test_moves_corrupted_profile(self, temp_dir):
        """破損したプロファイルを移動する"""
        profile_path = temp_dir / "corrupted_profile"
        profile_path.mkdir()
        (profile_path / "test_file.txt").write_text("test")

        result = my_lib.chrome_util._recover_corrupted_profile(profile_path)

        assert result is True
        assert not profile_path.exists()
        # バックアップが作成されていることを確認
        backup_dirs = list(temp_dir.glob("*corrupted*"))
        assert len(backup_dirs) == 1


class TestStartupFailureMarker:
    """連続起動失敗マーカー関連の関数テスト"""

    def test_read_returns_zero_when_marker_missing(self, temp_dir):
        """マーカー不在時は 0 を返す"""
        profile_path = temp_dir / "chrome" / "profile"

        result = my_lib.chrome_util._read_startup_failure_count(profile_path)

        assert result == 0

    def test_read_returns_value_from_marker(self, temp_dir):
        """マーカーから値を読み取る"""
        profile_path = temp_dir / "chrome" / "profile"
        profile_path.parent.mkdir(parents=True)
        marker = profile_path.parent / f"{profile_path.name}.startup_failures"
        marker.write_text("5")

        result = my_lib.chrome_util._read_startup_failure_count(profile_path)

        assert result == 5

    def test_read_returns_zero_for_invalid_content(self, temp_dir):
        """無効な内容のマーカーは 0 扱い"""
        profile_path = temp_dir / "chrome" / "profile"
        profile_path.parent.mkdir(parents=True)
        marker = profile_path.parent / f"{profile_path.name}.startup_failures"
        marker.write_text("not a number")

        result = my_lib.chrome_util._read_startup_failure_count(profile_path)

        assert result == 0

    def test_record_increments_count(self, temp_dir):
        """失敗を記録するとカウントが増える"""
        profile_path = temp_dir / "chrome" / "profile"
        profile_path.parent.mkdir(parents=True)

        first = my_lib.chrome_util._record_startup_failure(profile_path)
        second = my_lib.chrome_util._record_startup_failure(profile_path)
        third = my_lib.chrome_util._record_startup_failure(profile_path)

        assert first == 1
        assert second == 2
        assert third == 3

    def test_record_creates_parent_directory(self, temp_dir):
        """親ディレクトリが存在しなくても作成して記録する"""
        profile_path = temp_dir / "nonexistent" / "profile"

        result = my_lib.chrome_util._record_startup_failure(profile_path)

        assert result == 1
        marker = profile_path.parent / f"{profile_path.name}.startup_failures"
        assert marker.exists()

    def test_clear_removes_marker(self, temp_dir):
        """クリアでマーカーが削除される"""
        profile_path = temp_dir / "chrome" / "profile"
        profile_path.parent.mkdir(parents=True)
        my_lib.chrome_util._record_startup_failure(profile_path)
        marker = profile_path.parent / f"{profile_path.name}.startup_failures"
        assert marker.exists()

        my_lib.chrome_util._clear_startup_failures(profile_path)

        assert not marker.exists()

    def test_clear_handles_missing_marker(self, temp_dir):
        """マーカー不在でもエラーにならない"""
        profile_path = temp_dir / "chrome" / "profile"

        # 例外が発生しないことを確認
        my_lib.chrome_util._clear_startup_failures(profile_path)

    def test_marker_path_does_not_collide_with_corrupted_backup(self, temp_dir):
        """マーカーが corrupted バックアップのクリーンアップ対象にならない"""
        profile_path = temp_dir / "chrome" / "profile"
        profile_path.mkdir(parents=True)

        my_lib.chrome_util._record_startup_failure(profile_path)
        # NOTE: _recover_corrupted_profile は keep_latest=1 で過去の corrupted を掃除するが、
        #       マーカーファイルは startup_failures サフィックスでファイルなので対象外
        my_lib.chrome_util._recover_corrupted_profile(profile_path)

        marker = profile_path.parent / f"{profile_path.name}.startup_failures"
        assert marker.exists()


class TestCleanupProfileLock:
    """_cleanup_profile_lock 関数のテスト"""

    def test_removes_lock_files(self, temp_dir):
        """ロックファイルを削除する"""
        profile_path = temp_dir / "test_profile"
        profile_path.mkdir()
        lock_file = profile_path / "SingletonLock"
        lock_file.touch()

        my_lib.chrome_util._cleanup_profile_lock(profile_path)

        assert not lock_file.exists()

    def test_handles_nonexistent_locks(self, temp_dir):
        """存在しないロックファイルでも動作する"""
        profile_path = temp_dir / "test_profile"
        profile_path.mkdir()

        # エラーが発生しないことを確認
        my_lib.chrome_util._cleanup_profile_lock(profile_path)


class TestIsRunningInContainer:
    """_is_running_in_container 関数のテスト"""

    def test_returns_false_when_not_in_container(self):
        """コンテナ外では False を返す"""
        with unittest.mock.patch.object(pathlib.Path, "exists", return_value=False):
            result = my_lib.chrome_util._is_running_in_container()

            assert result is False

    def test_returns_true_when_in_container(self):
        """コンテナ内では True を返す"""
        with unittest.mock.patch.object(pathlib.Path, "exists", return_value=True):
            result = my_lib.chrome_util._is_running_in_container()

            assert result is True


class TestGetActualProfileName:
    """_get_actual_profile_name 関数のテスト"""

    def test_returns_name_without_suffix(self):
        """PYTEST_XDIST_WORKER がない場合はそのまま返す"""
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            result = my_lib.chrome_util._get_actual_profile_name("test_profile")

            assert result == "test_profile"

    def test_returns_name_with_suffix(self):
        """PYTEST_XDIST_WORKER がある場合はサフィックス付きで返す"""
        with unittest.mock.patch.dict("os.environ", {"PYTEST_XDIST_WORKER": "gw0"}):
            result = my_lib.chrome_util._get_actual_profile_name("test_profile")

            assert result == "test_profile.gw0"


class TestDeleteProfile:
    """delete_profile 関数のテスト"""

    def test_returns_true_for_nonexistent_profile(self, temp_dir):
        """存在しないプロファイルでは True を返す"""
        result = my_lib.chrome_util.delete_profile("nonexistent", temp_dir)

        assert result is True

    def test_deletes_existing_profile(self, temp_dir):
        """存在するプロファイルを削除する"""
        # NOTE: PYTEST_XDIST_WORKER 環境変数を考慮した実際のプロファイル名を使用
        actual_name = my_lib.chrome_util._get_actual_profile_name("test_profile")
        profile_path = temp_dir / "chrome" / actual_name
        profile_path.mkdir(parents=True)
        (profile_path / "test_file.txt").write_text("test")

        result = my_lib.chrome_util.delete_profile("test_profile", temp_dir)

        assert result is True
        assert not profile_path.exists()
