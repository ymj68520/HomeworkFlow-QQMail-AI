from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QTimer

class ProgressDialog(QDialog):
    """Reusable progress dialog for long-running operations"""

    # Signal to request cancellation from worker thread
    cancel_requested = Signal()

    def __init__(self, parent=None, title="处理中", cancelable=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)
        self.cancelable = cancelable

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Status label
        self.status_label = QLabel("准备...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # Default to indeterminate
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Detail label (shows current item)
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.detail_label)

        # Button box
        button_box = QDialogButtonBox()
        if self.cancelable:
            self.cancel_button = QPushButton("取消")
            self.cancel_button.clicked.connect(self._on_cancel)
            button_box.addButton(self.cancel_button, QDialogButtonBox.ActionRole)
        else:
            self.cancel_button = None
        layout.addWidget(button_box)

    def set_status(self, text: str):
        """Update main status text"""
        self.status_label.setText(text)

    def set_detail(self, text: str):
        """Update detail text (current item being processed)"""
        self.detail_label.setText(text)

    def set_progress(self, current: int, total: int):
        """Update progress bar"""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setFormat(f"{current}/{total} ({percentage}%)")

    def set_indeterminate(self):
        """Show indeterminate progress (for operations with unknown total)"""
        self.progress_bar.setRange(0, 0)  # Makes it show busy indicator

    def _on_cancel(self):
        """Handle cancel button click"""
        if self.cancel_button:
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("取消中...")
            self.cancel_requested.emit()

    def set_complete(self, success: bool = True):
        """Mark operation as complete, change cancel button to close"""
        if self.cancel_button:
            self.cancel_button.setText("关闭")
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self.accept)
            self.cancel_button.setEnabled(True)

        if success:
            self.set_status("完成！")
        else:
            self.set_status("操作完成（有错误）")
