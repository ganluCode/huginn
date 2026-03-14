"""单元测试：异常类继承关系和捕获行为"""

import pytest

from huginn.core.exceptions import (
    DuplicateItemError,
    HuginnError,
    PipelineError,
    StorageError,
    ValidationError,
)


class TestExceptionHierarchy:
    """测试异常类继承关系"""

    def test_storage_error_inherits_from_huginn_error(self):
        """StorageError 继承自 HuginnError"""
        assert issubclass(StorageError, HuginnError)

    def test_pipeline_error_inherits_from_huginn_error(self):
        """PipelineError 继承自 HuginnError"""
        assert issubclass(PipelineError, HuginnError)

    def test_validation_error_inherits_from_huginn_error(self):
        """ValidationError 继承自 HuginnError"""
        assert issubclass(ValidationError, HuginnError)

    def test_duplicate_item_error_inherits_from_pipeline_error(self):
        """DuplicateItemError 继承自 PipelineError"""
        assert issubclass(DuplicateItemError, PipelineError)
        # 间接继承自 HuginnError
        assert issubclass(DuplicateItemError, HuginnError)


class TestExceptionCanBeRaisedAndCaught:
    """测试异常可以被正常抛出和捕获"""

    def test_storage_error_can_be_raised_and_caught(self):
        """StorageError 可以被抛出并被 HuginnError 捕获"""
        with pytest.raises(HuginnError):
            raise StorageError("Storage failed")

    def test_pipeline_error_can_be_raised_and_caught(self):
        """PipelineError 可以被抛出并被 HuginnError 捕获"""
        with pytest.raises(HuginnError):
            raise PipelineError("Pipeline failed")

    def test_validation_error_can_be_raised_and_caught(self):
        """ValidationError 可以被抛出并被 HuginnError 捕获"""
        with pytest.raises(HuginnError):
            raise ValidationError("Validation failed")

    def test_duplicate_item_error_can_be_raised_and_caught(self):
        """DuplicateItemError 可以被抛出并被 PipelineError 捕获"""
        with pytest.raises(PipelineError):
            raise DuplicateItemError("Duplicate item")

    def test_duplicate_item_error_also_caught_by_huginn_error(self):
        """DuplicateItemError 也可以被 HuginnError 捕获（间接继承）"""
        with pytest.raises(HuginnError):
            raise DuplicateItemError("Duplicate item")

    def test_specific_exception_type_catching(self):
        """可以精确捕获特定异常类型"""
        # 捕获特定类型
        with pytest.raises(StorageError):
            raise StorageError("Storage failed")

        # 捕获特定类型
        with pytest.raises(ValidationError):
            raise ValidationError("Validation failed")

    def test_exception_message_preserved(self):
        """异常消息被正确保留"""
        msg = "Database connection failed"
        with pytest.raises(StorageError) as exc_info:
            raise StorageError(msg)

        assert str(exc_info.value) == msg

    def test_exception_can_be_raised_without_message(self):
        """异常可以不提供消息"""
        # 不提供消息
        with pytest.raises(HuginnError):
            raise StorageError()

        # 提供空消息
        with pytest.raises(HuginnError):
            raise ValidationError("")
