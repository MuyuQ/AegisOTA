"""设备日志导出服务。"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.executors.adb_executor import ADBExecutor
from app.models.artifact import Artifact

logger = logging.getLogger(__name__)


class LogExportService:
    """设备日志导出服务。

    从 Android 设备导出日志文件到任务产物目录。
    """

    def __init__(self, db: Session, adb_executor: Optional[ADBExecutor] = None):
        """初始化日志导出服务。

        Args:
            db: 数据库会话
            adb_executor: ADB 执行器，可选，默认创建新实例
        """
        self.db = db
        self.adb = adb_executor or ADBExecutor()

    def export_from_device(self, run_id: int, device_serial: str) -> List[str]:
        """从设备导出日志到任务产物目录。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号

        Returns:
            导出的文件名列表（仅包含成功导出的文件）
        """
        artifact_dir = Path(f"artifacts/{run_id}/logs")
        artifact_dir.mkdir(parents=True, exist_ok=True)

        exported_files: List[str] = []

        # 导出 recovery 日志
        exported_files.extend(self._export_recovery_logs(run_id, device_serial, artifact_dir))

        # 导出 update_engine 日志
        exported_files.extend(self._export_update_engine_log(run_id, device_serial, artifact_dir))

        # 导出 logcat
        exported_files.extend(self._export_logcat(run_id, device_serial, artifact_dir))

        # 导出设备信息
        exported_files.extend(self._export_device_info(run_id, device_serial, artifact_dir))

        # 保存产物记录到数据库
        self._create_artifact_records(run_id, artifact_dir, exported_files)

        return exported_files

    def _export_recovery_logs(
        self,
        run_id: int,
        device_serial: str,
        artifact_dir: Path,
    ) -> List[str]:
        """导出 recovery 日志。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            artifact_dir: 产物目录

        Returns:
            成功导出的文件名列表
        """
        exported: List[str] = []

        recovery_sources = [
            ("/cache/recovery/log", "recovery.log"),
            ("/cache/recovery/last_install", "last_install.txt"),
        ]

        for src_path, dst_name in recovery_sources:
            try:
                dst_path = artifact_dir / dst_name
                result = self.adb.pull(src_path, str(dst_path), device=device_serial)

                if result.success and dst_path.exists():
                    exported.append(dst_name)
                    logger.info(f"成功导出 {dst_name} (run_id={run_id}, device={device_serial})")
                else:
                    logger.warning(
                        f"无法导出 {src_path}: {result.stderr or '文件不存在'} "
                        f"(run_id={run_id}, device={device_serial})"
                    )
            except Exception as e:
                logger.warning(
                    f"导出 {src_path} 时发生错误: {e} "
                    f"(run_id={run_id}, device={device_serial})"
                )

        return exported

    def _export_update_engine_log(
        self,
        run_id: int,
        device_serial: str,
        artifact_dir: Path,
    ) -> List[str]:
        """导出 update_engine 日志。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            artifact_dir: 产物目录

        Returns:
            成功导出的文件名列表
        """
        exported: List[str] = []

        try:
            # update_engine_log 是一个目录，拉取后会创建子目录
            # 我们将其拉取到临时位置，然后重命名
            src_path = "/data/misc/update_engine_log/"
            temp_dir = artifact_dir / "update_engine_temp"

            result = self.adb.pull(src_path, str(temp_dir), device=device_serial)

            if result.success and temp_dir.exists():
                # 查找目录中的日志文件
                log_files = list(temp_dir.glob("*"))
                if log_files:
                    # 合并内容到单个文件（如果有多文件）
                    dst_path = artifact_dir / "update_engine.log"
                    with open(dst_path, "w", encoding="utf-8") as f:
                        for log_file in log_files:
                            if log_file.is_file():
                                try:
                                    content = log_file.read_text(encoding="utf-8", errors="replace")
                                    f.write(f"=== {log_file.name} ===\n")
                                    f.write(content)
                                    f.write("\n")
                                except Exception as read_error:
                                    logger.warning(
                                        f"读取 {log_file} 失败: {read_error}"
                                    )

                    exported.append("update_engine.log")
                    logger.info(
                        f"成功导出 update_engine.log (run_id={run_id}, device={device_serial})"
                    )

                    # 清理临时目录
                    self._cleanup_temp_dir(temp_dir)
                else:
                    logger.warning(
                        f"update_engine_log 目录为空 (run_id={run_id}, device={device_serial})"
                    )
                    self._cleanup_temp_dir(temp_dir)
            else:
                logger.warning(
                    f"无法导出 {src_path}: {result.stderr or '目录不存在'} "
                    f"(run_id={run_id}, device={device_serial})"
                )
        except Exception as e:
            logger.warning(
                f"导出 update_engine_log 时发生错误: {e} "
                f"(run_id={run_id}, device={device_serial})"
            )

        return exported

    def _export_logcat(
        self,
        run_id: int,
        device_serial: str,
        artifact_dir: Path,
    ) -> List[str]:
        """导出 logcat 日志。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            artifact_dir: 产物目录

        Returns:
            成功导出的文件名列表
        """
        exported: List[str] = []

        try:
            dst_path = artifact_dir / "logcat.txt"
            result = self.adb.logcat(device=device_serial, output_path=str(dst_path))

            if result.success and dst_path.exists():
                exported.append("logcat.txt")
                logger.info(
                    f"成功导出 logcat.txt (run_id={run_id}, device={device_serial})"
                )
            else:
                logger.warning(
                    f"无法导出 logcat: {result.stderr or '无日志内容'} "
                    f"(run_id={run_id}, device={device_serial})"
                )
        except Exception as e:
            logger.warning(
                f"导出 logcat 时发生错误: {e} "
                f"(run_id={run_id}, device={device_serial})"
            )

        return exported

    def _export_device_info(
        self,
        run_id: int,
        device_serial: str,
        artifact_dir: Path,
    ) -> List[str]:
        """导出设备信息。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            artifact_dir: 产物目录

        Returns:
            成功导出的文件名列表
        """
        exported: List[str] = []

        try:
            # 使用 get_device_snapshot 获取完整设备信息
            snapshot = self.adb.get_device_snapshot(device=device_serial)

            if snapshot:
                dst_path = artifact_dir / "device_info.json"
                with open(dst_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2, ensure_ascii=False)

                exported.append("device_info.json")
                logger.info(
                    f"成功导出 device_info.json (run_id={run_id}, device={device_serial})"
                )
            else:
                # 尝试仅使用 getprop
                props = self.adb.getprop(device=device_serial)
                if props:
                    dst_path = artifact_dir / "device_info.txt"
                    with open(dst_path, "w", encoding="utf-8") as f:
                        for key, value in props.items():
                            f.write(f"[{key}]: [{value}]\n")

                    exported.append("device_info.txt")
                    logger.info(
                        f"成功导出 device_info.txt (run_id={run_id}, device={device_serial})"
                    )
                else:
                    logger.warning(
                        f"无法获取设备信息 (run_id={run_id}, device={device_serial})"
                    )
        except Exception as e:
            logger.warning(
                f"导出设备信息时发生错误: {e} "
                f"(run_id={run_id}, device={device_serial})"
            )

        return exported

    def _cleanup_temp_dir(self, temp_dir: Path) -> None:
        """清理临时目录。

        Args:
            temp_dir: 临时目录路径
        """
        try:
            if temp_dir.exists():
                for file in temp_dir.glob("*"):
                    if file.is_file():
                        file.unlink()
                temp_dir.rmdir()
        except Exception as e:
            logger.warning(f"清理临时目录 {temp_dir} 失败: {e}")

    def _create_artifact_records(
        self,
        run_id: int,
        artifact_dir: Path,
        exported_files: List[str],
    ) -> None:
        """为导出的文件创建产物记录。

        Args:
            run_id: 任务ID
            artifact_dir: 产物目录
            exported_files: 成功导出的文件名列表
        """
        for filename in exported_files:
            file_path = artifact_dir / filename

            # 计算文件大小
            file_size = None
            if file_path.exists():
                try:
                    file_size = file_path.stat().st_size
                except Exception:
                    pass

            # 确定产物类型
            artifact_type = self._determine_artifact_type(filename)

            # 创建产物记录
            artifact = Artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                file_path=str(file_path),
                file_size=file_size,
                description=f"从设备导出的 {filename}",
            )
            self.db.add(artifact)

        try:
            self.db.commit()
            logger.info(f"已创建 {len(exported_files)} 个产物记录 (run_id={run_id})")
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建产物记录失败: {e} (run_id={run_id})")

    def _determine_artifact_type(self, filename: str) -> str:
        """根据文件名确定产物类型。

        Args:
            filename: 文件名

        Returns:
            产物类型字符串
        """
        type_mapping = {
            "recovery.log": "log",
            "last_install.txt": "log",
            "update_engine.log": "log",
            "logcat.txt": "logcat",
            "device_info.json": "log",
            "device_info.txt": "log",
        }

        return type_mapping.get(filename, "log")