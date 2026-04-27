"""
分页导航组件
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from gui.styles import palette


class PaginationBar(QFrame):
    """
    分页导航栏组件

    功能:
    - 显示当前页/总页数
    - 上一页/下一页按钮
    - 首页/末页快速跳转
    """

    # 定义信号: 页码变更时发送新页码
    pageChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PaginationBar")

        # 分页状态
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0

        self._init_ui()

    def _init_ui(self):
        """初始化UI布局"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        # 左侧: 统计信息
        self.stats_label = QLabel("共 0 条")
        self.stats_label.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self.stats_label)

        layout.addStretch()

        # 中间: 页码控制和按钮
        # 首页按钮
        self.btn_first = QPushButton("首页")
        self._setup_button(self.btn_first)
        self.btn_first.clicked.connect(lambda: self._go_to_page(1))
        layout.addWidget(self.btn_first)

        # 上一页按钮
        self.btn_prev = QPushButton("上一页")
        self._setup_button(self.btn_prev)
        self.btn_prev.clicked.connect(lambda: self._go_to_page(self.current_page - 1))
        layout.addWidget(self.btn_prev)

        # 页码显示
        self.page_label = QLabel("第 1 / 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet(f"""
            color: {palette.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: bold;
            min-width: 80px;
            padding: 0 10px;
        """)
        layout.addWidget(self.page_label)

        # 下一页按钮
        self.btn_next = QPushButton("下一页")
        self._setup_button(self.btn_next)
        self.btn_next.clicked.connect(lambda: self._go_to_page(self.current_page + 1))
        layout.addWidget(self.btn_next)

        # 末页按钮
        self.btn_last = QPushButton("末页")
        self._setup_button(self.btn_last)
        self.btn_last.clicked.connect(lambda: self._go_to_page(self.total_pages))
        layout.addWidget(self.btn_last)

        layout.addStretch()

        # 初始化按钮状态
        self._update_button_states()

    def _setup_button(self, button):
        """设置按钮样式"""
        button.setFixedHeight(32)
        button.setMinimumWidth(70)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.SURFACE};
                border: 1px solid {palette.BORDER};
                border-radius: 6px;
                color: {palette.TEXT_PRIMARY};
                font-size: 13px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {palette.PRIMARY};
                border-color: {palette.PRIMARY};
                color: white;
            }}
            QPushButton:disabled {{
                background-color: {palette.BACKGROUND};
                border-color: {palette.BORDER};
                color: {palette.TEXT_SECONDARY};
            }}
        """)

    def _update_button_states(self):
        """更新按钮启用/禁用状态"""
        self.btn_first.setEnabled(self.current_page > 1)
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)
        self.btn_last.setEnabled(self.current_page < self.total_pages)

        # 更新页码显示
        self.page_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
        self.stats_label.setText(f"共 {self.total_count} 条")

    def _go_to_page(self, page):
        """跳转到指定页码"""
        if 1 <= page <= self.total_pages and page != self.current_page:
            self.current_page = page
            self._update_button_states()
            self.pageChanged.emit(page)

    def update_pagination(self, current_page: int, total_pages: int, total_count: int):
        """
        更新分页信息

        Args:
            current_page: 当前页码
            total_pages: 总页数
            total_count: 总记录数
        """
        self.current_page = current_page
        self.total_pages = max(1, total_pages)
        self.total_count = total_count
        self._update_button_states()

    def reset(self):
        """重置到第一页"""
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self._update_button_states()
