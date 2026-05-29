"""筛选模式指示器组件 - 显示在表格上方"""

from typing import Dict
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PySide6.QtCore import Signal, Qt
from gui.styles import palette


class FilterIndicator(QFrame):
    """
    筛选模式指示器

    显示在数据表格上方，用于指示当前处于筛选模式，
    并显示激活的筛选条件。
    """

    # 信号：清除筛选按钮被点击
    clearRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._current_filters = {}

    def _setup_ui(self):
        """设置 UI 界面"""
        self.setFixedHeight(50)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                border-radius: 6px;
                margin: 0px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # 筛选图标
        icon_label = QLabel("🔍")
        icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_label)

        # 筛选模式文本
        self.mode_label = QLabel("筛选模式")
        self.mode_label.setStyleSheet(f"""
            QLabel {{
                color: {palette.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.mode_label)

        # 分隔符
        separator = QLabel("|")
        separator.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        layout.addWidget(separator)

        # 筛选条件标签容器
        self.filter_labels_widget = QWidget()
        self.filter_labels_layout = QHBoxLayout(self.filter_labels_widget)
        self.filter_labels_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_labels_layout.setSpacing(8)
        layout.addWidget(self.filter_labels_widget)

        # 弹性空间
        layout.addStretch()

        # 清除筛选按钮
        self.clear_btn = QPushButton("清除筛选")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #1565C0;
            }}
        """)
        self.clear_btn.clicked.connect(self.clearRequested.emit)
        layout.addWidget(self.clear_btn)

    def set_filters(self, filters: Dict[str, str]):
        """
        设置当前筛选条件并更新显示

        Args:
            filters: 筛选条件字典
                {
                    'student': '001 - 张三' or '全部学生',
                    'assignment': '作业1' or '全部作业',
                    'status': '已完成' or '全部状态'
                }
        """
        self._current_filters = filters
        self._update_filter_labels()

    def _update_filter_labels(self):
        """更新筛选条件标签显示"""
        # 清除现有标签
        while self.filter_labels_layout.count():
            item = self.filter_labels_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加激活的筛选条件标签
        active_filters = []

        if self._current_filters.get('student') != '全部学生':
            active_filters.append(('学生', self._current_filters['student']))

        if self._current_filters.get('assignment') != '全部作业':
            active_filters.append(('作业', self._current_filters['assignment']))

        if self._current_filters.get('status') != '全部状态':
            active_filters.append(('状态', self._current_filters['status']))

        # 创建标签
        for i, (label, value) in enumerate(active_filters):
            filter_label = QLabel(f"{label}: {value}")
            filter_label.setStyleSheet(f"""
                QLabel {{
                    background-color: white;
                    color: {palette.TEXT_PRIMARY};
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                }}
            """)
            self.filter_labels_layout.addWidget(filter_label)

        # 如果没有筛选条件（理论不应该进入筛选模式）
        if not active_filters:
            no_filter_label = QLabel("无筛选条件")
            no_filter_label.setStyleSheet(f"""
                QLabel {{
                    color: {palette.TEXT_SECONDARY};
                    font-size: 12px;
                    font-style: italic;
                }}
            """)
            self.filter_labels_layout.addWidget(no_filter_label)

    def clear_filters(self):
        """清除所有筛选条件"""
        self._current_filters = {
            'student': '全部学生',
            'assignment': '全部作业',
            'status': '全部状态'
        }
        self._update_filter_labels()
