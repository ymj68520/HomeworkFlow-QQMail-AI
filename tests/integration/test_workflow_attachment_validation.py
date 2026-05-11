# tests/integration/test_workflow_attachment_validation.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.workflow import AssignmentWorkflow

@pytest.mark.asyncio
async def test_workflow_rejects_invalid_attachments():
    """Test that workflow rejects emails with invalid attachments"""
    workflow = AssignmentWorkflow()

    # Mock the validator to reject
    with patch.object(workflow, 'attachment_validator') as mock_validator:
        mock_validator.validate_attachments = AsyncMock(
            return_value=MagicMock(
                is_valid=False,
                reason="Invalid file type: .exe"
            )
        )

        # Mock parser
        workflow.parser.parse_email = MagicMock(
            return_value={
                'uid': '12345',
                'subject': 'Test',
                'sender_email': 'test@example.com',
                'sender_name': 'Test',
                'has_attachments': True,
                'attachments': [
                    {'filename': 'test.exe', 'content': b'...', 'size': 1024}
                ]
            }
        )

        # Mock db
        workflow.db.log_email_action = MagicMock()

        result = await workflow.process_new_email('12345')

        assert result['success'] is False
        assert result['action'] == 'rejected'
        assert result['reason'] == "Invalid file type: .exe"

@pytest.mark.asyncio
async def test_workflow_accepts_valid_attachments():
    """Test that workflow accepts emails with valid attachments"""
    workflow = AssignmentWorkflow()

    # Mock the validator to accept
    with patch.object(workflow, 'attachment_validator') as mock_validator:
        mock_validator.validate_attachments = AsyncMock(
            return_value=MagicMock(is_valid=True)
        )

        # Mock parser and other dependencies
        workflow.parser.parse_email = MagicMock(
            return_value={
                'uid': '12345',
                'subject': '作业1 - 张三',
                'sender_email': 'zhangsan@example.com',
                'sender_name': 'Zhang San',
                'has_attachments': True,
                'attachments': [
                    {'filename': 'homework.pdf', 'content': b'...', 'size': 1024}
                ]
            }
        )

        # Mock AI to return valid result
        workflow.ai.extract_student_info = AsyncMock(
            return_value={
                'is_assignment': True,
                'student_id': '2021001',
                'name': '张三',
                'assignment_name': '作业1'
            }
        )

        # Mock other dependencies
        workflow.dedup_service.check_email = AsyncMock(
            return_value=MagicMock(is_duplicate=False)
        )
        workflow.dedup_service.check_submission_with_fuzzy = AsyncMock(
            return_value=MagicMock(is_duplicate=False)
        )
        workflow.storage.store_submission = MagicMock(return_value='/path/to/submission')
        workflow.db.create_submission = MagicMock(return_value=MagicMock(id=1))
        workflow.imap.folder_exists = MagicMock(return_value=True)
        workflow.parser.move_to_folder = MagicMock(return_value=True)
        workflow.smtp.send_reply = MagicMock(return_value=True)
        workflow.db.mark_replied = MagicMock()
        workflow.db.log_email_action = MagicMock()

        # Mock status manager
        status_manager_mock = MagicMock()
        status_manager_mock.transition = AsyncMock()
        status_manager_mock.close = AsyncMock()
        workflow._get_status_manager = MagicMock(return_value=status_manager_mock)

        result = await workflow.process_new_email('12345')

        # Should proceed with normal processing
        assert result['success'] is True