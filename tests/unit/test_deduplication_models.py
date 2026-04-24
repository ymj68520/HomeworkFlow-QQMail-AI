"""测试去重数据模型"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from core.deduplication.models import (
    DeduplicationResult,
    EmailDuplicateError,
    SubmissionDuplicateError,
    FileOperationError,
    TransactionError
)
from database.models import Submission


def test_deduplication_result_new_submission():
    """测试新提交结果"""
    result = DeduplicationResult(
        is_duplicate=False,
        action='new'
    )

    assert result.is_duplicate is False
    assert result.action == 'new'
    assert result.duplicate_type is None
    assert result.version is None


def test_deduplication_result_email_duplicate():
    """测试邮件重复结果"""
    mock_submission = Submission(id=1)
    result = DeduplicationResult(
        is_duplicate=True,
        duplicate_type='email',
        action='skip',
        submission=mock_submission
    )

    assert result.is_duplicate is True
    assert result.duplicate_type == 'email'
    assert result.action == 'skip'
    assert result.submission is not None


def test_deduplication_result_submission_duplicate():
    """测试提交重复结果"""
    result = DeduplicationResult(
        is_duplicate=True,
        duplicate_type='submission',
        action='update_version',
        version=2
    )

    assert result.is_duplicate is True
    assert result.duplicate_type == 'submission'
    assert result.action == 'update_version'
    assert result.version == 2


def test_email_duplicate_error():
    """测试邮件重复异常"""
    mock_submission = Submission(id=1, email_uid="test_uid")
    error = EmailDuplicateError("test_uid", mock_submission)

    assert str(error) == "Email test_uid already processed"
    assert error.email_uid == "test_uid"
    assert error.existing_submission == mock_submission


def test_submission_duplicate_error():
    """测试提交重复异常"""
    error = SubmissionDuplicateError("S001", "作业1", 2)

    assert "S001" in str(error)
    assert "作业1" in str(error)
    assert "version: 2" in str(error)
    assert error.student_id == "S001"
    assert error.assignment_name == "作业1"
    assert error.latest_version == 2


def test_file_operation_error():
    """测试文件操作异常"""
    from core.deduplication.models import FileOperationError, DeduplicationError
    error = FileOperationError("Failed to create folder")
    assert isinstance(error, DeduplicationError)
    assert "Failed to create folder" in str(error)


def test_transaction_error():
    """测试事务异常"""
    from core.deduplication.models import TransactionError, DeduplicationError
    error = TransactionError("Transaction rolled back")
    assert isinstance(error, DeduplicationError)
    assert "Transaction rolled back" in str(error)
