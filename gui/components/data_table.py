from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QCheckBox
)
from PySide6.QtCore import Signal, Qt, QEvent

from gui.components.collapsible_row import CollapsibleRow
from gui.components.assignment_group import AssignmentGroup
from gui.styles import palette

class DataTable(QWidget):
    """
    现代化数据表格组件
    使用 CollapsibleRow 支持折叠/展开功能
    """
    rowDoubleClicked = Signal(dict)
    childClicked = Signal(dict)
    selectionChanged = Signal()  # 选择状态变更信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsible_rows = []
        self.assignment_groups = []  # 新增：作业分组组件列表
        self._selection_model = MockSelectionModel(self)
        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        # 主垂直布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # 滚动内容容器
        self.scroll_content = QWidget()
        self.scroll_content.setLayout(self.main_layout)
        self.scroll_area.setWidget(self.scroll_content)

        # 将滚动区域添加到主布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.scroll_area)
        self.setLayout(outer_layout)

        # 安装事件过滤器以拦截子控件的右键事件
        self.scroll_area.viewport().installEventFilter(self)

    def _apply_style(self):
        # QSS 样式定义
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {palette.SURFACE};
                color: {palette.TEXT_PRIMARY};
            }}
        """)
        # 为滚动内容设置大小策略
        self.scroll_content.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Preferred
        )

    def eventFilter(self, obj, event):
        """拦截子控件的右键菜单事件，确保 customContextMenuRequested 正确发出"""
        if event.type() == QEvent.ContextMenu:
            self.customContextMenuRequested.emit(event.pos())
            return True
        return super().eventFilter(obj, event)

    def set_data(self, data_list: list):
        """
        设置数据 - 使用 CollapsibleRow 或 AssignmentGroup 展示

        Args:
            data_list: 数据字典列表，可以是：
                - 直接的提交记录列表（旧格式）
                - 按作业分组的数据列表（新格式，包含 assignment_name 字段）
        """
        # 清除现有的可折叠行和分组
        for row in self.collapsible_rows:
            row.deleteLater()
        self.collapsible_rows.clear()

        for group in self.assignment_groups:
            group.deleteLater()
        self.assignment_groups.clear()

        # 清空布局
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加表头
        self._add_header()

        # 检查数据格式
        if data_list and 'assignment_name' in data_list[0] and 'records' in data_list[0]:
            # 新格式：按作业分组
            self._set_assignment_grouped_data(data_list)
        else:
            # 旧格式：直接的学生提交记录
            self._set_flat_data(data_list)

        # 添加弹性空间
        self.main_layout.addStretch()

    def get_all_rows(self):
        """获取所有 CollapsibleRow，无论 flat 还是 grouped 模式"""
        rows = list(self.collapsible_rows)
        for group in self.assignment_groups:
            rows.extend(group.collapsible_rows)
        return rows

    def get_checked_rows(self):
        """获取所有被勾选的 CollapsibleRow"""
        return [row for row in self.get_all_rows() if row.is_checked()]

    def _connect_row_signals(self, row: CollapsibleRow):
        """连接单行的 checkbox 信号到 selectionChanged"""
        row.checkboxChanged.connect(lambda checked: self.selectionChanged.emit())

    def _set_flat_data(self, data_list: list):
        """
        设置平面数据（旧格式兼容）

        Args:
            data_list: 直接的提交记录列表
        """
        # 创建并添加 CollapsibleRow
        for data in data_list:
            collapsible_row = CollapsibleRow(data, self)
            collapsible_row.rowDoubleClicked.connect(self._on_row_double_clicked)
            collapsible_row.childClicked.connect(self._on_child_clicked)
            self._connect_row_signals(collapsible_row)
            self.main_layout.addWidget(collapsible_row)
            self.collapsible_rows.append(collapsible_row)

    def _set_assignment_grouped_data(self, data_list: list):
        """
        设置按作业分组的数据（新格式）

        Args:
            data_list: 按作业分组的数据列表
        """
        # 为每个作业组创建 AssignmentGroup 组件
        for group_data in data_list:
            assignment_group = AssignmentGroup(group_data, self)
            assignment_group.rowDoubleClicked.connect(self._on_row_double_clicked)
            assignment_group.childClicked.connect(self._on_child_clicked)
            # 连接分组内每行的 checkbox 信号
            for row in assignment_group.collapsible_rows:
                self._connect_row_signals(row)
            self.main_layout.addWidget(assignment_group)
            self.assignment_groups.append(assignment_group)

            # 添加间距
            spacer = QFrame()
            spacer.setFixedHeight(16)
            self.main_layout.addWidget(spacer)

    def _add_header(self):
        """添加表格头部"""
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {palette.SURFACE};
                border: none;
                border-bottom: 2px solid {palette.BORDER};
                padding: 12px 8px;
            }}
        """)

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        # 全选复选框
        self.select_all_checkbox = QCheckBox()
        self.select_all_checkbox.setFixedWidth(24)
        self.select_all_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
        """)
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        header_layout.addWidget(self.select_all_checkbox)

        # 列标题
        headers = ["学号", "姓名", "作业名称", "提交时间", "状态", "本地路径"]

        # 添加多作业组指示器列标题
        group_label = QLabel("📎")
        group_label.setStyleSheet(f"""
            QLabel {{
                color: {palette.TEXT_SECONDARY};
                font-weight: bold;
                font-size: 14px;
                padding: 0 4px;
            }}
        """)
        group_label.setToolTip("多作业组指示")
        header_layout.addWidget(group_label)

        # 添加分隔符
        separator = QLabel("|")
        separator.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        header_layout.addWidget(separator)

        for header_text in headers:
            label = QLabel(header_text)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {palette.TEXT_SECONDARY};
                    font-weight: bold;
                    font-size: 11px;
                    text-transform: uppercase;
                }}
            """)
            header_layout.addWidget(label)

        # 弹性空间
        header_layout.addStretch()

        # 折叠按钮占位
        placeholder = QLabel()
        placeholder.setFixedWidth(32)
        header_layout.addWidget(placeholder)

        self.main_layout.addWidget(header_frame)

    def _on_select_all_changed(self, state):
        """处理全选复选框状态改变"""
        is_checked = (state == Qt.Checked or state == 2) # Qt.Checked is 2
        for row in self.get_all_rows():
            row.checkbox.blockSignals(True)
            row.set_checked(is_checked)
            row.checkbox.blockSignals(False)
        self.selectionChanged.emit()

    def _on_row_double_clicked(self, data: dict):
        """
        处理主记录双击事件

        Args:
            data: 主记录数据
        """
        self.rowDoubleClicked.emit(data)

    def _on_child_clicked(self, data: dict):
        """
        处理子记录点击事件

        Args:
            data: 子记录数据
        """
        self.childClicked.emit(data)

    def clear_data(self):
        """清空表格数据"""
        # 清除现有的可折叠行
        for row in self.collapsible_rows:
            row.deleteLater()
        self.collapsible_rows.clear()

        # 清除作业分组组件
        for group in self.assignment_groups:
            group.deleteLater()
        self.assignment_groups.clear()

        # 清空布局
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_row(self, row_data: dict):
        """
        添加单行数据（向后兼容方法）

        Args:
            row_data: 行数据字典
        """
        # 转换为分组格式
        group_data = {
            'primary_submission': row_data,
            'children': []
        }
        collapsible_row = CollapsibleRow(group_data, self)
        collapsible_row.rowDoubleClicked.connect(self._on_row_double_clicked)
        collapsible_row.childClicked.connect(self._on_child_clicked)
        self._connect_row_signals(collapsible_row)
        self.main_layout.insertWidget(self.main_layout.count() - 1, collapsible_row)  # 在stretch之前插入
        self.collapsible_rows.append(collapsible_row)

    def set_data_bulk(self, data_list: list):
        """
        批量设置数据（向后兼容方法）

        Args:
            data_list: 数据字典列表
        """
        # 转换为分组格式
        grouped_data = [
            {
                'primary_submission': row_data,
                'children': []
            }
            for row_data in data_list
        ]
        self.set_data(grouped_data)

    def rowCount(self):
        """返回行数（向后兼容方法）"""
        return len(self.get_all_rows())

    def item(self, row: int, column: int):
        """
        获取表格项（向后兼容方法）

        注意：这是简化实现，仅用于基本兼容
        """
        all_rows = self.get_all_rows()
        if row < len(all_rows):
            collapsible_row = all_rows[row]
            # 返回一个模拟的 QTableWidgetItem
            class MockItem:
                def __init__(self, text):
                    self._text = str(text)

                def text(self):
                    return self._text

            # 兼容 primary_submission 嵌套格式和直接格式
            data = collapsible_row.data
            if 'primary_submission' in data:
                primary = data['primary_submission']
            else:
                primary = data

            column_mapping = {
                0: primary.get('student_id', ''),
                1: primary.get('student_name', ''),
                2: primary.get('assignment_name', ''),
                3: primary.get('submission_time', ''),
                4: primary.get('status', ''),
                5: primary.get('local_path', ''),
                6: primary.get('local_path', '')
            }

            return MockItem(column_mapping.get(column, ''))

        return None

    def setSelectionModel(self, selection_model):
        """设置选择模型（向后兼容占位符）"""
        pass

    def selectionModel(self):
        """返回选择模型（向后兼容占位符）"""
        return self._selection_model

    def setSelectionMode(self, mode):
        """设置选择模式（向后兼容占位符）"""
        pass

    def set_headers(self, headers, stretch_column=None):
        """
        设置表头（向后兼容占位符）

        Args:
            headers: 表头列表
            stretch_column: 伸缩列索引
        """
        pass

    def update_rows_bulk(self, row_updates: dict):
        """
        批量更新行数据（向后兼容方法）

        Args:
            row_updates: 字典，键为行索引，值为要更新的数据字典
        """
        all_rows = self.get_all_rows()
        for row_idx, updates in row_updates.items():
            if row_idx < len(all_rows):
                collapsible_row = all_rows[row_idx]
                # 更新主记录数据
                primary = collapsible_row.data.get('primary_submission', {})
                primary.update(updates)
                # 重新创建行组件
                collapsible_row.primary_row.deleteLater()
                collapsible_row.primary_row = collapsible_row._create_primary_row()
                collapsible_row.layout().insertWidget(0, collapsible_row.primary_row)


class MockSelectionModel:
    """模拟选择模型（向后兼容）"""
    def __init__(self, table):
        self.table = table

    def selectedRows(self):
        """遍历所有行，返回被勾选行的索引"""
        selected = []
        for i, row in enumerate(self.table.get_all_rows()):
            if row.is_checked():
                selected.append(MockIndex(i))
        return selected

    def select(self, index, flags):
        pass

class MockIndex:
    """模拟 QModelIndex"""
    def __init__(self, row):
        self._row = row
    
    def row(self):
        return self._row
