from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QWidget, QGridLayout)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, QPoint
from gui.styles import palette

class Drawer(QFrame):
    """
    右侧滑入详情抽屉组件
    包含动画控制、详情展示区域和正文显示区域
    """
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Drawer")
        self.setFixedWidth(450)
        self._is_open = False
        self._init_ui()
        self._apply_style()
        
        # 初始位置设在父容器外部右侧
        if parent:
            self.hide()
            self.move(parent.width(), 0)

    def _init_ui(self):
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 头部区域 (Header)
        header = QFrame()
        header.setFixedHeight(64)
        header.setObjectName("DrawerHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        self.title_label = QLabel("详情预览")
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {palette.TEXT_PRIMARY};")
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_drawer)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: 16px;
                color: {palette.TEXT_SECONDARY};
                font-size: 18px;
                background-color: transparent;
            }}
            QPushButton:hover {{
                background-color: {palette.BORDER}44;
                color: {palette.TEXT_PRIMARY};
            }}
        """)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(header)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet(f"background-color: {palette.BORDER}; max-height: 1px; border: none;")
        self.main_layout.addWidget(line)

        # 可滚动内容区 (Scroll Area)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;")
        
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(24, 24, 24, 24)
        self.content_layout.setSpacing(20)
        
        # 1. 详情网格 (Details Grid)
        self.details_group = QFrame()
        self.details_layout = QGridLayout(self.details_group)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setVerticalSpacing(12)
        self.details_layout.setHorizontalSpacing(16)
        self.content_layout.addWidget(self.details_group)
        
        # 2. 正文展示区 (Body Content)
        body_label = QLabel("正文内容")
        body_label.setStyleSheet(f"font-weight: bold; color: {palette.TEXT_SECONDARY};")
        self.content_layout.addWidget(body_label)
        
        self.body_text = QLabel()
        self.body_text.setWordWrap(True)
        self.body_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.body_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body_text.setStyleSheet(f"color: {palette.TEXT_PRIMARY}; line-height: 1.5;")
        self.content_layout.addWidget(self.body_text)
        
        self.content_layout.addStretch() # 底部留白
        
        self.scroll_area.setWidget(self.content_container)
        self.main_layout.addWidget(self.scroll_area)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QFrame#Drawer {{
                background-color: {palette.SURFACE};
                border-left: 1px solid {palette.BORDER};
            }}
            QFrame#DrawerHeader {{
                background-color: {palette.SURFACE};
            }}
        """)

    def set_details(self, details: dict, body: str = ""):
        """
        更新展示内容
        details: 键值对字典
        body: 长文本内容
        """
        # 清除旧的详情
        while self.details_layout.count():
            child = self.details_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 重新填充详情
        row = 0
        for key, value in details.items():
            key_lbl = QLabel(f"{key}:")
            key_lbl.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-weight: 500;")
            
            val_lbl = QLabel(str(value))
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet(f"color: {palette.TEXT_PRIMARY};")
            
            self.details_layout.addWidget(key_lbl, row, 0, Qt.AlignTop)
            self.details_layout.addWidget(val_lbl, row, 1, Qt.AlignTop)
            row += 1
            
        # 设置正文
        self.body_text.setText(body or "无正文内容")

    def open_drawer(self):
        """执行滑入动画"""
        if self._is_open: return
        
        # 停止正在进行的动画
        if hasattr(self, "animation"):
            try:
                self.animation.stop()
                # 仅断开 hide，或者直接断开所有 (更安全)
                self.animation.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
        
        self.show()
        self.raise_()
        
        parent = self.parentWidget()
        if not parent: return
        
        # 动态调整高度以匹配父窗口
        self.setFixedHeight(parent.height())
        
        # 从当前位置开始动画，而不是硬编码的起点
        start_pos = self.pos()
        end_pos = QPoint(parent.width() - self.width(), 0)
        
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
        self._is_open = True

    def close_drawer(self):
        """执行滑出动画"""
        if not self._is_open: return
        
        # 停止正在进行的动画
        if hasattr(self, "animation"):
            try:
                self.animation.stop()
                # 仅断开 hide，或者直接断开所有 (更安全)
                self.animation.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
        
        parent = self.parentWidget()
        if not parent: 
            self.hide()
            return
            
        start_pos = self.pos()
        end_pos = QPoint(parent.width(), 0)
        
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.hide)
        self.animation.start()
        self._is_open = False
        self.closed.emit()

    def resizeEvent(self, event):
        """父窗口调整大小时，如果抽屉是打开的，需要保持在最右侧"""
        super().resizeEvent(event)
        parent = self.parentWidget()
        if parent and self._is_open:
            self.move(parent.width() - self.width(), 0)
            self.setFixedHeight(parent.height())
