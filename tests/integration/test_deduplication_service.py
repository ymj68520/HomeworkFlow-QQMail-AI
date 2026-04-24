"""测试DeduplicationService集成"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.deduplication.service import DeduplicationService
from core.deduplication.models import DeduplicationResult
from database.models import Submission, Student, Assignment


@pytest.fixture
def mock_components():
    """模拟所有组件"""
    mock_db = Mock()
    mock_email_dedup = AsyncMock()
    mock_submission_dedup = AsyncMock()
    mock_version_mgr = AsyncMock()
    mock_cache_mgr = AsyncMock()

    return {
        'db': mock_db,
        'email_dedup': mock_email_dedup,
        'submission_dedup': mock_submission_dedup,
        'version_mgr': mock_version_mgr,
        'cache_mgr': mock_cache_mgr
    }


@pytest.fixture
def service(mock_components):
    """创建DeduplicationService实例"""
    with patch('core.deduplication.service.EmailDeduplicator', return_value=mock_components['email_dedup']), \
         patch('core.deduplication.service.SubmissionDeduplicator', return_value=mock_components['submission_dedup']), \
         patch('core.deduplication.service.VersionManager', return_value=mock_components['version_mgr']), \
         patch('core.deduplication.service.CacheManager', return_value=mock_components['cache_mgr']):
        return DeduplicationService(mock_components['db'])


@pytest.mark.asyncio
async def test_check_email_duplicate(service, mock_components):
    """测试：检测到邮件重复"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_components['email_dedup'].check.return_value = True
    mock_components['email_dedup'].get_existing.return_value = mock_submission

    result = await service.check_email("existing_uid")

    assert result.is_duplicate is True
    assert result.duplicate_type == 'email'
    assert result.action == 'skip'
    assert result.submission == mock_submission


@pytest.mark.asyncio
async def test_check_submission_duplicate(service, mock_components):
    """测试：检测到提交重复"""
    mock_submission = Submission(
        id=1,
        student=Student(id=1, student_id="S001", name="张三"),
        assignment=Assignment(id=1, name="作业1"),
        version=1
    )
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = True
    mock_components['submission_dedup'].get_latest.return_value = mock_submission
    mock_components['version_mgr'].get_next_version.return_value = 2

    result = await service.check_submission("S001", "作业1")

    assert result.is_duplicate is True
    assert result.duplicate_type == 'submission'
    assert result.version == 2


@pytest.mark.asyncio
async def test_check_new_submission(service, mock_components):
    """测试：新提交，无重复"""
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = False
    mock_components['cache_mgr'].get.return_value = None

    result = await service.check_all(
        email_uid="new_uid",
        student_id="S001",
        assignment_name="作业1"
    )

    assert result.is_duplicate is False
    assert result.action == 'new'


@pytest.mark.asyncio
async def test_check_with_cache_hit(service, mock_components):
    """测试：缓存命中"""
    cached_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1'
    }
    mock_components['cache_mgr'].get.return_value = cached_data
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = False

    result = await service.check_all(
        email_uid="cached_uid",
        student_id="S001",
        assignment_name="作业1"
    )

    assert result.cached_data == cached_data
