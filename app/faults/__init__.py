"""异常注入模块。"""

from app.faults.base import FaultPlugin, FaultResult
from app.faults.download_interrupted import DownloadInterruptedFault
from app.faults.low_battery import LowBatteryFault
from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault
from app.faults.package_corrupted import PackageCorruptedFault
from app.faults.performance_regression import PerformanceRegressionFault
from app.faults.post_boot_watchdog_failure import PostBootWatchdogFailureFault
from app.faults.reboot_interrupted import RebootInterruptedFault
from app.faults.storage_pressure import StoragePressureFault

__all__ = [
    "FaultPlugin",
    "FaultResult",
    "StoragePressureFault",
    "RebootInterruptedFault",
    "MonkeyAfterUpgradeFault",
    "DownloadInterruptedFault",
    "PackageCorruptedFault",
    "LowBatteryFault",
    "PostBootWatchdogFailureFault",
    "PerformanceRegressionFault",
]
