"""简单的内存速率限制器。"""

import time
from collections import defaultdict


class RateLimiter:
    """基于滑动窗口的简单内存速率限制器。"""

    def __init__(self):
        # {identifier: [timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(
        self,
        identifier: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """检查请求是否允许。

        Args:
            identifier: 请求标识符（通常是 IP 地址）
            max_requests: 时间窗口内允许的最大请求数
            window_seconds: 时间窗口大小（秒）

        Returns:
            如果允许请求返回 True，否则返回 False
        """
        now = time.time()
        cutoff = now - window_seconds

        # 清理过期记录
        self._requests[identifier] = [ts for ts in self._requests[identifier] if ts > cutoff]

        # 检查是否超过限制
        if len(self._requests[identifier]) >= max_requests:
            return False

        # 记录本次请求
        self._requests[identifier].append(now)
        return True

    def cleanup(self, older_than_seconds: int = 3600):
        """清理长时间未使用的标识符记录。"""
        cutoff = time.time() - older_than_seconds
        keys_to_remove = []
        for identifier, timestamps in self._requests.items():
            if not timestamps or max(timestamps) < cutoff:
                keys_to_remove.append(identifier)
        for key in keys_to_remove:
            del self._requests[key]


# 全局速率限制器实例
rate_limiter = RateLimiter()
