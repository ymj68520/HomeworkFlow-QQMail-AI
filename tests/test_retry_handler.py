import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from core.retry_handler import RetryHandler, retry_handler

@pytest.fixture
def mock_submission():
    return {
        'id': 1,
        'email_uid': 'test_uid_123',
        'student_id': '2021001',
        'name': 'Test Student',
        'assignment_name': '作业1',
        'status': 'ai_error',
        'email': 'test@example.com',
        'submission_time': None
    }

@pytest.fixture
def mock_email_data():
    return {
        'subject': '作业1 - 2021001 - Test Student',
        'sender_email': 'test@example.com',
        'sender_name': 'Test Student',
        'attachments': [
            {'filename': 'homework.docx', 'size': 12345}
        ],
        'has_attachments': True,
        'message_id': 'test_msg_id'
    }

class TestRetryHandler:
    """Test RetryHandler class"""

    def test_abnormal_statuses_constant(self):
        """Test that ABNORMAL_STATUSES includes expected values"""
        handler = RetryHandler()
        assert 'ai_error' in handler.ABNORMAL_STATUSES
        assert 'download_failed' in handler.ABNORMAL_STATUSES
        assert 'pending' in handler.ABNORMAL_STATUSES

    @pytest.mark.asyncio
    async def test_smart_retry_page_empty_list(self):
        """Test smart_retry_page with empty submission list"""
        handler = RetryHandler()
        result = await handler.smart_retry_page([])
        assert result['total'] == 0
        assert result['success'] == 0
        assert result['failed'] == 0

    @pytest.mark.asyncio
    async def test_smart_retry_page_no_abnormal_entries(self):
        """Test smart_retry_page when no abnormal entries exist"""
        handler = RetryHandler()
        normal_submissions = [
            {'id': 1, 'status': 'completed', 'email_uid': 'uid1'},
            {'id': 2, 'status': 'unreplied', 'email_uid': 'uid2'}
        ]
        result = await handler.smart_retry_page(normal_submissions)
        assert result['total'] == 0

    @pytest.mark.asyncio
    async def test_smart_retry_page_filters_abnormal(self, mock_submission):
        """Test that smart_retry_page only processes abnormal entries"""
        handler = RetryHandler()
        submissions = [
            mock_submission,  # ai_error
            {'id': 2, 'status': 'completed', 'email_uid': 'uid2'}  # normal
        ]

        with patch.object(handler, 'parser') as mock_parser:
            mock_parser.connect.return_value = True
            mock_parser.parse_email.return_value = None  # Email doesn't exist
            mock_parser.disconnect.return_value = None

            with patch.object(handler, '_email_exists', return_value=False):
                result = await handler.smart_retry_page(submissions)

                # Should only process the abnormal entry
                assert result['total'] == 1
                assert result['skipped'] == 1

    @pytest.mark.asyncio
    async def test_batch_reanalyze_empty_list(self):
        """Test batch_reanalyze with empty submission list"""
        handler = RetryHandler()
        result = await handler.batch_reanalyze([])
        assert result['total'] == 0
        assert result['success'] == 0

    @pytest.mark.asyncio
    async def test_batch_reanalyze_success(
        self,
        mock_submission,
        mock_email_data
    ):
        """Test batch_reanalyze successful case"""
        handler = RetryHandler()

        with patch.object(handler, 'parser') as mock_parser:
            mock_parser.connect.return_value = True
            mock_parser.parse_email.return_value = mock_email_data
            mock_parser.imap.select_folder.return_value = True
            mock_parser.disconnect.return_value = None

            mock_ai_result = {
                'is_assignment': True,
                'student_id': '2021001',
                'name': 'Test Student',
                'assignment_name': '作业1',
                'confidence': 0.95
            }

            with patch.object(handler, 'ai') as mock_ai:
                mock_ai.extract_student_info = AsyncMock(return_value=mock_ai_result)

                with patch.object(handler, 'db') as mock_db:
                    mock_db.update_submission_full.return_value = True

                    result = await handler.batch_reanalyze([mock_submission])

                    assert result['total'] == 1
                    assert result['success'] == 1
                    assert result['failed'] == 0
                    mock_db.update_submission_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_exists_in_target_folder(self):
        """Test _email_exists finds email in TARGET_FOLDER"""
        handler = RetryHandler()

        with patch.object(handler.parser, 'imap') as mock_imap:
            mock_imap.select_folder.return_value = True

            with patch.object(handler.parser, 'uid_exists', return_value=True):
                result = await handler._email_exists('test_uid')
                assert result is True

    @pytest.mark.asyncio
    async def test_fetch_fresh_email_priority(self):
        """Test _fetch_fresh_email tries TARGET_FOLDER first"""
        handler = RetryHandler()
        mock_email = {'subject': 'Test'}

        with patch.object(handler.parser, 'imap') as mock_imap:
            mock_imap.select_folder.return_value = True

            with patch.object(handler.parser, 'parse_email') as mock_parse:
                # TARGET_FOLDER returns email immediately
                mock_parse.return_value = mock_email

                result = handler._fetch_fresh_email('test_uid')

                assert result == mock_email
                # Should only call once (found in TARGET_FOLDER)
                assert mock_parse.call_count == 1

def test_global_instance():
    """Test that global retry_handler instance exists"""
    from core.retry_handler import retry_handler
    assert retry_handler is not None
    assert isinstance(retry_handler, RetryHandler)
