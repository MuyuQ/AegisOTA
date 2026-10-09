"""失败分类器测试。"""

from app.reporting.failure_classifier import FailureCategory, FailureClassifier


def test_failure_category_values():
    """测试失败分类枚举值。"""
    assert FailureCategory.PACKAGE_ISSUE.value == "package_issue"
    assert FailureCategory.DEVICE_ENV_ISSUE.value == "device_env_issue"
    assert FailureCategory.BOOT_FAILURE.value == "boot_failure"
    assert FailureCategory.UNKNOWN.value == "unknown"


def test_classifier_init():
    """测试分类器初始化。"""
    classifier = FailureClassifier()
    assert classifier is not None


def test_classify_precheck_failure():
    """测试分类升级前检查失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="precheck",
        error_message="Battery level too low",
        step_results={"precheck": {"battery_level": 10}},
    )

    assert result == FailureCategory.DEVICE_ENV_ISSUE


def test_classify_push_failure():
    """测试分类推送失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="package_prepare",  # 推送包的步骤
        error_message="No space left on device",
        step_results={},
    )

    # "space" keyword maps to DEVICE_ENV_ISSUE in package_prepare rules
    assert result == FailureCategory.DEVICE_ENV_ISSUE


def test_classify_reboot_failure():
    """测试分类重启失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="reboot_wait",
        error_message="Device did not boot within timeout",
        step_results={},
    )

    assert result == FailureCategory.BOOT_FAILURE


def test_classify_validation_failure():
    """测试分类验证失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="post_validate",
        error_message="Version mismatch",
        step_results={"post_validate": {"version_mismatch": True}},
    )

    assert result == FailureCategory.VALIDATION_FAILURE


def test_classify_unknown():
    """测试分类未知错误。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="unknown",
        error_message="Some unknown error",
        step_results={},
    )

    assert result == FailureCategory.UNKNOWN


def test_get_recommendation():
    """测试获取建议。"""
    classifier = FailureClassifier()

    rec = classifier.get_recommendation(FailureCategory.DEVICE_ENV_ISSUE)
    assert "检查设备状态" in rec or "设备" in rec


def test_get_next_actions():
    """测试获取下一步行动。"""
    classifier = FailureClassifier()

    actions = classifier.get_next_actions(FailureCategory.BOOT_FAILURE)
    assert len(actions) > 0
    assert any("logcat" in action.lower() or "日志" in action for action in actions)


def test_classify_apply_update_package_issue():
    """测试分类升级应用时的包问题。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="apply_update",
        error_message="Package verification failed",
        step_results={},
    )

    assert result == FailureCategory.PACKAGE_ISSUE


def test_classify_monkey_instability():
    """测试分类 Monkey 不稳定。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="post_validate",
        error_message="Monkey test found crash",
        step_results={"post_validate": {"crashed": 1}},
    )

    assert result == FailureCategory.MONKEY_INSTABILITY


def test_classify_performance_issue():
    """测试分类性能问题。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="post_validate",
        error_message="Performance metrics exceed threshold",
        step_results={"post_validate": {"perf_issue": True}},
    )

    assert result == FailureCategory.PERFORMANCE_SUSPECT
