"""可折叠行组件 - 用于展示主记录和子记录（历史版本和可能重复）"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QCheckBox
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
    rowDoubleClicked = Signal(dict)   # 主记录双击
    childClicked = Signal(dict)       # 子记录点击
    checkboxChanged = Signal(bool)    # 复选框状态变更

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

        # 计算子记录统计
        child_count = self.data.get('child_count', 0)
        version_count = self.data.get('version_count', 0)
        possible_dup_count = self.data.get('possible_dup_count', 0)

        # 根据子记录类型设置边框颜色
        border_color = self._get_border_color(version_count, possible_dup_count)

        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.SURFACE};
                border: 1px solid {border_color};
                border-left: 4px solid {border_color};
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

        # 复选框
        self.checkbox = QCheckBox()
        self.checkbox.setFixedWidth(24)
        self.checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
        """)
        layout.addWidget(self.checkbox)
        self.checkbox.stateChanged.connect(lambda state: self.checkboxChanged.emit(state == 2))

        # 学号
        layout.addWidget(QLabel(self._format_field('student_id')))
        layout.addWidget(self._create_separator())

        # 姓名（兼容 name 和 student_name 两种字段名）
        name_value = self._format_field('name') if self._format_field('name') != '-' else self._format_field('student_name')
        layout.addWidget(QLabel(name_value))
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

        # 折叠按钮（仅在有子记录时显示）
        child_count = self.data.get('child_count', 0)
        if child_count > 0:
            self.toggle_button = self._create_toggle_button()
            self.toggle_button.clicked.connect(self.toggle_collapse)
            layout.addWidget(self.toggle_button)
        else:
            self.toggle_button = None

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

    def _get_border_color(self, version_count: int, possible_dup_count: int) -> str:
        """
        根据子记录类型获取边框颜色

        Args:
            version_count: 历史版本数量
            possible_dup_count: 可能重复数量

        Returns:
            边框颜色十六进制值
        """
        if possible_dup_count > 0:
            # 橙色 - 有可能重复的记录
            return '#FD7E14'
        elif version_count > 0:
            # 蓝色 - 只有历史版本
            return '#228BE6'
        else:
            # 默认边框颜色
            return palette.BORDER

    def _create_toggle_button(self) -> QPushButton:
        """
        创建带有计数徽章的折叠按钮

        Returns:
            折叠按钮组件
        """
        child_count = self.data.get('child_count', 0)
        version_count = self.data.get('version_count', 0)
        possible_dup_count = self.data.get('possible_dup_count', 0)

        # 按钮样式 - 根据子记录类型使用不同颜色
        if possible_dup_count > 0:
            button_color = '#FD7E14'  # 橙色 - 有重复
            hover_color = '#E96902'
        else:
            button_color = '#228BE6'  # 蓝色 - 只有版本
            hover_color = '#1C7ED6'

        button = QPushButton(f"▶ {child_count}")
        button.setFixedWidth(60)
        button.setFixedHeight(32)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {button_color};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """)

        # 设置工具提示
        tooltip_parts = []
        if version_count > 0:
            tooltip_parts.append(f"📚 历史版本: {version_count}条")
        if possible_dup_count > 0:
            tooltip_parts.append(f"🔄 可能重复: {possible_dup_count}条")
        button.setToolTip("\n".join(tooltip_parts) if tooltip_parts else "点击展开查看子记录")

        return button

    def toggle_collapse(self):
        """切换折叠状态"""
        if self.toggle_button is None:
            return

        self.is_expanded = not self.is_expanded

        # 更新按钮文本
        child_count = self.data.get('child_count', 0)
        self.toggle_button.setText("▼" if self.is_expanded else f"▶ {child_count}")

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
        label = QLabel(str(relation_label))
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
            elif isinstance(submission_time, datetime):
                submission_time = submission_time.strftime('%Y-%m-%d %H:%M')
            
            # 确保传递给 QLabel 的是字符串
            layout.addWidget(QLabel(str(submission_time)))
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
        # 发送数据时，提取主记录（兼容 primary_submission 嵌套格式）
        data_to_send = self.data
        if 'primary_submission' in self.data:
            # 新格式：提取 primary_submission 作为顶层字段
            primary = self.data.get('primary_submission', {})
            data_to_send = {
                **primary,
                # 保留折叠所需的信息
                'is_collapsible': self.data.get('is_collapsible', False),
                'child_count': self.data.get('child_count', 0),
                'version_count': self.data.get('version_count', 0),
                'possible_dup_count': self.data.get('possible_dup_count', 0),
                'children': self.data.get('children', [])
            }
        else:
            # 旧格式：直接使用
            data_to_send = self.data

        self.rowDoubleClicked.emit(data_to_send)

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

    def is_checked(self) -> bool:
        """
        获取复选框状态

        Returns:
            是否选中
        """
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        """
        设置复选框状态

        Args:
            checked: 是否选中
        """
        self.checkbox.setChecked(checked)

    def get_submission_data(self) -> dict:
        """
        获取提交记录数据

        Returns:
            提交记录字典（兼容 primary_submission 嵌套格式）
        """
        if 'primary_submission' in self.data:
            return self.data['primary_submission']
        return self.data
