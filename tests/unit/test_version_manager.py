"""测试VersionManager"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.version_manager import VersionManager
from database.models import Submission


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_latest_submission = AsyncMock()
    db.mark_old_versions_as_not_latest = AsyncMock()
    return db


@pytest.fixture
def version_manager(mock_db):
    """创建VersionManager实例"""
    return VersionManager(mock_db)


@pytest.fixture
def mock_submission_v1():
    """创建版本1的模拟提交"""
    return Submission(
        id=1,
        student_id=1,
        assignment_id=1,
        version=1,
        is_latest=True
    )


@pytest.fixture
def mock_submission_v2():
    """创建版本2的模拟提交"""
    return Submission(
        id=2,
        student_id=1,
        assignment_id=1,
        version=2,
        is_latest=True
    )


@pytest.mark.asyncio
async def test_get_next_version_returns_2_when_version_1_exists(
    version_manager, mock_db, mock_submission_v1
):
    """测试：版本1存在时返回版本2"""
    mock_db.get_latest_submission.return_value = mock_submission_v1

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 2
    mock_db.get_latest_submission.assert_called_once_with("S001", "作业1")


@pytest.mark.asyncio
async def test_get_next_version_returns_1_when_no_submission_exists(
    version_manager, mock_db
):
    """测试：没有提交时返回版本1"""
    mock_db.get_latest_submission.return_value = None

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 1


@pytest.mark.asyncio
async def test_get_next_version_returns_3_when_version_2_exists(
    version_manager, mock_db, mock_submission_v2
):
    """测试：版本2存在时返回版本3"""
    mock_db.get_latest_submission.return_value = mock_submission_v2

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 3


@pytest.mark.asyncio
async def test_mark_old_versions(version_manager, mock_db):
    """测试：标记旧版本为非最新"""
    mock_db.mark_old_versions_as_not_latest.return_value = 1

    result = await version_manager.mark_old_versions("S001", "作业1", 2)

    assert result == 1
    mock_db.mark_old_versions_as_not_latest.assert_called_once_with(
        "S001", "作业1", 2
    )


@pytest.mark.asyncio
async def test_mark_old_versions_returns_0_when_no_old_versions(
    version_manager, mock_db
):
    """测试：没有旧版本时返回0"""
    mock_db.mark_old_versions_as_not_latest.return_value = 0

    result = await version_manager.mark_old_versions("S001", "作业1", 1)

    assert result == 0
