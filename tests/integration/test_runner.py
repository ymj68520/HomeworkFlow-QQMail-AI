#!/usr/bin/env python3
"""
Simple test runner for versioning functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from database.operations import DatabaseOperations

def test_versioning():
    """Test all versioning functionality"""
    db_ops = DatabaseOperations()

    try:
        print("Testing basic version creation...")
        # Test basic version creation
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
        assert submission is not None
        assert submission.version == 2
        assert submission.is_latest == True
        print("✓ Basic version creation passed")

        print("Testing version retrieval...")
        retrieved = db_ops.get_submission_by_uid("test-v1")
        assert retrieved is not None
        assert retrieved.version == 2
        assert retrieved.is_latest == True
        print("✓ Version retrieval passed")

        print("Testing multiple versions...")
        # Create multiple versions
        db_ops.create_submission(
            student_id="2021001",
            assignment_name="作业1",
            email_uid="test-v2",
            email_subject="Test v1",
            sender_email="test@example.com",
            sender_name="张三",
            submission_time=datetime.now(),
            version=1
        )

        db_ops.create_submission(
            student_id="2021001",
            assignment_name="作业1",
            email_uid="test-v2",
            email_subject="Test v2",
            sender_email="test@example.com",
            sender_name="张三",
            submission_time=datetime.now(),
            version=2
        )

        all_versions = db_ops.get_all_submission_versions("2021001", "作业1")
        assert len(all_versions) == 2
        assert all_versions[0].version == 2
        assert all_versions[1].version == 1
        print("✓ Multiple versions passed")

        print("Testing latest version retrieval...")
        latest = db_ops.get_latest_submission("2021001", "作业1")
        assert latest is not None
        assert latest.version == 2
        assert latest.is_latest == True
        print("✓ Latest version retrieval passed")

        print("Testing old versions marking...")
        count = db_ops.mark_old_versions_as_not_latest("2021001", "作业1", 1)
        assert count == 1
        print("✓ Old versions marking passed")

        print("All tests passed! ✓")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db_ops.close()

if __name__ == "__main__":
    success = test_versioning()
    sys.exit(0 if success else 1)