"""性能检查器测试。"""

from app.executors.mock_executor import MockADBExecutor
from app.validators.perf_check import PerfChecker, PerfCheckResult


def test_perf_checker_init():
    """测试性能检查器初始化。"""
    checker = PerfChecker()
    assert checker is not None


def test_perf_checker_collect_metrics():
    """测试收集性能指标。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell cat /proc/meminfo",
        stdout=(
            "MemTotal:       8192000 kB\nMemFree:         4000000 kB\nMemAvailable:    5000000 kB\n"
        ),
    )
    executor.set_response("shell dumpsys cpuinfo", stdout="CPU usage: 5%\n")
    executor.set_response("shell getprop", stdout="[sys.boot_time]: [30000]\n")

    checker = PerfChecker(executor=executor)
    metrics = checker.collect_metrics("ABC123")

    assert "memory" in metrics
    assert "cpu" in metrics


def test_perf_checker_get_boot_time():
    """测试获取启动时间。"""
    executor = MockADBExecutor()
    executor.set_response("shell getprop", stdout="[sys.boot_time]: [30000]\n")

    checker = PerfChecker(executor=executor)
    boot_time = checker.get_boot_time("ABC123")

    assert boot_time >= 0


def test_perf_check_result_creation():
    """测试性能检查结果创建。"""
    result = PerfCheckResult(
        passed=True,
        memory_usage_percent=50.0,
        cpu_usage_percent=10.0,
        boot_time_ms=30000,
        message="性能指标正常",
        details={},
    )

    assert result.passed is True
    assert result.memory_usage_percent == 50.0


def test_perf_check_result_to_dict():
    """测试性能检查结果转换。"""
    result = PerfCheckResult(
        passed=True,
        memory_usage_percent=50.0,
        cpu_usage_percent=10.0,
        boot_time_ms=30000,
        message="性能指标正常",
        details={"memory": {"total_kb": 8192000}},
    )

    data = result.to_dict()
    assert data["passed"] is True
    assert data["memory_usage_percent"] == 50.0
    assert data["boot_time_ms"] == 30000
    assert "memory" in data["details"]


def test_perf_checker_check_passed():
    """测试性能检查通过。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell cat /proc/meminfo",
        stdout="MemTotal:       8192000 kB\nMemFree:         4000000 kB\n",
    )
    executor.set_response("shell dumpsys cpuinfo", stdout="CPU usage: 10%\n")
    executor.set_response("shell getprop", stdout="[sys.boot_time]: [30000]\n")

    checker = PerfChecker(executor=executor)
    result = checker.check("ABC123")

    assert result.passed is True
    assert "通过" in result.message


def test_perf_checker_check_memory_high():
    """测试内存使用过高。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell cat /proc/meminfo",
        stdout="MemTotal:       8192000 kB\nMemFree:          800000 kB\n",  # ~90% used
    )
    executor.set_response("shell dumpsys cpuinfo", stdout="CPU usage: 10%\n")
    executor.set_response("shell getprop", stdout="[sys.boot_time]: [30000]\n")

    checker = PerfChecker(executor=executor, memory_threshold=80.0)
    result = checker.check("ABC123")

    assert result.passed is False
    assert "内存" in result.message


def test_perf_checker_parse_memory():
    """测试解析内存信息。"""
    checker = PerfChecker()

    output = """MemTotal:       8192000 kB
MemFree:         4000000 kB
MemAvailable:    5000000 kB
Buffers:          100000 kB
"""

    mem_info = checker._parse_memory(output)
    assert mem_info["total_kb"] == 8192000
    assert mem_info["free_kb"] == 4000000
    assert mem_info["available_kb"] == 5000000


def test_perf_checker_parse_cpu():
    """测试解析 CPU 信息。"""
    checker = PerfChecker()

    # Note: Our regex looks for "CPU usage: X%" format
    # Let's test with matching format
    output2 = "CPU usage: 5%\n"
    cpu_info2 = checker._parse_cpu(output2)
    assert cpu_info2.get("usage_percent", 0.0) == 5.0
