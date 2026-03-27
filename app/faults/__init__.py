"""异常注入模块。"""

from app.faults.base import FaultPlugin, FaultResult
from app.faults.storage_pressure import StoragePressureFault
from app.faults.reboot_interrupted import RebootInterruptedFault
from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault
from app.faults.download_interrupted import DownloadInterruptedFault

__all__ = [
    "FaultPlugin",
    "FaultResult",
    "StoragePressureFault",
    "RebootInterruptedFault",
    "MonkeyAfterUpgradeFault",
    "DownloadInterruptedFault",
]