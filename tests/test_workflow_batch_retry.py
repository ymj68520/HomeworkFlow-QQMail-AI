# tests/test_workflow_batch_retry.py
"""Integration tests for workflow with batch retry"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.workflow import workflow

@pytest.mark.asyncio
async def test_workflow_with_batch_retry():
    """Test full workflow with emails that have Unknown fields"""

    # Mock parser
    mock_parser = MagicMock()
    mock_parser.connect.return_value = True
    mock_parser.disconnect.return_value = None
    mock_parser.uid_exists.return_value = True

    # Mock 3 emails with different missing fields
    mock_parser.get_new_emails.return_value = [
        {
            'uid': '1001',
            'subject': '提交作业',  # Missing: student_id, name, assignment
            'from': 'Unknown <unknown@test.com>',
            'sender_email': 'unknown@test.com',
            'sender_name': 'Unknown',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        },
        {
            'uid': '1002',
            'subject': '2021001-作业1',  # Missing: name
            'from': 'Student1 <student1@test.com>',
            'sender_email': 'student1@test.com',
            'sender_name': 'Student1',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        },
        {
            'uid': '1003',
            'subject': '张三-作业1',  # Missing: student_id
            'from': '张三 <zhangsan@test.com>',
            'sender_email': 'zhangsan@test.com',
            'sender_name': '张三',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        }
    ]

    # Mock parse_email
    def mock_parse_email(uid):
        emails = {
            '1001': {
                'uid': '1001',
                'subject': '提交作业',
                'from': 'Unknown <unknown@test.com>',
                'sender_email': 'unknown@test.com',
                'sender_name': 'Unknown',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            },
            '1002': {
                'uid': '1002',
                'subject': '2021001-作业1',
                'from': 'Student1 <student1@test.com>',
                'sender_email': 'student1@test.com',
                'sender_name': 'Student1',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            },
            '1003': {
                'uid': '1003',
                'subject': '张三-作业1',
                'from': '张三 <zhangsan@test.com>',
                'sender_email': 'zhangsan@test.com',
                'sender_name': '张三',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            }
        }
        return emails.get(uid)

    mock_parser.parse_email = mock_parse_email

    # Mock AI extraction - individual phase returns partial/missing data
    async def mock_extract_individual(subject, sender, attachments):
        if '2021001' in subject:
            return {
                'is_assignment': True,
                'student_id': '2021001',
                'name': None,  # Missing
                'assignment_name': '作业1',
                'confidence': 0.6,
                'reasoning': 'Partial extraction'
            }
        elif '张三' in subject:
            return {
                'is_assignment': True,
                'student_id': None,  # Missing
                'name': '张三',
                'assignment_name': '作业1',
                'confidence': 0.6,
                'reasoning': 'Partial extraction'
            }
        else:
            return {
                'is_assignment': True,
                'student_id': None,
                'name': None,
                'assignment_name': None,
                'confidence': 0.3,
                'reasoning': 'Could not extract'
            }

    # Mock AI batch retry - returns complete data
    async def mock_batch_retry(email_list):
        # Simulate batch AI fixing the missing fields
        return [
            {
                'is_assignment': True,
                'student_id': '2021002',
                'name': '学生2',
                'assignment_name': '作业1',
                'confidence': 0.85,
                'reasoning': 'Batch extracted'
            },
            {
                'is_assignment': True,
                'student_id': '2021001',
                'name': '学生1',
                'assignment_name': '作业1',
                'confidence': 0.9,
                'reasoning': 'Batch extracted'
            },
            {
                'is_assignment': True,
                'student_id': '2021003',
                'name': '张三',
                'assignment_name': '作业1',
                'confidence': 0.88,
                'reasoning': 'Batch extracted'
            }
        ]

    # Apply mocks
    with patch.object(workflow, 'parser', mock_parser):
        with patch.object(workflow.ai, 'extract_student_info', side_effect=mock_extract_individual):
            with patch.object(workflow.ai, 'batch_retry_unknown', side_effect=mock_batch_retry):
                # Mock other dependencies
                with patch.object(workflow.storage, 'store_submission', return_value='/path/to/submission'):
                    with patch.object(workflow.db, 'create_submission') as mock_create:
                        mock_submission = MagicMock()
                        mock_submission.id = 123
                        mock_create.return_value = mock_submission

                        with patch.object(workflow.db, 'add_attachment'):
                            with patch.object(workflow.db, 'log_email_action'):
                                with patch.object(workflow.db, 'mark_replied'):
                                    with patch.object(workflow.parser, 'mark_as_read'):
                                        with patch.object(workflow.parser, 'move_to_folder', return_value=True):
                                            with patch.object(workflow.smtp, 'send_reply'):
                                                with patch.object(workflow.dedup, 'check_and_handle_duplicate', return_value=(False, {})):

                                                    # Run workflow
                                                    result = await workflow.process_inbox()

                                                    # Verify pending_retry was populated
                                                    assert len(workflow.pending_retry) == 0  # Cleared after batch

                                                    # Verify batch retry was called
                                                    workflow.ai.batch_retry_unknown.assert_called_once()

                                                    # Verify all emails were processed
                                                    assert result['total'] == 3
