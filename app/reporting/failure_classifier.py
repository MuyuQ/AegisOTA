"""失败分类模块。"""

from enum import Enum
from typing import Optional, Dict, Any, List

from app.models.run import StepName


class FailureCategory(str, Enum):
    """失败分类枚举。"""

    PACKAGE_ISSUE = "package_issue"
    DEVICE_ENV_ISSUE = "device_env_issue"
    BOOT_FAILURE = "boot_failure"
    VALIDATION_FAILURE = "validation_failure"
    MONKEY_INSTABILITY = "monkey_instability"
    PERFORMANCE_SUSPECT = "performance_suspect"
    ADB_TRANSPORT_ISSUE = "adb_transport_issue"
    UNKNOWN = "unknown"


# 分类规则 - 基于步骤和关键词
CLASSIFICATION_RULES = {
    StepName.PRECHECK: {
        "battery": FailureCategory.DEVICE_ENV_ISSUE,
        "storage": FailureCategory.DEVICE_ENV_ISSUE,
        "offline": FailureCategory.ADB_TRANSPORT_ISSUE,
        "health": FailureCategory.DEVICE_ENV_ISSUE,
        "device": FailureCategory.DEVICE_ENV_ISSUE,
        "low": FailureCategory.DEVICE_ENV_ISSUE,
    },
    StepName.PACKAGE_PREPARE: {
        "space": FailureCategory.DEVICE_ENV_ISSUE,
        "permission": FailureCategory.DEVICE_ENV_ISSUE,
        "corrupted": FailureCategory.PACKAGE_ISSUE,
        "download": FailureCategory.PACKAGE_ISSUE,
        "transport": FailureCategory.ADB_TRANSPORT_ISSUE,
        "push": FailureCategory.DEVICE_ENV_ISSUE,
    },
    StepName.APPLY_UPDATE: {
        "package": FailureCategory.PACKAGE_ISSUE,
        "version": FailureCategory.PACKAGE_ISSUE,
        "apply": FailureCategory.PACKAGE_ISSUE,
        "timeout": FailureCategory.BOOT_FAILURE,
        "verification": FailureCategory.PACKAGE_ISSUE,
    },
    StepName.REBOOT_WAIT: {
        "boot": FailureCategory.BOOT_FAILURE,
        "timeout": FailureCategory.BOOT_FAILURE,
        "watchdog": FailureCategory.BOOT_FAILURE,
        "restart": FailureCategory.BOOT_FAILURE,
        "hang": FailureCategory.BOOT_FAILURE,
        "responding": FailureCategory.BOOT_FAILURE,
    },
    StepName.POST_VALIDATE: {
        "version": FailureCategory.VALIDATION_FAILURE,
        "boot": FailureCategory.BOOT_FAILURE,
        "crash": FailureCategory.MONKEY_INSTABILITY,
        "monkey": FailureCategory.MONKEY_INSTABILITY,
        "perf": FailureCategory.PERFORMANCE_SUSPECT,
        "memory": FailureCategory.PERFORMANCE_SUSPECT,
        "cpu": FailureCategory.PERFORMANCE_SUSPECT,
        "validation": FailureCategory.VALIDATION_FAILURE,
        "fingerprint": FailureCategory.VALIDATION_FAILURE,
    },
}

# 建议模板
RECOMMENDATIONS = {
    FailureCategory.PACKAGE_ISSUE: "检查升级包是否完整，验证包签名和版本信息。建议重新生成或下载升级包。",
    FailureCategory.DEVICE_ENV_ISSUE: "检查设备状态：电量、存储空间、网络连接。建议恢复设备环境后重试。",
    FailureCategory.BOOT_FAILURE: "检查设备启动日志（logcat），确认是否存在 watchdog 重启或关键进程异常。建议隔离设备进行人工排查。",
    FailureCategory.VALIDATION_FAILURE: "检查升级后版本信息，确认升级是否正确完成。可能需要重新执行升级或回滚。",
    FailureCategory.MONKEY_INSTABILITY: "Monkey 测试发现系统不稳定，检查崩溃日志和应用异常。建议进行更深入的系统稳定性测试。",
    FailureCategory.PERFORMANCE_SUSPECT: "性能指标异常，检查内存泄漏或 CPU 占用过高的问题。建议进行性能分析。",
    FailureCategory.ADB_TRANSPORT_ISSUE: "ADB 连接异常，检查 USB 连接或网络 adb 配置。建议检查设备连接状态。",
    FailureCategory.UNKNOWN: "未知错误，建议查看详细日志进行人工分析。",
}


class FailureClassifier:
    """失败分类器。"""

    def __init__(self):
        self.rules = CLASSIFICATION_RULES
        self.recommendations = RECOMMENDATIONS

    def classify(
        self,
        failed_step: str,
        error_message: str,
        step_results: Dict[str, Any],
    ) -> FailureCategory:
        """根据失败信息进行分类。"""

        if not failed_step:
            return FailureCategory.UNKNOWN

        # 转换步骤名称
        try:
            step_name = StepName(failed_step)
        except ValueError:
            step_name = None

        # 获取该步骤的规则
        if step_name and step_name in self.rules:
            step_rules = self.rules[step_name]

            # 匹配错误消息中的关键词
            error_lower = error_message.lower() if error_message else ""
            for keyword, category in step_rules.items():
                if keyword.lower() in error_lower:
                    return category

            # 检查步骤结果中的特定标志
            step_result = step_results.get(failed_step, {})
            for keyword, category in step_rules.items():
                if step_result.get(keyword) or step_result.get(f"{keyword}_issue"):
                    return category

        # 默认返回 UNKNOWN
        return FailureCategory.UNKNOWN

    def classify_from_context(
        self,
        failed_step: StepName,
        error: str,
        context_data: Dict[str, Any],
    ) -> FailureCategory:
        """从执行上下文数据进行分类。"""
        return self.classify(
            failed_step.value,
            error,
            context_data.get("step_results", {}),
        )

    def get_recommendation(self, category: FailureCategory) -> str:
        """获取处理建议。"""
        return self.recommendations.get(category, self.recommendations[FailureCategory.UNKNOWN])

    def get_next_actions(self, category: FailureCategory) -> List[str]:
        """获取下一步行动建议。"""
        actions: List[str] = []

        if category == FailureCategory.PACKAGE_ISSUE:
            actions = [
                "验证升级包完整性",
                "检查包签名",
                "重新下载或生成升级包",
            ]
        elif category == FailureCategory.DEVICE_ENV_ISSUE:
            actions = [
                "检查设备电量",
                "清理存储空间",
                "重启设备后重试",
            ]
        elif category == FailureCategory.BOOT_FAILURE:
            actions = [
                "收集 logcat 日志",
                "检查 watchdog 重启记录",
                "隔离设备进行人工排查",
            ]
        elif category == FailureCategory.VALIDATION_FAILURE:
            actions = [
                "确认升级版本",
                "检查升级日志",
                "考虑执行回滚",
            ]
        elif category == FailureCategory.MONKEY_INSTABILITY:
            actions = [
                "分析崩溃日志",
                "定位问题应用",
                "增加 Monkey 测试时长",
            ]
        elif category == FailureCategory.ADB_TRANSPORT_ISSUE:
            actions = [
                "检查 USB 连接",
                "重启 adb server",
                "检查网络 adb 配置",
            ]
        else:
            actions = [
                "查看详细日志",
                "人工分析失败原因",
            ]

        return actions