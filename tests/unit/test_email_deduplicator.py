"""测试EmailDeduplicator"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.email_deduplicator import EmailDeduplicator
from database.models import Submission


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_submission_by_uid = AsyncMock()
    return db


@pytest.fixture
def email_deduplicator(mock_db):
    """创建EmailDeduplicator实例"""
    return EmailDeduplicator(mock_db)


@pytest.mark.asyncio
async def test_check_returns_true_when_email_exists(email_deduplicator, mock_db):
    """测试：邮件存在时返回True"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_db.get_submission_by_uid.return_value = mock_submission

    result = await email_deduplicator.check("existing_uid")

    assert result is True
    mock_db.get_submission_by_uid.assert_called_once_with("existing_uid")


@pytest.mark.asyncio
async def test_check_returns_false_when_email_not_exists(email_deduplicator, mock_db):
    """测试：邮件不存在时返回False"""
    mock_db.get_submission_by_uid.return_value = None

    result = await email_deduplicator.check("new_uid")

    assert result is False
    mock_db.get_submission_by_uid.assert_called_once_with("new_uid")


@pytest.mark.asyncio
async def test_get_existing_returns_submission(email_deduplicator, mock_db):
    """测试：获取已存在的邮件记录"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_db.get_submission_by_uid.return_value = mock_submission

    result = await email_deduplicator.get_existing("existing_uid")

    assert result == mock_submission
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_existing_returns_none_when_not_found(email_deduplicator, mock_db):
    """测试：邮件不存在时返回None"""
    mock_db.get_submission_by_uid.return_value = None

    result = await email_deduplicator.get_existing("new_uid")

    assert result is None
