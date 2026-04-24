"""测试SubmissionDeduplicator"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from database.models import Submission, Student, Assignment


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_latest_submission = AsyncMock()
    return db


@pytest.fixture
def submission_deduplicator(mock_db):
    """创建SubmissionDeduplicator实例"""
    return SubmissionDeduplicator(mock_db)


@pytest.fixture
def mock_latest_submission():
    """创建模拟的最新提交记录"""
    student = Student(id=1, student_id="S001", name="张三")
    assignment = Assignment(id=1, name="作业1")
    return Submission(
        id=1,
        student_id=1,
        assignment_id=1,
        student=student,
        assignment=assignment,
        version=1,
        is_latest=True
    )


@pytest.mark.asyncio
async def test_check_returns_true_when_submission_exists(
    submission_deduplicator, mock_db, mock_latest_submission
):
    """测试：提交存在时返回True"""
    mock_db.get_latest_submission.return_value = mock_latest_submission

    result = await submission_deduplicator.check("S001", "作业1")

    assert result is True
    mock_db.get_latest_submission.assert_called_once_with("S001", "作业1")


@pytest.mark.asyncio
async def test_check_returns_false_when_submission_not_exists(
    submission_deduplicator, mock_db
):
    """测试：提交不存在时返回False"""
    mock_db.get_latest_submission.return_value = None

    result = await submission_deduplicator.check("S001", "作业1")

    assert result is False


@pytest.mark.asyncio
async def test_get_latest_returns_submission(
    submission_deduplicator, mock_db, mock_latest_submission
):
    """测试：获取最新提交记录"""
    mock_db.get_latest_submission.return_value = mock_latest_submission

    result = await submission_deduplicator.get_latest("S001", "作业1")

    assert result == mock_latest_submission
    assert result.version == 1


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_not_found(
    submission_deduplicator, mock_db
):
    """测试：提交不存在时返回None"""
    mock_db.get_latest_submission.return_value = None

    result = await submission_deduplicator.get_latest("S001", "作业1")

    assert result is None
