"""产物模型测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.artifact import Artifact, ArtifactType
from app.models.device import Device
from app.models.run import (
    RunSession,
    RunStatus,
    RunStep,
    StepName,
    StepStatus,
    UpgradePlan,
    UpgradeType,
)


@pytest.fixture
def db_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_device(db_session):
    """创建示例设备。"""
    device = Device(serial="TEST001", brand="Google", model="Pixel 7")
    db_session.add(device)
    db_session.commit()
    return device


@pytest.fixture
def sample_plan(db_session):
    """创建示例升级计划。"""
    plan = UpgradePlan(name="测试升级计划", upgrade_type=UpgradeType.FULL)
    db_session.add(plan)
    db_session.commit()
    return plan


@pytest.fixture
def sample_run(db_session, sample_device, sample_plan):
    """创建示例运行会话。"""
    run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
    db_session.add(run)
    db_session.commit()
    return run


@pytest.fixture
def sample_step(db_session, sample_run):
    """创建示例步骤。"""
    step = RunStep(run_id=sample_run.id, step_name=StepName.PRECHECK, step_order=1)
    db_session.add(step)
    db_session.commit()
    return step


class TestArtifactType:
    """ArtifactType 枚举测试。"""

    def test_type_values(self):
        """测试枚举值正确。"""
        assert ArtifactType.LOGCAT == "logcat"
        assert ArtifactType.STDOUT == "stdout"
        assert ArtifactType.STDERR == "stderr"
        assert ArtifactType.SCREENSHOT == "screenshot"
        assert ArtifactType.MONKEY_RESULT == "monkey_result"
        assert ArtifactType.PERF_DATA == "perf_data"
        assert ArtifactType.REPORT == "report"
        assert ArtifactType.TIMELINE == "timeline"

    def test_type_count(self):
        """测试枚举值数量。"""
        assert len(ArtifactType) == 8

    def test_type_is_string_enum(self):
        """测试枚举是字符串枚举。"""
        assert isinstance(ArtifactType.LOGCAT.value, str)


class TestArtifactCreation:
    """Artifact 创建测试。"""

    def test_create_artifact_minimal(self, db_session, sample_run):
        """测试创建最小产物。"""
        artifact = Artifact(
            run_id=sample_run.id,
            artifact_type=ArtifactType.LOGCAT.value,
            file_path="/artifacts/run_1/logcat.log",
        )
        db_session.add(artifact)
        db_session.commit()

        assert artifact.id is not None
        assert artifact.run_id == sample_run.id
        assert artifact.artifact_type == ArtifactType.LOGCAT.value
        assert artifact.file_path == "/artifacts/run_1/logcat.log"
        assert artifact.created_at is not None

    def test_create_artifact_full(self, db_session, sample_run, sample_step):
        """测试创建完整产物。"""
        artifact = Artifact(
            run_id=sample_run.id,
            step_id=sample_step.id,
            artifact_type=ArtifactType.SCREENSHOT.value,
            file_path="/artifacts/run_1/screenshot.png",
            file_size=2048,
            mime_type="image/png",
            description="升级后截图",
        )
        artifact.set_metadata({
            "width": 1080,
            "height": 2400,
            "taken_at": "2024-01-15T10:30:00Z",
        })
        db_session.add(artifact)
        db_session.commit()

        assert artifact.id is not None
        assert artifact.step_id == sample_step.id
        assert artifact.file_size == 2048
        assert artifact.mime_type == "image/png"
        assert artifact.description == "升级后截图"
        assert artifact.get_metadata() == {
            "width": 1080,
            "height": 2400,
            "taken_at": "2024-01-15T10:30:00Z",
        }

    def test_artifact_metadata_methods(self, db_session, sample_run):
        """测试元数据方法。"""
        artifact = Artifact(
            run_id=sample_run.id,
            artifact_type=ArtifactType.MONKEY_RESULT.value,
            file_path="/artifacts/run_1/monkey_result.json",
        )

        # 测试空元数据
        assert artifact.get_metadata() == {}

        # 测试设置元数据
        metadata = {
            "total_events": 10000,
            "crashes": 2,
            "anrs": 1,
            "duration_seconds": 120,
        }
        artifact.set_metadata(metadata)
        db_session.add(artifact)
        db_session.commit()

        assert artifact.get_metadata() == metadata

    def test_artifact_metadata_empty(self, db_session, sample_run):
        """测试空元数据。"""
        artifact = Artifact(
            run_id=sample_run.id,
            artifact_type=ArtifactType.STDOUT.value,
            file_path="/artifacts/run_1/stdout.log",
        )
        artifact.set_metadata({})
        db_session.add(artifact)
        db_session.commit()

        assert artifact.artifact_metadata is None
        assert artifact.get_metadata() == {}


class TestArtifactRelationships:
    """Artifact 关系测试。"""

    def test_artifact_run_relationship(self, db_session, sample_run):
        """测试产物与会话的关联。"""
        artifact = Artifact(
            run_id=sample_run.id,
            artifact_type=ArtifactType.LOGCAT.value,
            file_path="/artifacts/run_1/logcat.log",
        )
        db_session.add(artifact)
        db_session.commit()

        db_session.refresh(artifact)
        assert artifact.run_session is not None
        assert artifact.run_session.id == sample_run.id

    def test_artifact_step_relationship(self, db_session, sample_run, sample_step):
        """测试产物与步骤的关联。"""
        artifact = Artifact(
            run_id=sample_run.id,
            step_id=sample_step.id,
            artifact_type=ArtifactType.STDOUT.value,
            file_path="/artifacts/run_1/step_1_stdout.log",
        )
        db_session.add(artifact)
        db_session.commit()

        db_session.refresh(artifact)
        assert artifact.step is not None
        assert artifact.step.id == sample_step.id
        assert artifact.step.step_name == StepName.PRECHECK

    def test_run_artifacts_relationship(self, db_session, sample_run):
        """测试会话的产物列表。"""
        artifacts = [
            Artifact(
                run_id=sample_run.id,
                artifact_type=ArtifactType.LOGCAT.value,
                file_path="/artifacts/run_1/logcat.log",
            ),
            Artifact(
                run_id=sample_run.id,
                artifact_type=ArtifactType.STDERR.value,
                file_path="/artifacts/run_1/stderr.log",
            ),
            Artifact(
                run_id=sample_run.id,
                artifact_type=ArtifactType.SCREENSHOT.value,
                file_path="/artifacts/run_1/screenshot.png",
            ),
        ]
        db_session.add_all(artifacts)
        db_session.commit()

        db_session.refresh(sample_run)
        assert len(sample_run.artifacts) == 3


class TestCascadeDelete:
    """级联删除测试。"""

    def test_run_delete_cascades_artifacts(self, db_session, sample_device, sample_plan):
        """测试删除会话级联删除产物。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        artifact = Artifact(
            run_id=run.id,
            artifact_type=ArtifactType.REPORT.value,
            file_path="/artifacts/run_1/report.md",
        )
        db_session.add(artifact)
        db_session.commit()

        artifact_id = artifact.id

        # 删除会话
        db_session.delete(run)
        db_session.commit()

        # 产物应该被级联删除
        from sqlalchemy.orm import object_session
        assert object_session(artifact) is None


class TestAllArtifactTypes:
    """所有产物类型创建测试。"""

    def test_create_all_artifact_types(self, db_session, sample_run, sample_step):
        """测试创建所有产物类型。"""
        artifact_configs = [
            (ArtifactType.LOGCAT, "/logs/logcat.log", {"device_serial": "TEST001"}),
            (ArtifactType.STDOUT, "/logs/stdout.log", {"size_mb": 5}),
            (ArtifactType.STDERR, "/logs/stderr.log", {"error_count": 3}),
            (ArtifactType.SCREENSHOT, "/img/screenshot.png", {"resolution": "1080x2400"}),
            (ArtifactType.MONKEY_RESULT, "/results/monkey.json", {"events": 10000}),
            (ArtifactType.PERF_DATA, "/data/perf.csv", {"metrics": ["cpu", "mem"]}),
            (ArtifactType.REPORT, "/reports/report.md", {"format": "markdown"}),
            (ArtifactType.TIMELINE, "/data/timeline.json", {"events": 50}),
        ]

        artifacts = []
        for artifact_type, path, metadata in artifact_configs:
            artifact = Artifact(
                run_id=sample_run.id,
                step_id=sample_step.id,
                artifact_type=artifact_type.value,
                file_path=path,
            )
            artifact.set_metadata(metadata)
            artifacts.append(artifact)

        db_session.add_all(artifacts)
        db_session.commit()

        assert len(artifacts) == 8
        for artifact in artifacts:
            assert artifact.id is not None
            assert artifact.get_metadata() != {}