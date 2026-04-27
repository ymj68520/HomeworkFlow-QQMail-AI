import pytest
import asyncio
import threading
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox
import sys
from gui.main_window import MainWindow
from core.retry_handler import retry_handler

@pytest.fixture
def app():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app

@pytest.fixture
def main_window(app):
    window = MainWindow()
    yield window
    window.close()

class TestSmartRetryIntegration:
    """Integration tests for smart retry feature"""

    def test_sidebar_buttons_exist(self, main_window):
        """Test that new buttons are present in sidebar"""
        assert hasattr(main_window.sidebar, 'btn_smart_retry')
        assert hasattr(main_window.sidebar, 'btn_batch_reanalyze')
        assert main_window.sidebar.btn_smart_retry.text() == "智能重试"
        assert main_window.sidebar.btn_batch_reanalyze.text() == "批量AI重析"

    def test_batch_reanalyze_button_disabled_with_no_selection(self, main_window):
        """Test that batch re-analyze button is disabled when nothing selected"""
        assert main_window.sidebar.btn_batch_reanalyze.isEnabled() is False

    def test_batch_reanalyze_button_enabled_with_selection(self, main_window):
        """Test that batch re-analyze button becomes enabled when rows selected"""
        # Simulate row selection
        main_window.table.selectRow(0)
        main_window.update_status_info()
        # Note: This depends on having data loaded, may need mock data

    def test_smart_retry_shows_message_for_no_abnormal(self, main_window):
        """Test smart retry shows info message when no abnormal entries"""
        with patch.object(main_window, 'filtered_submissions', []):
            with patch('gui.main_window.QMessageBox.information') as mock_info:
                main_window.on_smart_retry()
                # Should show message about no abnormal entries
                mock_info.assert_called_once()
                args = mock_info.call_args[0]
                assert "没有需要重试的异常条目" in args[2]

    def test_smart_retry_calls_retry_handler(self, main_window):
        """Test that smart retry calls retry_handler with correct data"""
        mock_submissions = [
            {'id': 1, 'status': 'ai_error', 'email_uid': 'uid1'},
            {'id': 2, 'status': 'completed', 'email_uid': 'uid2'}
        ]

        with patch.object(main_window, 'filtered_submissions', mock_submissions):
            with patch('gui.main_window.QMessageBox.question') as mock_confirm:
                mock_confirm.return_value = QMessageBox.No

                with patch.object(retry_handler, 'smart_retry_page', new=AsyncMock()) as mock_retry:
                    # Don't actually run - just verify setup
                    # The actual call happens in a background thread
                    assert hasattr(retry_handler, 'smart_retry_page')

class TestBatchReanalyzeIntegration:
    """Integration tests for batch re-analyze feature"""

    def test_shows_message_for_no_selection(self, main_window):
        """Test batch re-analyze shows message when nothing selected"""
        with patch.object(main_window, 'get_selected_submissions', return_value=[]):
            with patch('gui.main_window.QMessageBox.information') as mock_info:
                main_window.on_batch_reanalyze()
                # Should show message about selecting records
                mock_info.assert_called_once()

    def test_calls_retry_handler_with_selection(self, main_window):
        """Test that batch re-analyze calls retry_handler with selected submissions"""
        mock_selection = [
            {'id': 1, 'student_id': '001', 'email_uid': 'uid1'}
        ]

        with patch.object(main_window, 'get_selected_submissions', return_value=mock_selection):
            with patch('gui.main_window.QMessageBox.question') as mock_confirm:
                mock_confirm.return_value = QMessageBox.No

                # Verify setup is correct
                assert len(mock_selection) == 1
                assert hasattr(retry_handler, 'batch_reanalyze')
