"""相似案例召回服务。

从历史案例中检索相似案例，用于辅助诊断决策。
"""

import hashlib
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.diagnostic import DiagnosticResult, SimilarCaseIndex


class SimilarCaseService:
    """相似案例召回服务。

    提供案例索引和相似度检索功能，帮助诊断引擎找到历史相似案例。
    """

    def __init__(self, session: Session):
        """初始化服务。

        Args:
            session: 数据库会话
        """
        self.session = session
        self.settings = get_settings()

    def index_case(
        self,
        run_id: int,
        device_serial: str,
        category: str,
        root_cause: str,
        key_evidence: Optional[list[dict]] = None,
    ) -> None:
        """将诊断结果索引到相似案例库。

        Args:
            run_id: 任务 ID
            device_serial: 设备序列号
            category: 故障分类
            root_cause: 根因标识
            key_evidence: 关键证据列表
        """
        # 生成证据哈希
        evidence_hash = self._generate_evidence_hash(key_evidence)

        # 检查是否已存在
        stmt = select(SimilarCaseIndex).where(SimilarCaseIndex.run_id == run_id)
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            existing.category = category
            existing.root_cause = root_cause
            existing.key_evidence_hash = evidence_hash
        else:
            index = SimilarCaseIndex(
                run_id=run_id,
                device_serial=device_serial,
                category=category,
                root_cause=root_cause,
                key_evidence_hash=evidence_hash,
            )
            self.session.add(index)

        # 不在此处提交，让调用者控制事务边界

    def _generate_evidence_hash(self, key_evidence: Optional[list[dict]]) -> Optional[str]:
        """生成证据哈希。

        从关键证据中提取前几条日志行，生成 MD5 哈希用于相似度匹配。

        Args:
            key_evidence: 关键证据列表

        Returns:
            哈希字符串，如果没有证据则返回 None
        """
        if not key_evidence:
            return None

        # 取前3条证据的normalized_code组合
        codes = []
        for evidence in key_evidence[:3]:
            code = evidence.get("normalized_code", "")
            if code:
                codes.append(code)

        if not codes:
            return None

        # 组合并哈希
        combined = "|".join(codes)
        return hashlib.md5(combined.encode()).hexdigest()

    def find_similar(
        self,
        category: str,
        root_cause: str,
        evidence_hash: Optional[str] = None,
        limit: int = 3,
        exclude_run_id: Optional[int] = None,
    ) -> list[dict]:
        """从历史案例中召回相似案例。

        Args:
            category: 故障分类
            root_cause: 根因标识
            evidence_hash: 证据哈希（可选）
            limit: 返回数量限制
            exclude_run_id: 排除的任务 ID（通常是当前任务）

        Returns:
            相似案例列表，包含 run_id、device_serial、category、root_cause、
            similarity、created_at 字段
        """
        # 查询历史案例索引
        stmt = select(SimilarCaseIndex).where(
            SimilarCaseIndex.category == category,
            SimilarCaseIndex.root_cause == root_cause,
        )

        if exclude_run_id:
            stmt = stmt.where(SimilarCaseIndex.run_id != exclude_run_id)

        candidates = self.session.execute(stmt).scalars().all()

        # 计算相似度
        scored_cases = []
        for candidate in candidates:
            score = self._calculate_similarity(
                root_cause=root_cause,
                evidence_hash=evidence_hash,
                candidate=candidate,
            )
            # 只保留高于阈值的案例
            if score >= self.settings.SIMILARITY_THRESHOLD:
                scored_cases.append((candidate, score))

        # 排序并取 top N
        scored_cases.sort(key=lambda x: x[1], reverse=True)
        top_cases = scored_cases[:limit]

        # 转换为字典列表
        similar_cases = []
        for candidate, score in top_cases:
            similar_cases.append(
                {
                    "run_id": candidate.run_id,
                    "device_serial": candidate.device_serial,
                    "category": candidate.category,
                    "root_cause": candidate.root_cause,
                    "similarity": score,
                    "created_at": candidate.created_at,
                }
            )

        return similar_cases

    def _calculate_similarity(
        self,
        root_cause: str,
        evidence_hash: Optional[str],
        candidate: SimilarCaseIndex,
    ) -> float:
        """计算相似度。

        使用多种方法综合评估：
        1. 根因完全匹配（基础分）
        2. 证据哈希相似度

        Args:
            root_cause: 当前根因
            evidence_hash: 当前证据哈希
            candidate: 历史案例索引

        Returns:
            相似度分数 (0.0-1.0)
        """
        score = 0.0

        # 获取权重配置
        root_cause_weight = self.settings.SIMILARITY_ROOT_CAUSE_WEIGHT
        category_weight = self.settings.SIMILARITY_CATEGORY_WEIGHT
        evidence_weight = self.settings.SIMILARITY_EVIDENCE_WEIGHT

        # 根因完全匹配
        if root_cause == candidate.root_cause:
            score += root_cause_weight

        # 分类匹配（已在查询中过滤，这里额外加分）
        score += category_weight

        # 证据哈希相似度
        if evidence_hash and candidate.key_evidence_hash:
            hash_similarity = self._calculate_hash_similarity(
                evidence_hash, candidate.key_evidence_hash
            )
            score += hash_similarity * evidence_weight

        return min(1.0, score)

    def _calculate_hash_similarity(self, query_hash: str, case_hash: str) -> float:
        """计算哈希字符串相似度。

        使用 RapidFuzz 的 ratio 方法计算字符串相似度。

        Args:
            query_hash: 查询哈希
            case_hash: 案例哈希

        Returns:
            相似度分数 (0.0-1.0)
        """
        if not query_hash or not case_hash:
            return 0.0
        return fuzz.ratio(query_hash, case_hash) / 100.0

    def rebuild_index(self) -> int:
        """重建相似案例索引。

        从现有的 DiagnosticResult 记录重建整个索引。

        Returns:
            索引数量
        """
        # 清空现有索引
        self.session.execute(select(SimilarCaseIndex).where(True))
        for index in self.session.execute(select(SimilarCaseIndex)).scalars().all():
            self.session.delete(index)

        # 获取所有诊断结果
        results = self.session.execute(select(DiagnosticResult)).scalars().all()

        count = 0
        for result in results:
            key_evidence = result.get_key_evidence()
            self.index_case(
                run_id=result.run_id,
                device_serial=result.device_serial,
                category=result.category,
                root_cause=result.root_cause,
                key_evidence=key_evidence,
            )
            count += 1

        # 提交所有索引变更
        self.session.commit()
        return count

    def get_index_stats(self) -> dict:
        """获取索引统计信息。

        Returns:
            统计信息字典，包含总数、分类分布等
        """
        # 总数
        total = self.session.execute(select(SimilarCaseIndex).where(True)).scalars().all()
        total_count = len(total)

        # 按分类统计
        categories = {}
        for index in total:
            cat = index.category
            categories[cat] = categories.get(cat, 0) + 1

        # 按根因统计
        root_causes = {}
        for index in total:
            rc = index.root_cause
            root_causes[rc] = root_causes.get(rc, 0) + 1

        return {
            "total_count": total_count,
            "categories": categories,
            "root_causes": root_causes,
        }
