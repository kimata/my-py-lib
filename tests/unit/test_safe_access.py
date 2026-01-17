#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.safe_access モジュールのユニットテスト
"""

from __future__ import annotations


class TestNullObject:
    """_NullObject クラスのテスト"""

    def test_null_is_singleton(self):
        """NULL はシングルトンである"""
        from my_lib.safe_access import NULL, _NullObject

        null1 = _NullObject()
        null2 = _NullObject()
        assert null1 is null2
        assert null1 is NULL

    def test_null_is_falsy(self):
        """NULL は False を返す"""
        from my_lib.safe_access import NULL

        assert bool(NULL) is False

    def test_null_getattr_returns_self(self):
        """NULL への属性アクセスは自身を返す"""
        from my_lib.safe_access import NULL

        result = NULL.some_attribute
        assert result is NULL

    def test_null_chained_access(self):
        """NULL へのチェーンアクセスも NULL を返す"""
        from my_lib.safe_access import NULL

        result = NULL.a.b.c.d.e
        assert result is NULL

    def test_null_repr(self):
        """NULL の repr は "NULL" """
        from my_lib.safe_access import NULL

        assert repr(NULL) == "NULL"


class TestSafeAccess:
    """SafeAccess クラスのテスト"""

    def test_access_existing_attribute(self):
        """存在する属性にアクセス"""
        from my_lib.safe_access import safe

        class Obj:
            name = "test"

        result = safe(Obj()).name.value()
        assert result == "test"

    def test_access_missing_attribute(self):
        """存在しない属性にアクセスすると None を返す"""
        from my_lib.safe_access import safe

        class Obj:
            name = "test"

        result = safe(Obj()).missing.value()
        assert result is None

    def test_access_with_default(self):
        """デフォルト値を指定"""
        from my_lib.safe_access import safe

        class Obj:
            name = "test"

        result = safe(Obj()).missing.value(default="default")
        assert result == "default"

    def test_chained_access(self):
        """チェーンアクセス"""
        from my_lib.safe_access import safe

        class Level3:
            data = "deep"

        class Level2:
            level3 = Level3()

        class Level1:
            level2 = Level2()

        result = safe(Level1()).level2.level3.data.value()
        assert result == "deep"

    def test_chained_access_with_missing_intermediate(self):
        """途中で存在しない属性がある場合"""
        from my_lib.safe_access import safe

        class Obj:
            name = "test"

        result = safe(Obj()).missing.nested.deep.value()
        assert result is None

    def test_none_object(self):
        """None オブジェクトへのアクセス"""
        from my_lib.safe_access import safe

        result = safe(None).anything.value()
        assert result is None

    def test_none_attribute(self):
        """None 値の属性へのアクセス"""
        from my_lib.safe_access import safe

        class Obj:
            attr = None

        result = safe(Obj()).attr.nested.value()
        assert result is None

    def test_bool_with_valid_value(self):
        """有効な値の場合は True"""
        from my_lib.safe_access import safe

        class Obj:
            name = "test"

        safe_obj = safe(Obj()).name
        assert bool(safe_obj) is True

    def test_bool_with_null(self):
        """NULL の場合は False"""
        from my_lib.safe_access import safe

        class Obj:
            pass

        safe_obj = safe(Obj()).missing
        assert bool(safe_obj) is False

    def test_bool_with_none(self):
        """None の場合は False"""
        from my_lib.safe_access import safe

        safe_obj = safe(None)
        assert bool(safe_obj) is False


class TestSafeAccessPracticalUseCases:
    """SafeAccess の実用的なユースケースのテスト"""

    def test_pyVmomi_like_structure(self):
        """pyVmomi ライクな構造へのアクセス"""
        from my_lib.safe_access import safe

        class CpuInfo:
            numCpuThreads = 16
            numCpuCores = 8

        class Hardware:
            cpuInfo = CpuInfo()
            memorySize = 68719476736  # 64GB

        class HostSystem:
            hardware = Hardware()

        host = HostSystem()
        threads = safe(host).hardware.cpuInfo.numCpuThreads.value()
        cores = safe(host).hardware.cpuInfo.numCpuCores.value()

        assert threads == 16
        assert cores == 8

    def test_pyVmomi_like_structure_with_missing(self):
        """pyVmomi ライクな構造で途中が None の場合"""
        from my_lib.safe_access import safe

        class HostSystem:
            hardware = None

        host = HostSystem()
        threads = safe(host).hardware.cpuInfo.numCpuThreads.value()

        assert threads is None

    def test_pyVmomi_like_structure_with_default(self):
        """pyVmomi ライクな構造でデフォルト値を使用"""
        from my_lib.safe_access import safe

        class HostSystem:
            hardware = None

        host = HostSystem()
        threads = safe(host).hardware.cpuInfo.numCpuThreads.value(default=0)

        assert threads == 0

    def test_extract_cpu_info_pattern(self):
        """_extract_cpu_info パターンのテスト"""
        from my_lib.safe_access import safe

        class CpuInfo:
            numCpuThreads = 16
            numCpuCores = 8

        class Hardware:
            cpuInfo = CpuInfo()

        class HostSystem:
            hardware = Hardware()

        host = HostSystem()

        # SafeAccess を使用したパターン
        safe_host = safe(host)
        cpu_info = safe_host.hardware.cpuInfo
        cpu_threads = cpu_info.numCpuThreads.value()
        cpu_cores = cpu_info.numCpuCores.value()

        assert cpu_threads == 16
        assert cpu_cores == 8

    def test_extract_memory_total_pattern(self):
        """_extract_memory_total パターンのテスト"""
        from my_lib.safe_access import safe

        class Hardware:
            memorySize = 68719476736

        class HostSystem:
            hardware = Hardware()

        host = HostSystem()
        memory = safe(host).hardware.memorySize.value()

        assert memory == 68719476736

    def test_extract_os_version_pattern(self):
        """_extract_os_version パターンのテスト"""
        from my_lib.safe_access import safe

        class Product:
            fullName = "VMware ESXi 8.0.0 build-12345"

        class Config:
            product = Product()

        class HostSystem:
            config = Config()

        host = HostSystem()
        os_version = safe(host).config.product.fullName.value()

        assert os_version == "VMware ESXi 8.0.0 build-12345"


class TestSafeFactoryFunction:
    """safe ファクトリ関数のテスト"""

    def test_safe_creates_safe_access(self):
        """safe() は SafeAccess インスタンスを返す"""
        from my_lib.safe_access import SafeAccess, safe

        class Obj:
            pass

        result = safe(Obj())
        assert isinstance(result, SafeAccess)

    def test_safe_with_none(self):
        """safe(None) も動作する"""
        from my_lib.safe_access import SafeAccess, safe

        result = safe(None)
        assert isinstance(result, SafeAccess)
        assert result.value() is None


class TestSafeAccessEdgeCases:
    """SafeAccess のエッジケーステスト"""

    def test_access_private_attribute(self):
        """プライベート属性へのアクセス"""
        from my_lib.safe_access import safe

        class Obj:
            _private = "secret"

        result = safe(Obj())._private.value()
        assert result == "secret"

    def test_access_special_method_attribute(self):
        """特殊なメソッド属性へのアクセス"""
        from my_lib.safe_access import safe

        class Obj:
            class_name = "TestClass"

        # 通常の属性アクセスは動作する
        result = safe(Obj()).class_name.value()
        assert result == "TestClass"

        # NOTE: __class__ などのダンダー属性は Python の特殊な動作により
        # SafeAccess の __getattr__ を経由せず、SafeAccess 自身の属性を返す。
        # これは Python の仕様であり、SafeAccess は通常の属性に対してのみ使用する。

    def test_value_returns_actual_object(self):
        """value() は実際のオブジェクトを返す"""
        from my_lib.safe_access import safe

        class Inner:
            data = (1, 2, 3)  # immutable tuple

        class Obj:
            inner = Inner()

        inner = safe(Obj()).inner.value()
        assert isinstance(inner, Inner)
        assert inner.data == (1, 2, 3)

    def test_falsy_but_valid_values(self):
        """Falsy だが有効な値"""
        from my_lib.safe_access import safe

        class Obj:
            zero = 0
            empty_string = ""
            false = False

        obj = Obj()

        # 0 は有効な値
        assert safe(obj).zero.value() == 0
        assert safe(obj).zero.value(default=100) == 0

        # "" は有効な値
        assert safe(obj).empty_string.value() == ""
        assert safe(obj).empty_string.value(default="default") == ""

        # False は有効な値
        assert safe(obj).false.value() is False
        assert safe(obj).false.value(default=True) is False

    def test_empty_list_and_dict(self):
        """空のリストと辞書"""
        from my_lib.safe_access import safe

        class Obj:
            def __init__(self) -> None:
                self.empty_list: list = []
                self.empty_dict: dict = {}

        obj = Obj()

        assert safe(obj).empty_list.value() == []
        assert safe(obj).empty_dict.value() == {}
