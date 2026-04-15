"""AegisOTA 自定义异常类。"""


class AegisOTAError(Exception):
    """AegisOTA 基础异常类。"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DeviceNotFoundError(AegisOTAError):
    """设备未找到异常。"""

    def __init__(self, message: str = "Device not found"):
        super().__init__(message, status_code=404)


class PoolNotFoundError(AegisOTAError):
    """设备池未找到异常。"""

    def __init__(self, message: str = "Pool not found"):
        super().__init__(message, status_code=404)


class RunNotFoundError(AegisOTAError):
    """任务未找到异常。"""

    def __init__(self, message: str = "Run not found"):
        super().__init__(message, status_code=404)


class ValidationError(AegisOTAError):
    """验证错误异常。"""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)
