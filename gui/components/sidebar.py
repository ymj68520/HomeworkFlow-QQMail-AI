from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit,
    QComboBox, QScrollArea, QWidget, QSizePolicy, QPushButton, QToolButton
)
from PySide6.QtCore import Qt, Signal
from gui.styles import palette
from config.settings import settings

class StatsCard(QFrame):
    """
    美观的统计卡片组件
    """
    def __init__(self, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 12px;")
        
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"color: {palette.TEXT_PRIMARY}; font-size: 24px; font-weight: bold;")
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

class CollapsibleFrame(QFrame):
    """
    可折叠卡片组件 (简易实现)
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 标题栏
        self.header = QFrame()
        self.header.setFixedHeight(40)
        self.header.setStyleSheet(f"border-bottom: 1px solid {palette.BORDER};")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.title_label)
        
        # 内容区
        self.content = QFrame()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.content)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

class Sidebar(QFrame):
    """
    侧边栏组件
    """
    # 信号：筛选选项刷新按钮被点击
    refreshFiltersRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(f"background-color: {palette.BACKGROUND}; border-right: 1px solid {palette.BORDER};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(20)
        
        # 1. 统计区
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(10)
        self.total_card = StatsCard("总提交", "0")
        self.downloaded_card = StatsCard("已下载", "0")
        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.downloaded_card)
        layout.addLayout(stats_layout)
        
        # 2. 搜索与过滤区
        filter_section = CollapsibleFrame("过滤器")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索学号或姓名...")

        self.student_filter = QComboBox()
        self.student_filter.addItem("全部学生")

        self.assignment_filter = QComboBox()
        self.assignment_filter.addItem("全部作业")

        self.status_filter = QComboBox()
        self.status_filter.addItem("全部状态")

        filter_section.add_widget(QLabel("关键字搜索:"))
        filter_section.add_widget(self.search_input)
        filter_section.add_widget(QLabel("按学生筛选:"))
        filter_section.add_widget(self.student_filter)
        filter_section.add_widget(QLabel("按作业筛选:"))
        filter_section.add_widget(self.assignment_filter)
        filter_section.add_widget(QLabel("状态筛选:"))
        filter_section.add_widget(self.status_filter)

        # 筛选选项刷新按钮和指示器
        filter_controls_layout = QHBoxLayout()
        filter_controls_layout.setContentsMargins(0, 5, 0, 0)

        self.refresh_filter_btn = QToolButton()
        self.refresh_filter_btn.setText("🔄 刷新选项")
        self.refresh_filter_btn.setToolTip("从数据库重新加载所有筛选选项")
        self.refresh_filter_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_filter_btn.setStyleSheet("""
            QToolButton {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #e5e7eb;
            }
        """)
        self.refresh_filter_btn.clicked.connect(self.refreshFiltersRequested.emit)

        self.filter_new_indicator = QLabel()
        self.filter_new_indicator.setVisible(False)
        self.filter_new_indicator.setStyleSheet("""
            QLabel {
                color: #059669;
                font-size: 10px;
                padding: 2px 6px;
                background-color: #d1fae5;
                border-radius: 3px;
            }
        """)

        filter_controls_layout.addWidget(self.refresh_filter_btn)
        filter_controls_layout.addWidget(self.filter_new_indicator)
        filter_controls_layout.addStretch()

        filter_controls_widget = QWidget()
        filter_controls_widget.setLayout(filter_controls_layout)
        filter_section.add_widget(filter_controls_widget)

        layout.addWidget(filter_section)

        # 3. 批量操作区
        batch_section = CollapsibleFrame("批量操作")
        
        self.btn_download = QPushButton("批量下载附件")
        self.btn_reply = QPushButton("批量回复邮件")
        self.btn_delete = QPushButton("批量删除记录")
        self.btn_export = QPushButton("导出 Excel")

        # 样式微调
        btn_style = f"""
            QPushButton {{
                background-color: {palette.SURFACE};
                border: 1px solid {palette.BORDER};
                border-radius: 4px;
                padding: 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {palette.BORDER};
            }}
        """
        for btn in [self.btn_download, self.btn_reply, self.btn_delete, self.btn_export]:
            btn.setStyleSheet(btn_style)
            batch_section.add_widget(btn)

        # Smart Retry Button
        self.btn_smart_retry = QPushButton("智能重试")
        self.btn_smart_retry.setMinimumHeight(40)
        self.btn_smart_retry.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:pressed {
                background-color: #b45309;
            }
            QPushButton:disabled {
                background-color: #fed7aa;
                color: #9ca3af;
            }
        """)
        batch_section.add_widget(self.btn_smart_retry)

        # Batch Re-analyze Button
        self.btn_batch_reanalyze = QPushButton("批量AI重析")
        self.btn_batch_reanalyze.setMinimumHeight(40)
        self.btn_batch_reanalyze.setEnabled(False)  # Disabled until selection
        self.btn_batch_reanalyze.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:pressed {
                background-color: #6d28d9;
            }
            QPushButton:disabled {
                background-color: #ddd6fe;
                color: #9ca3af;
            }
        """)
        batch_section.add_widget(self.btn_batch_reanalyze)

        # 邮件回复开关逻辑
        self.btn_reply.setEnabled(settings.ENABLE_REPLY)
        if not settings.ENABLE_REPLY:
            self.btn_reply.setToolTip("邮件回复功能已在配置中禁用")

        layout.addWidget(batch_section)

        # 弹性空间
        layout.addStretch()

    def set_filter_new_indicator(self, has_new: bool):
        """
        设置筛选选项新项指示器

        Args:
            has_new: 是否有新选项
        """
        self.filter_new_indicator.setVisible(has_new)
        if has_new:
            self.filter_new_indicator.setText("✨ 新选项")
