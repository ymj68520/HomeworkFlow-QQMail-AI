#!/usr/bin/env python3
"""Test script to verify the critical fixes for multi-assignment processor"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.multi_assignment_processor import multi_assignment_processor
from database.async_operations import async_db


async def test_idempotency_check():
    """Test 1: Verify idempotency check prevents duplicate processing"""
    print("\n" + "="*80)
    print("TEST 1: Idempotency Check")
    print("="*80)

    # Setup test data
    test_email_uid = "test_idempotency_12345"
    test_email_data = {
        'message_id': 'test_msg_123',
        'subject': 'Test Multi-Assignment',
        'sender_email': 'test@example.com',
        'sender_name': 'Test Student',
        'attachments': [],
        'email_body': 'Test body'
    }
    test_detection_result = {
        'is_complete': True,
        'is_multi_assignment': True,
        'detection_method': 'filename_analysis',
        'overall_confidence': 0.95,
        'student_id': '2021001',
        'name': 'Test Student',
        'assignments': [
            {
                'assignment_name': '作业1',
                'attachments': ['file1.docx']
            }
        ]
    }

    try:
        # First call - should create a new group
        print("\n[First Call] Processing email for the first time...")
        result1 = await multi_assignment_processor.process_multi_assignment(
            test_email_uid,
            test_email_data,
            test_detection_result
        )

        print(f"  Result: {result1['action']}")
        print(f"  Success: {result1['success']}")
        print(f"  Group ID: {result1['group_id']}")

        group_id_1 = result1.get('group_id')

        # Second call - should detect existing group and return early
        print("\n[Second Call] Processing same email again (should be idempotent)...")
        result2 = await multi_assignment_processor.process_multi_assignment(
            test_email_uid,
            test_email_data,
            test_detection_result
        )

        print(f"  Result: {result2['action']}")
        print(f"  Success: {result2['success']}")
        print(f"  Group ID: {result2['group_id']}")

        # Verify idempotency
        if result2['action'] == 'already_processed' and result2['group_id'] == group_id_1:
            print("\n✓ IDEMPOTENCY CHECK PASSED: Second call correctly detected existing group")
            return True
        else:
            print("\n✗ IDEMPOTENCY CHECK FAILED: Second call should return 'already_processed'")
            return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup test data
        try:
            if group_id_1:
                # Clean up test group and submissions
                group = await async_db.get_group_with_submissions(group_id_1)
                if group:
                    for submission in group.submissions:
                        if submission.local_path:
                            multi_assignment_processor.storage.delete_files(submission.local_path)
        except:
            pass


async def test_file_cleanup_on_rollback():
    """Test 2: Verify file cleanup on rollback"""
    print("\n" + "="*80)
    print("TEST 2: File Cleanup on Rollback")
    print("="*80)

    test_email_uid = "test_rollback_67890"
    test_email_data = {
        'message_id': 'test_msg_456',
        'subject': 'Test Rollback',
        'sender_email': 'test2@example.com',
        'sender_name': 'Test Student 2',
        'attachments': [],
        'email_body': 'Test body'
    }

    # Create a detection result that will succeed storage but fail later
    test_detection_result = {
        'is_complete': True,
        'is_multi_assignment': True,
        'detection_method': 'filename_analysis',
        'overall_confidence': 0.95,
        'student_id': '2021002',
        'name': 'Test Student 2',
        'assignments': [
            {
                'assignment_name': '作业1',
                'attachments': []  # Empty attachments will cause processing to fail
            }
        ]
    }

    try:
        print("\n[Processing] Creating group that will trigger rollback...")

        # Create group first (this will succeed)
        group = await async_db.create_submission_group(
            email_uid=test_email_uid,
            message_id=test_email_data['message_id'],
            email_subject=test_email_data['subject'],
            sender_email=test_email_data['sender_email'],
            sender_name=test_email_data['sender_name'],
            processing_mode='multi',
            detection_method='filename_analysis',
            ai_confidence=0.95,
            total_assignments=1,
            total_attachments=0,
            status='processing'
        )

        if not group:
            print("\n✗ Failed to create test group")
            return False

        print(f"  Created group {group.id}")

        # Simulate file storage (create a dummy directory)
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="test_submission_")

        # Create a submission record with the temp path
        submission = await async_db.create_submission(
            email_uid=test_email_uid,
            message_id=test_email_data['message_id'],
            email_subject=test_email_data['subject'],
            sender_email=test_email_data['sender_email'],
            sender_name=test_email_data['sender_name'],
            submission_time=None,
            student_id='2021002',
            assignment_name='作业1',
            local_path=temp_dir,
            status='pending'
        )

        if not submission:
            print("\n✗ Failed to create test submission")
            return False

        print(f"  Created submission {submission.id} with files at {temp_dir}")

        # Link submission to group
        await async_db.update_submission(
            submission_id=submission.id,
            group_id=group.id,
            group_order=1,
            is_primary=False
        )

        # Verify file exists before rollback
        from pathlib import Path
        if Path(temp_dir).exists():
            print(f"  ✓ Files exist before rollback: {temp_dir}")
        else:
            print(f"  ✗ Files don't exist before rollback: {temp_dir}")
            return False

        # Trigger rollback
        print("\n[Rollback] Triggering rollback with file cleanup...")
        await multi_assignment_processor._rollback_group(
            group.id,
            "Test rollback error"
        )

        # Verify files were cleaned up
        if not Path(temp_dir).exists():
            print(f"  ✓ Files were cleaned up successfully")
            print("\n✓ FILE CLEANUP ON ROLLBACK PASSED")
            return True
        else:
            print(f"  ✗ Files still exist after rollback: {temp_dir}")
            print("\n✗ FILE CLEANUP ON ROLLBACK FAILED")
            return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_session_management_consistency():
    """Test 3: Verify session management consistency"""
    print("\n" + "="*80)
    print("TEST 3: Session Management Consistency")
    print("="*80)

    print("\n[Verification] Checking _add_attachment_record implementation...")

    # Read the source code to verify the fix
    import inspect
    source = inspect.getsource(multi_assignment_processor._add_attachment_record)

    # Check for proper session management pattern
    has_get_async_session = 'get_async_session()' in source
    has_async_with = 'async with get_async_session()' in source
    imports_attachment = 'from database.models import get_async_session, Attachment' in source
    has_logging = 'logger.debug' in source

    print(f"  Uses get_async_session(): {has_get_async_session}")
    print(f"  Uses async with pattern: {has_async_with}")
    print(f"  Imports Attachment model: {imports_attachment}")
    print(f"  Has debug logging: {has_logging}")

    if has_get_async_session and has_async_with and imports_attachment and has_logging:
        print("\n✓ SESSION MANAGEMENT CONSISTENCY PASSED")
        print("  _add_attachment_record now follows async_db pattern consistently")
        return True
    else:
        print("\n✗ SESSION MANAGEMENT CONSISTENCY FAILED")
        print("  _add_attachment_record should use get_async_session() pattern")
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("CRITICAL FIXES VERIFICATION TESTS")
    print("="*80)
    print("\nTesting fixes for:")
    print("1. File-Database Inconsistency")
    print("2. No Idempotency Protection")
    print("3. Session Management Inconsistency")

    results = []

    # Run tests
    results.append(await test_idempotency_check())
    results.append(await test_file_cleanup_on_rollback())
    results.append(await test_session_management_consistency())

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Idempotency Check: {'PASSED ✓' if results[0] else 'FAILED ✗'}")
    print(f"File Cleanup on Rollback: {'PASSED ✓' if results[1] else 'FAILED ✗'}")
    print(f"Session Management: {'PASSED ✓' if results[2] else 'FAILED ✗'}")

    total_passed = sum(results)
    total_tests = len(results)
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if all(results):
        print("\n✓ ALL CRITICAL FIXES VERIFIED SUCCESSFULLY")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED - Please review")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
