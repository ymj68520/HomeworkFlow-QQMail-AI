from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Signal

from gui.components.collapsible_row import CollapsibleRow
from gui.styles import palette

class DataTable(QWidget):
    """
    现代化数据表格组件
    使用 CollapsibleRow 支持折叠/展开功能
    """
    rowDoubleClicked = Signal(dict)
    childClicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsible_rows = []
        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        # 主垂直布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

    def _apply_style(self):
        # QSS 样式定义
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {palette.SURFACE};
                color: {palette.TEXT_PRIMARY};
            }}
        """)

    def set_data(self, data_list: list):
        """
        设置数据 - 使用 CollapsibleRow 展示

        Args:
            data_list: 数据字典列表，每个字典代表一条提交记录
        """
        # 清除现有的可折叠行
        for row in self.collapsible_rows:
            row.deleteLater()
        self.collapsible_rows.clear()

        # 清空布局
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加表头
        self._add_header()

        # 创建并添加 CollapsibleRow
        for data in data_list:
            collapsible_row = CollapsibleRow(data, self)
            collapsible_row.rowDoubleClicked.connect(self._on_row_double_clicked)
            collapsible_row.childClicked.connect(self._on_child_clicked)
            self.main_layout.addWidget(collapsible_row)
            self.collapsible_rows.append(collapsible_row)

        # 添加弹性空间
        self.main_layout.addStretch()

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

        # 列标题
        headers = ["学号", "姓名", "作业名称", "提交时间", "状态", "本地路径"]
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
