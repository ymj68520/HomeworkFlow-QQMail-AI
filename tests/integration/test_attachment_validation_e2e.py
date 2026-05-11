# tests/integration/test_attachment_validation_e2e.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.workflow import AssignmentWorkflow
from core.deduplication.service import DeduplicationService
from mail.imap_client import imap_client_inbox
from mail.smtp_client import smtp_client
from mail.parser import mail_parser_inbox as mail_parser
from core.attachment_validator import AttachmentValidator

@pytest.mark.asyncio
async def test_e2e_valid_attachment_flow():
    """End-to-end test: Valid attachment gets processed"""
    workflow = AssignmentWorkflow()

    # Mock the attachment validator to return valid
    workflow.attachment_validator = MagicMock(spec=AttachmentValidator)
    workflow.attachment_validator.validate_attachments = AsyncMock(return_value=MagicMock(is_valid=True, reason=''))

    # Mock all dependencies
    mock_email_data = {
        'uid': 'test-uid-001',
        'subject': '作业1 - 张三',
        'sender_email': 'zhangsan@example.com',
        'sender_name': 'Zhang San',
        'from': 'zhangsan@example.com',
        'has_attachments': True,
        'attachments': [
            {'filename': 'homework.pdf', 'content': b'fake content', 'size': 5 * 1024 * 1024}
        ],
        'message_id': '<test-msg-id@example.com>'
    }

    with patch.object(workflow, 'parser') as mock_parser:
        mock_parser.parse_email.return_value = mock_email_data
        mock_parser.connect.return_value = True
        mock_parser.mark_as_read = MagicMock()

        with patch('core.workflow.ai_extractor') as mock_ai:
            mock_ai.extract_student_info.return_value = {
                'is_assignment': True,
                'student_id': '2021001',
                'name': '张三',
                'assignment_name': '作业1'
            }

            # Mock the AI cache to avoid interference
            mock_ai.cache = {}
            mock_ai.get_cached_result = MagicMock(return_value=None)

            # Mock the db to avoid batch retry
            workflow.db = MagicMock()
            workflow.db.log_email_action = MagicMock()

            with patch('core.workflow.async_db') as mock_db:
                mock_db.create_submission = AsyncMock(return_value=MagicMock(id=1))
                mock_db.get_student_by_id = AsyncMock(return_value=MagicMock(id=1, name='张三'))
                mock_db.get_assignment_by_name = AsyncMock(return_value=MagicMock(id=1))

                with patch('core.workflow.storage_manager') as mock_storage:
                    mock_storage.store_submission.return_value = '/submissions/作业1/2021001张三'

                    with patch.object(workflow, 'imap', spec=imap_client_inbox) as mock_imap:
                        mock_imap.folder_exists.return_value = True

                        with patch.object(workflow, 'smtp', spec=smtp_client) as mock_smtp:
                            mock_smtp.send_reply.return_value = True

                            with patch.object(workflow, 'dedup_service', spec=DeduplicationService) as mock_dedup:
                                mock_dedup.check_email = AsyncMock(
                                    return_value=MagicMock(is_duplicate=False)
                                )
                                mock_dedup.check_submission_with_fuzzy = AsyncMock(
                                    return_value=MagicMock(is_duplicate=False)
                                )

                                with patch('core.workflow.get_async_status_manager') as mock_status:
                                    mock_status.return_value = MagicMock()
                                    mock_status.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                                        transition=AsyncMock()
                                    ))
                                    mock_status.return_value.__aexit__ = AsyncMock()

                                    result = await workflow.process_new_email('test-uid-001')

                                    assert result['success'] is True
                                    assert result['action'] in ['processed', 'reprocessed']

@pytest.mark.asyncio
async def test_e2e_invalid_attachment_rejected():
    """End-to-end test: Invalid attachment gets rejected"""
    workflow = AssignmentWorkflow()

    # Mock the attachment validator to return invalid
    workflow.attachment_validator = MagicMock(spec=AttachmentValidator)
    workflow.attachment_validator.validate_attachments = AsyncMock(return_value=MagicMock(is_valid=False, reason='Executable files not allowed (.exe)'))

    mock_email_data = {
        'uid': 'test-uid-002',
        'subject': '作业1 - 李四',
        'sender_email': 'lisi@example.com',
        'sender_name': 'Li Si',
        'from': 'lisi@example.com',
        'has_attachments': True,
        'attachments': [
            {'filename': 'virus.exe', 'content': b'malicious', 'size': 1 * 1024 * 1024}
        ],
        'message_id': '<test-msg-id-2@example.com>'
    }

    with patch.object(workflow, 'parser', spec=mail_parser) as mock_parser:
        mock_parser.parse_email.return_value = mock_email_data

        # Mock the db on workflow instance
        workflow.db = MagicMock()
        workflow.db.log_email_action = MagicMock()

        result = await workflow.process_new_email('test-uid-002')

        assert result['success'] is False
        assert result['action'] == 'rejected'
        assert '.exe' in result['reason']

        workflow.db.log_email_action.assert_called_once()