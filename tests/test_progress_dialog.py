import pytest
from PySide6.QtWidgets import QApplication
import sys
from gui.components.progress_dialog import ProgressDialog

@pytest.fixture
def app():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app

def test_progress_dialog_creation(app):
    """Test that progress dialog can be created"""
    dialog = ProgressDialog()
    assert dialog.windowTitle() == "处理中"
    assert dialog.cancelable is True
    assert dialog.cancel_button is not None

def test_progress_dialog_not_cancelable(app):
    """Test non-cancelable dialog"""
    dialog = ProgressDialog(cancelable=False)
    assert dialog.cancelable is False
    assert dialog.cancel_button is None

def test_progress_dialog_updates(app):
    """Test status and progress updates"""
    dialog = ProgressDialog()

    dialog.set_status("Testing...")
    assert dialog.status_label.text() == "Testing..."

    dialog.set_detail("Processing item 1")
    assert dialog.detail_label.text() == "Processing item 1"

    dialog.set_progress(5, 10)
    assert dialog.progress_bar.value() == 5
    assert dialog.progress_bar.maximum() == 10

def test_progress_dialog_indeterminate(app):
    """Test indeterminate progress mode"""
    dialog = ProgressDialog()
    dialog.set_indeterminate()
    assert dialog.progress_bar.minimum() == 0
    assert dialog.progress_bar.maximum() == 0

def test_progress_dialog_complete(app):
    """Test completion state"""
    dialog = ProgressDialog()
    dialog.set_complete(success=True)
    assert dialog.status_label.text() == "完成！"
    assert dialog.cancel_button.text() == "关闭"
