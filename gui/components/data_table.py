from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, Signal
from gui.components.common import Badge
from gui.styles import palette

class DataTable(QTableWidget):
    """
    现代化数据表格组件
    支持自定义 Badge 渲染、Hover 效果和双击行信号
    """
    rowDoubleClicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        # 基础配置
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)  # 开启鼠标追踪以支持更灵敏的 Hover

        # 表头配置
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setHighlightSections(False)

        # 信号连接
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _apply_style(self):
        # QSS 样式定义 - 方案 A 深色模式
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {palette.SURFACE};
                color: {palette.TEXT_PRIMARY};
                border: 1px solid {palette.BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 12px 8px;
                border-bottom: 1px solid {palette.BORDER};
                color: {palette.TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: {palette.PRIMARY}33; /* 20% 透明度的主色 */
                color: {palette.PRIMARY};
                border-bottom: 1px solid {palette.BORDER};
            }}
            QTableWidget::item:hover {{
                background-color: {palette.BORDER}44;
            }}
            QHeaderView::section {{
                background-color: {palette.SURFACE};
                color: {palette.TEXT_SECONDARY};
                padding: 12px 8px;
                border: none;
                border-bottom: 2px solid {palette.BORDER};
                font-weight: bold;
                font-size: 11px;
                text-transform: uppercase;
            }}
        """)

    def _on_cell_double_clicked(self, row, column):
        """处理行双击，组装字典并发送信号"""
        row_data = {}
        for col in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(col)
            if header_item:
                key = header_item.text()
                # 优先获取 Item 文本
                item = self.item(row, col)
                if item:
                    row_data[key] = item.data(Qt.UserRole) or item.text()
                
                # 如果有 Widget (如 Badge)，尝试从 Widget 获取
                widget = self.cellWidget(row, col)
                if isinstance(widget, Badge):
                    row_data[key] = widget.text()
        
        self.rowDoubleClicked.emit(row_data)

    def set_headers(self, headers: list, stretch_column: int = None):
        """
        设置表头
        stretch_column: 指定伸展的列索引，若为 None 则尝试自动匹配
        """
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        header = self.horizontalHeader()
        
        # 如果未指定，尝试自动匹配“主题”或“内容”作为伸展列
        if stretch_column is None:
            for i, h in enumerate(headers):
                if h in ["主题", "内容", "Subject", "Body"]:
                    stretch_column = i
                    break
        
        # 应用伸展模式
        if stretch_column is not None and stretch_column < len(headers):
            header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
            # 其他列保持 Interactive
            for i in range(len(headers)):
                if i != stretch_column:
                    header.setSectionResizeMode(i, QHeaderView.Interactive)
        else:
            # 默认回退：所有列交互，最后一列伸展
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(True)

    def add_row(self, data: dict):
        """
        添加一行数据
        data 字典的键应与表头文字对应
        """
        row = self.rowCount()
        self.insertRow(row)
        
        for col in range(self.columnCount()):
            header_text = self.horizontalHeaderItem(col).text()
            val = data.get(header_text, "")
            
            if header_text == "状态":
                # 特殊处理状态列，渲染 Badge
                color_type = "primary"
                val_str = str(val)
                if "成功" in val_str or "完成" in val_str:
                    color_type = "success"
                elif "失败" in val_str or "错误" in val_str:
                    color_type = "error"
                
                badge = Badge(val_str, color_type=color_type)
                container = self._wrap_widget(badge)
                self.setCellWidget(row, col, container)
                
                # 关键修复：setText("") 确保单元格背景没有文字显示，数据存入 UserRole
                item = QTableWidgetItem("") 
                item.setData(Qt.UserRole, val)
                self.setItem(row, col, item)
            else:
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, val)
                self.setItem(row, col, item)
        
        self.setRowHeight(row, 52)

    def _wrap_widget(self, widget):
        """辅助方法：将组件居中包裹在容器中"""
        from PySide6.QtWidgets import QWidget, QHBoxLayout
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return container

    def clear_data(self):
        """清空所有行"""
        self.setRowCount(0)
