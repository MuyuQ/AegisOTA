"""诊断执行服务。

orchestrate the entire diagnosis flow from log parsing to result generation.
"""

import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.diagnosis.engine import DiagnosticResultData, RuleEngine
from app.diagnosis.loader import DiagnosticRule, RuleLoader
from app.diagnosis.similar import SimilarCaseService
from app.models.diagnostic import (
    DiagnosticResult,
    RuleHit,
    SimilarCaseIndex,
)
from app.models.diagnostic import (
    NormalizedEvent as NormalizedEventDB,
)
from app.models.enums import ResultStatus, RunStatus, Stage
from app.models.event import NormalizedEvent as NormalizedEventPydantic
from app.models.run import RunSession
from app.parsers.logcat_parser import LogcatParser
from app.parsers.monkey_parser import MonkeyParser
from app.parsers.normalizer import EventNormalizer
from app.parsers.recovery_parser import RecoveryParser
from app.parsers.update_engine_parser import UpdateEngineParser

logger = logging.getLogger(__name__)


class DiagnosisService:
    """诊断执行服务。

    执行完整的诊断流程：
    1. 加载日志文件
    2. 解析各类型日志
    3. 标准化事件
    4. 保存事件到数据库
    5. 加载诊断规则
    6. 执行规则匹配
    7. 计算置信度
    8. 查找相似案例
    9. 保存诊断结果
    10. 索引案例用于相似搜索
    """

    def __init__(self, db: Session):
        """初始化诊断服务。

        Args:
            db: 数据库会话
        """
        self.db = db
        self.settings = get_settings()

        # 初始化解析器
        self.recovery_parser = RecoveryParser()
        self.update_engine_parser = UpdateEngineParser()
        self.logcat_parser = LogcatParser()
        self.monkey_parser = MonkeyParser()

        # 初始化标准化器
        self.normalizer = EventNormalizer()

        # 初始化规则加载器和引擎
        self.rule_loader = RuleLoader(db_session=db)
        self.rule_engine = RuleEngine()

        # 初始化相似案例服务
        self.similar_service = SimilarCaseService(db)

    def run_diagnosis(self, run_id: int) -> Optional[DiagnosticResult]:
        """执行诊断流程。

        Args:
            run_id: 任务ID

        Returns:
            诊断结果，如果诊断失败返回 None
        """
        # 获取任务会话
        run_session = self._get_run_session(run_id)
        if not run_session:
            logger.warning(f"Run session {run_id} not found")
            return None

        # 检查任务是否需要诊断
        if not self._needs_diagnosis(run_session):
            logger.info(f"Run {run_id} does not need diagnosis (status: {run_session.status})")
            return None

        # 获取设备序列号
        device_serial = self._get_device_serial(run_session)
        if not device_serial:
            logger.warning(f"Run {run_id} has no device serial")
            return None

        # 清理旧的诊断数据
        self._clear_old_diagnosis(run_id)

        # 加载日志文件
        log_files = self._load_log_files(run_id)
        if not log_files:
            logger.warning(f"No log files found for run {run_id}")
            return None

        # 解析日志
        raw_events = self._parse_logs(log_files, run_id)
        if not raw_events:
            logger.warning(f"No events parsed from logs for run {run_id}")
            return None

        # 标准化事件
        normalized_events = self._normalize_events(run_id, raw_events)
        if not normalized_events:
            logger.warning(f"No normalized events for run {run_id}")
            return None

        # 保存事件到数据库
        db_events = self._save_events(run_id, normalized_events)

        # 加载诊断规则
        rules = self.rule_loader.load_all_rules()
        if not rules:
            logger.warning("No diagnostic rules loaded")
            # 创建证据不足结果
            return self._create_insufficient_evidence_result(run_id, device_serial, db_events)

        # 执行规则匹配
        result_data, matched_rules = self.rule_engine.evaluate(run_id, normalized_events)

        # 查找相似案例
        similar_cases = self._find_similar_cases(result_data, device_serial, run_id)

        # 保存诊断结果
        diagnostic_result = self._save_diagnostic_result(
            run_id, device_serial, result_data, similar_cases
        )

        # 保存规则命中记录
        self._save_rule_hits(run_id, diagnostic_result.id, matched_rules)

        # 索引案例用于相似搜索
        self._index_case(run_id, device_serial, result_data, diagnostic_result.get_key_evidence())

        # 提交所有变更
        self.db.commit()

        logger.info(
            f"Diagnosis completed for run {run_id}: "
            f"category={result_data.category}, root_cause={result_data.root_cause}, "
            f"confidence={result_data.confidence:.2f}"
        )

        return diagnostic_result

    def _get_run_session(self, run_id: int) -> Optional[RunSession]:
        """获取任务会话。

        Args:
            run_id: 任务ID

        Returns:
            任务会话，如果不存在返回 None
        """
        stmt = select(RunSession).where(RunSession.id == run_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def _needs_diagnosis(self, run_session: RunSession) -> bool:
        """检查任务是否需要诊断。

        只有失败或被中止的任务需要诊断。

        Args:
            run_session: 任务会话

        Returns:
            是否需要诊断
        """
        # 终态任务才进行诊断
        if not run_session.is_terminal_state():
            return False

        # 失败或中止的任务需要诊断
        return run_session.status in (
            RunStatus.FAILED,
            RunStatus.ABORTED,
            RunStatus.PREEMPTED,
        )

    def _get_device_serial(self, run_session: RunSession) -> Optional[str]:
        """获取设备序列号。

        Args:
            run_session: 任务会话

        Returns:
            设备序列号，如果没有关联设备返回 None
        """
        if run_session.device:
            return run_session.device.serial
        return None

    def _load_log_files(self, run_id: int) -> dict[str, str]:
        """加载日志文件内容。

        从 artifacts/{run_id}/logs/ 目录加载各类日志文件。

        Args:
            run_id: 任务ID

        Returns:
            日志文件内容字典，键为日志类型，值为文件内容
        """
        log_dir = self.settings.ARTIFACTS_DIR / str(run_id) / "logs"

        if not log_dir.exists():
            logger.debug(f"Log directory {log_dir} does not exist")
            return {}

        log_files = {}

        # 定义日志文件映射
        file_mapping = {
            "recovery_log": ["recovery.log", "recovery.txt"],
            "last_install": ["last_install.txt", "last_install"],
            "update_engine_log": ["update_engine.log", "update_engine.txt"],
            "logcat": ["logcat.txt", "logcat.log"],
            "monkey_output": ["monkey.txt", "monkey.log", "monkey_output.txt"],
        }

        # 加载每种类型的日志文件
        for log_type, file_names in file_mapping.items():
            for file_name in file_names:
                file_path = log_dir / file_name
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if content.strip():
                            log_files[log_type] = content
                            logger.debug(f"Loaded {log_type} from {file_path}")
                            break
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")

        return log_files

    def _parse_logs(self, log_files: dict[str, str], run_id: int) -> list[dict]:
        """解析所有日志类型。

        Args:
            log_files: 日志文件内容字典
            run_id: 任务ID

        Returns:
            解析后的原始事件列表
        """
        all_events = []

        # 解析 recovery 日志
        if "recovery_log" in log_files:
            events = self.recovery_parser.parse(log_files["recovery_log"], str(run_id))
            all_events.extend(events)
            logger.debug(f"Recovery parser found {len(events)} events")

        # 解析 last_install（可能在 recovery_log 中已处理）
        if "last_install" in log_files:
            events = self.recovery_parser.parse_last_install_file(
                log_files["last_install"], str(run_id)
            )
            all_events.extend(events)
            logger.debug(f"Last install parser found {len(events)} events")

        # 解析 update_engine 日志
        if "update_engine_log" in log_files:
            events = self.update_engine_parser.parse(log_files["update_engine_log"], str(run_id))
            all_events.extend(events)
            logger.debug(f"Update engine parser found {len(events)} events")

        # 解析 logcat 日志
        if "logcat" in log_files:
            events = self.logcat_parser.parse(log_files["logcat"], str(run_id))
            all_events.extend(events)
            logger.debug(f"Logcat parser found {len(events)} events")

        # 解析 monkey 日志
        if "monkey_output" in log_files:
            events = self.monkey_parser.parse(log_files["monkey_output"], str(run_id))
            all_events.extend(events)
            logger.debug(f"Monkey parser found {len(events)} events")

        return all_events

    def _normalize_events(
        self, run_id: int, raw_events: list[dict]
    ) -> list[NormalizedEventPydantic]:
        """标准化事件。

        Args:
            run_id: 任务ID
            raw_events: 原始事件列表

        Returns:
            标准化后的 Pydantic 事件列表
        """
        normalized_events = []

        for raw_event in raw_events:
            source_type = raw_event.get("source_type", "recovery_log")
            try:
                events = self.normalizer.normalize(run_id, source_type, [raw_event])
                normalized_events.extend(events)
            except Exception as e:
                logger.warning(f"Failed to normalize event: {e}")

        return normalized_events

    def _save_events(
        self, run_id: int, events: list[NormalizedEventPydantic]
    ) -> list[NormalizedEventDB]:
        """保存标准化事件到数据库。

        Args:
            run_id: 任务ID
            events: Pydantic 标准化事件列表

        Returns:
            数据库事件列表
        """
        db_events = []

        for event in events:
            db_event = NormalizedEventDB(
                run_id=run_id,
                source_type=event.source_type.value
                if hasattr(event.source_type, "value")
                else str(event.source_type),
                stage=event.stage.value if hasattr(event.stage, "value") else str(event.stage),
                event_type=event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type),
                severity=event.severity.value
                if hasattr(event.severity, "value")
                else str(event.severity),
                normalized_code=event.normalized_code,
                raw_line=event.raw_line,
                line_no=event.line_no,
                timestamp=event.timestamp,
            )

            # 设置 kv_payload
            if event.kv_payload:
                db_event.set_kv_payload(event.kv_payload)

            self.db.add(db_event)
            db_events.append(db_event)

        # 刷新以获取 ID，但不提交（让主流程控制提交）
        self.db.flush()

        return db_events

    def _clear_old_diagnosis(self, run_id: int) -> None:
        """清理旧的诊断数据。

        Args:
            run_id: 任务ID
        """
        # 删除旧的规则命中记录
        self.db.execute(delete(RuleHit).where(RuleHit.run_id == run_id))

        # 删除旧的诊断结果
        self.db.execute(delete(DiagnosticResult).where(DiagnosticResult.run_id == run_id))

        # 删除旧的标准化事件
        self.db.execute(delete(NormalizedEventDB).where(NormalizedEventDB.run_id == run_id))

        # 删除旧的相似案例索引
        self.db.execute(delete(SimilarCaseIndex).where(SimilarCaseIndex.run_id == run_id))

        # 提交删除
        self.db.commit()

    def _find_similar_cases(
        self,
        result_data: DiagnosticResultData,
        device_serial: str,
        run_id: int,
    ) -> list[dict]:
        """查找相似案例。

        Args:
            result_data: 诊断结果数据
            device_serial: 设备序列号
            run_id: 当前任务ID（排除）

        Returns:
            相似案例列表
        """
        # 生成证据哈希
        key_evidence = [{"normalized_code": code} for code in result_data.key_evidence[:3]]
        evidence_hash = self.similar_service._generate_evidence_hash(key_evidence)

        # 查找相似案例
        similar_cases = self.similar_service.find_similar(
            category=result_data.category,
            root_cause=result_data.root_cause,
            evidence_hash=evidence_hash,
            limit=self.settings.SIMILAR_CASE_LIMIT,
            exclude_run_id=run_id,
        )

        return similar_cases

    def _save_diagnostic_result(
        self,
        run_id: int,
        device_serial: str,
        result_data: DiagnosticResultData,
        similar_cases: list[dict],
    ) -> DiagnosticResult:
        """保存诊断结果到数据库。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            result_data: 诊断结果数据
            similar_cases: 相似案例列表

        Returns:
            数据库诊断结果
        """
        diagnostic_result = DiagnosticResult(
            run_id=run_id,
            device_serial=device_serial,
            stage=result_data.stage.value
            if hasattr(result_data.stage, "value")
            else str(result_data.stage),
            category=result_data.category,
            root_cause=result_data.root_cause,
            confidence=result_data.confidence,
            result_status=result_data.result_status.value
            if hasattr(result_data.result_status, "value")
            else str(result_data.result_status),
            next_action=result_data.next_action,
        )

        # 设置关键证据
        key_evidence_list = [{"raw_line": line} for line in result_data.key_evidence]
        diagnostic_result.set_key_evidence(key_evidence_list)

        # 设置相似案例
        diagnostic_result.set_similar_cases(similar_cases)

        self.db.add(diagnostic_result)
        self.db.flush()

        return diagnostic_result

    def _save_rule_hits(
        self, run_id: int, result_id: int, matched_rules: list[DiagnosticRule]
    ) -> None:
        """保存规则命中记录。

        Args:
            run_id: 任务ID
            result_id: 诊断结果ID
            matched_rules: 匹配的规则列表
        """
        for rule in matched_rules:
            rule_hit = RuleHit(
                run_id=run_id,
                result_id=result_id,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                priority=rule.priority,
                base_confidence=rule.base_confidence,
            )

            # 设置匹配的事件码
            matched_codes = list(set(rule.match_all + rule.match_any))
            rule_hit.set_matched_codes(matched_codes)

            self.db.add(rule_hit)

    def _index_case(
        self,
        run_id: int,
        device_serial: str,
        result_data: DiagnosticResultData,
        key_evidence: list[dict],
    ) -> None:
        """索引案例用于相似搜索。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            result_data: 诊断结果数据
            key_evidence: 关键证据列表
        """
        self.similar_service.index_case(
            run_id=run_id,
            device_serial=device_serial,
            category=result_data.category,
            root_cause=result_data.root_cause,
            key_evidence=key_evidence,
        )

    def _create_insufficient_evidence_result(
        self,
        run_id: int,
        device_serial: str,
        db_events: list[NormalizedEventDB],
    ) -> DiagnosticResult:
        """创建证据不足的诊断结果。

        Args:
            run_id: 任务ID
            device_serial: 设备序列号
            db_events: 数据库事件列表

        Returns:
            证据不足的诊断结果
        """
        # 确定阶段
        stages = [e.stage for e in db_events]
        stage = self._determine_latest_stage(stages)

        # 提取关键证据
        key_evidence = [e.raw_line for e in db_events if e.raw_line][:5]

        diagnostic_result = DiagnosticResult(
            run_id=run_id,
            device_serial=device_serial,
            stage=stage,
            category="unknown",
            root_cause="insufficient_evidence",
            confidence=0.0,
            result_status=ResultStatus.INSUFFICIENT_EVIDENCE.value,
            next_action="collect more diagnostic evidence",
        )

        key_evidence_list = [{"raw_line": line} for line in key_evidence]
        diagnostic_result.set_key_evidence(key_evidence_list)

        self.db.add(diagnostic_result)
        self.db.commit()

        return diagnostic_result

    def _determine_latest_stage(self, stages: list[str]) -> str:
        """确定最晚的阶段。

        Args:
            stages: 阶段列表

        Returns:
            最晚的阶段
        """
        stage_order = [
            Stage.PRECHECK,
            Stage.PACKAGE_PREPARE,
            Stage.APPLY_UPDATE,
            Stage.REBOOT_WAIT,
            Stage.POST_REBOOT,
            Stage.POST_VALIDATE,
        ]

        for stage in reversed(stage_order):
            if stage.value in stages:
                return stage.value

        return Stage.PRECHECK.value

    def get_diagnosis_for_run(self, run_id: int) -> Optional[DiagnosticResult]:
        """获取任务的诊断结果。

        Args:
            run_id: 任务ID

        Returns:
            诊断结果，如果没有返回 None
        """
        stmt = select(DiagnosticResult).where(DiagnosticResult.run_id == run_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_events_for_run(self, run_id: int) -> list[NormalizedEventDB]:
        """获取任务的标准化事件。

        Args:
            run_id: 任务ID

        Returns:
            标准化事件列表
        """
        stmt = (
            select(NormalizedEventDB)
            .where(NormalizedEventDB.run_id == run_id)
            .order_by(NormalizedEventDB.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_rule_hits_for_run(self, run_id: int) -> list[RuleHit]:
        """获取任务的规则命中记录。

        Args:
            run_id: 任务ID

        Returns:
            规则命中记录列表
        """
        stmt = select(RuleHit).where(RuleHit.run_id == run_id).order_by(RuleHit.priority.desc())
        return list(self.db.execute(stmt).scalars().all())
