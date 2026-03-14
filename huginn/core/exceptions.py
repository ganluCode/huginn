"""Huginn 自定义异常类

定义了项目中使用的异常层次结构：
- HuginnError: 所有自定义异常的基类
- StorageError: 存储层异常（数据库、文件系统等）
- PipelineError: 数据管道异常（清洗、去重等）
- ValidationError: 数据验证异常
- DuplicateItemError: 重复数据异常（继承自 PipelineError）
"""


class HuginnError(Exception):
    """Huginn 项目基础异常类

    所有自定义异常的基类，用于统一捕获项目特定的异常。
    """

    pass


class StorageError(HuginnError):
    """存储层异常

    当数据库操作、文件读写等存储相关操作失败时抛出。
    """

    pass


class PipelineError(HuginnError):
    """数据管道异常

    当数据处理管道（清洗、去重、转换等）操作失败时抛出。
    """

    pass


class ValidationError(HuginnError):
    """数据验证异常

    当数据不符合预期格式或业务规则时抛出。
    """

    pass


class DuplicateItemError(PipelineError):
    """重复数据异常

    当检测到重复数据时抛出。继承自 PipelineError，
    因为重复检测通常在数据管道中完成。
    """

    pass
