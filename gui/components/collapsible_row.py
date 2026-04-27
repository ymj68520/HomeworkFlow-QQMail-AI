"""可折叠行组件 - 用于展示主记录和子记录（历史版本和可能重复）"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from datetime import datetime
from typing import Dict, List, Any, Optional

from gui.styles import palette
from gui.components.common import Badge


class CollapsibleRow(QWidget):
    """
    可折叠行组件

    显示主提交记录，可以展开显示子记录（历史版本和可能重复）
    """

    # 信号定义
    rowDoubleClicked = Signal(dict)  # 主记录双击
    childClicked = Signal(dict)      # 子记录点击

    def __init__(self, data: Dict[str, Any], parent=None):
        """
        初始化可折叠行

        Args:
            data: 主记录数据字典，包含：
                - id, student_id, student_name, assignment_name
                - submission_time, status, local_path
                - children: 子记录列表（可选）
            parent: 父组件
        """
        super().__init__(parent)
        self.data = data
        self.is_expanded = False
        self.child_widgets: List[QWidget] = []

        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        # 主垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建主行
        self.primary_row = self._create_primary_row()
        main_layout.addWidget(self.primary_row)

        # 创建可折叠区域（初始隐藏）
        self.collapsible_area = QWidget()
        self.collapsible_area.setVisible(False)
        main_layout.addWidget(self.collapsible_area)

    def _create_primary_row(self) -> QFrame:
        """
        创建主行组件

        Returns:
            主行框架组件
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.SURFACE};
                border: 1px solid {palette.BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
            QFrame:hover {{
                background-color: {palette.BACKGROUND};
            }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 学号
        layout.addWidget(QLabel(self._format_field('student_id')))
        layout.addWidget(self._create_separator())

        # 姓名
        layout.addWidget(QLabel(self._format_field('student_name')))
        layout.addWidget(self._create_separator())

        # 作业名称
        layout.addWidget(QLabel(self._format_field('assignment_name')))
        layout.addWidget(self._create_separator())

        # 提交时间
        layout.addWidget(QLabel(self._format_field('submission_time')))
        layout.addWidget(self._create_separator())

        # 状态标签
        status_badge = Badge(
            self._format_field('status'),
            self._get_status_color_type()
        )
        layout.addWidget(status_badge)
        layout.addWidget(self._create_separator())

        # 本地路径
        layout.addWidget(QLabel(self._format_field('local_path')))

        # 弹性空间
        layout.addStretch()

        # 折叠按钮
        self.toggle_button = QPushButton("▶")
        self.toggle_button.setFixedWidth(32)
        self.toggle_button.setFixedHeight(32)
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.PRIMARY};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #228BE6;
            }}
            QPushButton:pressed {{
                background-color: #1C7ED6;
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_collapse)
        layout.addWidget(self.toggle_button)

        # 双击事件
        frame.mouseDoubleClickEvent = self._on_double_click

        return frame

    def _create_separator(self) -> QLabel:
        """创建分隔符"""
        separator = QLabel("|")
        separator.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        return separator

    def _format_field(self, field: str) -> str:
        """
        格式化字段值

        Args:
            field: 字段名

        Returns:
            格式化后的字符串
        """
        # 处理分组数据格式
        if 'primary_submission' in self.data:
            primary = self.data.get('primary_submission', {})
            value = primary.get(field)
        else:
            # 直接数据格式（向后兼容）
            value = self.data.get(field)

        if value is None or value == '':
            return '-'

        # 格式化日期时间字段
        if field in ['submission_time', 'received_time', 'created_at', 'updated_at']:
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d %H:%M')
                except:
                    return value
            elif isinstance(value, datetime):
                return value.strftime('%Y-%m-%d %H:%M')

        # 映射状态码到中文标签
        if field == 'status':
            status_map = {
                'pending': '待处理',
                'ai_error': '识别异常',
                'download_failed': '下载失败',
                'unreplied': '未回复',
                'completed': '已完成',
                'ignored': '已忽略'
            }
            return status_map.get(value, value)

        # 截断过长的本地路径
        if field == 'local_path' and len(str(value)) > 30:
            return '...' + str(value)[-30:]

        return str(value)

    def _get_status_color_type(self) -> str:
        """
        获取状态对应的颜色类型

        Returns:
            颜色类型字符串
        """
        # 处理分组数据格式
        if 'primary_submission' in self.data:
            primary = self.data.get('primary_submission', {})
            status = primary.get('status', 'pending')
        else:
            status = self.data.get('status', 'pending')

        color_map = {
            'completed': 'success',
            'download_failed': 'error',
            'ai_error': 'error',
            'unreplied': 'warning',
            'pending': 'primary',
            'ignored': 'primary'
        }
        return color_map.get(status, 'primary')

    def toggle_collapse(self):
        """切换折叠状态"""
        self.is_expanded = not self.is_expanded

        # 更新按钮文本
        self.toggle_button.setText("▼" if self.is_expanded else "▶")

        # 显示/隐藏可折叠区域
        self.collapsible_area.setVisible(self.is_expanded)

        # 如果展开，填充子记录
        if self.is_expanded:
            self._populate_children()

    def _populate_children(self):
        """填充子记录"""
        # 清除现有子组件
        for widget in self.child_widgets:
            widget.deleteLater()
        self.child_widgets.clear()

        # 获取子记录
        children = self.data.get('children', [])

        if not children:
            # 无子记录时显示提示
            no_children_label = QLabel("无相关记录")
            no_children_label.setStyleSheet(f"""
                QLabel {{
                    color: {palette.TEXT_SECONDARY};
                    padding: 16px;
                    font-style: italic;
                }}
            """)
            self.child_widgets.append(no_children_label)
        else:
            # 按关系类型分组
            version_children = []
            possible_dup_children = []

            for child in children:
                relation_type = child.get('relation_type')
                if relation_type == 'version':
                    version_children.append(child)
                elif relation_type == 'possible_dup':
                    possible_dup_children.append(child)

            # 创建历史版本区域
            if version_children:
                version_section = self._create_section(
                    "📚 历史版本",
                    version_children
                )
                self.child_widgets.append(version_section)

            # 创建可能重复区域
            if possible_dup_children:
                dup_section = self._create_section(
                    "🔄 可能重复",
                    possible_dup_children
                )
                self.child_widgets.append(dup_section)

        # 添加到可折叠区域
        layout = QVBoxLayout(self.collapsible_area)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        for widget in self.child_widgets:
            layout.addWidget(widget)

    def _create_section(self, title: str, children: List[Dict[str, Any]]) -> QFrame:
        """
        创建子记录区域

        Args:
            title: 区域标题
            children: 子记录列表

        Returns:
            区域框架组件
        """
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.SURFACE};
                border: 1px solid {palette.BORDER};
                border-left: 4px solid {palette.PRIMARY};
                border-radius: 8px;
                margin: 4px 0;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {palette.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: bold;
                padding-bottom: 4px;
            }}
        """)
        layout.addWidget(title_label)

        # 子记录行
        for child in children:
            child_row = self._create_child_row(child)
            layout.addWidget(child_row)

        return frame

    def _create_child_row(self, child: Dict[str, Any]) -> QFrame:
        """
        创建子记录行

        Args:
            child: 子记录数据

        Returns:
            子记录行组件
        """
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.BACKGROUND};
                border-radius: 6px;
                padding: 6px;
            }}
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        # 关系标签
        relation_label = child.get('relation_label', '子记录')
        label = QLabel(relation_label)
        label.setStyleSheet(f"""
            QLabel {{
                color: {palette.TEXT_SECONDARY};
                font-size: 12px;
                padding-right: 8px;
            }}
        """)
        layout.addWidget(label)

        # 学号和姓名
        student_info = f"{child.get('student_id', '-')} - {child.get('student_name', '-')}"
        layout.addWidget(QLabel(student_info))
        layout.addWidget(self._create_separator())

        # 提交时间
        submission_time = child.get('submission_time')
        if submission_time:
            if isinstance(submission_time, str):
                try:
                    dt = datetime.fromisoformat(submission_time.replace('Z', '+00:00'))
                    submission_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass
            layout.addWidget(QLabel(submission_time))
        else:
            layout.addWidget(QLabel('-'))

        # 弹性空间
        layout.addStretch()

        # 查看详情按钮
        detail_button = QPushButton("查看详情")
        detail_button.setFixedHeight(28)
        detail_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.SURFACE};
                color: {palette.PRIMARY};
                border: 1px solid {palette.PRIMARY};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {palette.PRIMARY};
                color: white;
            }}
        """)
        detail_button.clicked.connect(
            lambda checked, c=child: self.childClicked.emit(c)
        )
        layout.addWidget(detail_button)

        return frame

    def _on_double_click(self, event: QMouseEvent):
        """
        处理双击事件

        Args:
            event: 鼠标事件
        """
        self.rowDoubleClicked.emit(self.data)

    def update_data(self, data: Dict[str, Any]):
        """
        更新数据

        Args:
            data: 新的主记录数据
        """
        self.data = data

        # 如果已展开，重新填充子记录
        if self.is_expanded:
            self._populate_children()

        # 重新创建主行以更新显示
        main_layout = self.layout()
        if main_layout:
            main_layout.removeWidget(self.primary_row)
            self.primary_row.deleteLater()
            self.primary_row = self._create_primary_row()
            main_layout.insertWidget(0, self.primary_row)
