"""作业分组组件 - 按作业名称分组显示学生提交"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict, Any

from gui.components.collapsible_row import CollapsibleRow
from gui.styles import palette


class AssignmentGroup(QWidget):
    """
    作业分组组件

    显示一个作业的所有学生提交记录
    """

    # 信号定义
    rowDoubleClicked = Signal(dict)  # 主记录双击
    childClicked = Signal(dict)      # 子记录点击

    def __init__(self, group_data: Dict[str, Any], parent=None):
        """
        初始化作业分组组件

        Args:
            group_data: 作业分组数据，包含：
                - assignment_name: 作业名称
                - total_submissions: 提交总数
                - total_children: 子记录总数
                - records: 学生提交记录列表
            parent: 父组件
        """
        super().__init__(parent)
        self.group_data = group_data
        self.collapsible_rows = []
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        # 主垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建作业标题
        header = self._create_header()
        main_layout.addWidget(header)

        # 创建记录列表容器
        self.records_container = QWidget()
        self.records_layout = QVBoxLayout(self.records_container)
        self.records_layout.setContentsMargins(0, 8, 0, 0)
        self.records_layout.setSpacing(8)

        # 添加学生提交记录
        records = self.group_data.get('records', [])
        for record_data in records:
            collapsible_row = CollapsibleRow(record_data, self)
            collapsible_row.rowDoubleClicked.connect(self._on_row_double_clicked)
            collapsible_row.childClicked.connect(self._on_child_clicked)
            self.records_layout.addWidget(collapsible_row)
            self.collapsible_rows.append(collapsible_row)

        main_layout.addWidget(self.records_container)

    def _create_header(self) -> QFrame:
        """
        创建作业分组标题

        Returns:
            标题框架组件
        """
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.PRIMARY};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 作业名称
        assignment_name = self.group_data.get('assignment_name', '未知作业')
        name_label = QLabel(assignment_name)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(name_label)

        # 弹性空间
        layout.addStretch()

        # 统计信息
        total_submissions = self.group_data.get('total_submissions', 0)
        total_children = self.group_data.get('total_children', 0)

        stats_text = f"{total_submissions} 位学生提交"
        if total_children > 0:
            stats_text += f" | {total_children} 个历史版本"

        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.9);
                font-size: 13px;
            }}
        """)
        layout.addWidget(stats_label)

        return frame

    def _on_row_double_clicked(self, data: dict):
        """处理主记录双击事件"""
        self.rowDoubleClicked.emit(data)

    def _on_child_clicked(self, data: dict):
        """处理子记录点击事件"""
        self.childClicked.emit(data)
