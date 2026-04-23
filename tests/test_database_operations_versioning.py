# tests/test_database_operations_versioning.py
import pytest
from datetime import datetime
from database.operations import DatabaseOperations

def test_get_submission_by_uid_with_version():
    """Test retrieving submission with version info"""
    db_ops = DatabaseOperations()

    # Create submission with version
    submission = db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v1",
        email_subject="Test",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=2
    )

    # Retrieve and verify version
    retrieved = db_ops.get_submission_by_uid("test-v1")
    assert retrieved is not None
    assert retrieved.version == 2
    assert retrieved.is_latest == True

def test_create_multiple_versions():
    """Test creating multiple versions of the same submission"""
    db_ops = DatabaseOperations()

    # Create version 1
    submission1 = db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v2",
        email_subject="Test v1",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=1,
        is_latest=True
    )

    # Create version 2 (should update v1 to is_latest=False)
    submission2 = db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v2",
        email_subject="Test v2",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=2,
        is_latest=True
    )

    # Verify both versions exist
    all_versions = db_ops.get_all_submission_versions("2021001", "作业1")
    assert len(all_versions) == 2
    assert all_versions[0].version == 2  # Latest version first
    assert all_versions[0].is_latest == True
    assert all_versions[1].version == 1
    assert all_versions[1].is_latest == False

def test_get_latest_submission():
    """Test getting only the latest version"""
    db_ops = DatabaseOperations()

    # Create multiple versions
    db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v3",
        email_subject="Test v1",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=1,
        is_latest=True
    )

    db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v3",
        email_subject="Test v2",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=2,
        is_latest=True
    )

    db_ops.create_submission(
        student_id="2021001",
        assignment_name="作业1",
        email_uid="test-v3",
        email_subject="Test v3",
        sender_email="test@example.com",
        sender_name="张三",
        submission_time=datetime.now(),
        version=3,
        is_latest=True
    )

    # Get latest version
    latest = db_ops.get_latest_submission("2021001", "作业1")
    assert latest is not None
    assert latest.version == 3
    assert latest.is_latest == True

def test_mark_old_versions_as_not_latest():
    """Test the method that marks old versions as not latest"""
    db_ops = DatabaseOperations()

    # Create some submissions
    db_ops.create_submission(
        student_id="2021002",
        assignment_name="作业2",
        email_uid="test-v4",
        email_subject="Test v1",
        sender_email="test@example.com",
        sender_name="李四",
        submission_time=datetime.now(),
        version=1
    )

    db_ops.create_submission(
        student_id="2021002",
        assignment_name="作业2",
        email_uid="test-v4",
        email_subject="Test v2",
        sender_email="test@example.com",
        sender_name="李四",
        submission_time=datetime.now(),
        version=2
    )

    db_ops.create_submission(
        student_id="2021002",
        assignment_name="作业2",
        email_uid="test-v4",
        email_subject="Test v3",
        sender_email="test@example.com",
        sender_name="李四",
        submission_time=datetime.now(),
        version=3
    )

    # Mark version 2 as the current latest (should mark 1 and 3 as not latest)
    count = db_ops.mark_old_versions_as_not_latest("2021002", "作业2", 2)
    assert count == 2  # Should mark 2 versions as not latest

    # Verify state
    all_versions = db_ops.get_all_submission_versions("2021002", "作业2")
    version_2 = next(v for v in all_versions if v.version == 2)
    version_1 = next(v for v in all_versions if v.version == 1)
    version_3 = next(v for v in all_versions if v.version == 3)

    assert version_2.is_latest == True
    assert version_1.is_latest == False
    assert version_3.is_latest == False

    # Get latest version
    latest = db_ops.get_latest_submission("2021002", "作业2")
    assert latest is not None
    assert latest.version == 2