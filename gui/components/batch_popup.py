"""
批量修改悬浮弹出层组件 - PySide6 实现
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStackedWidget, QWidget, QLineEdit, 
    QComboBox, QFrame, QApplication
)
from PySide6.QtCore import Qt, Signal
from gui.styles import palette
from typing import List, Dict, Callable, Any, Optional

class BatchPopup(QDialog):
    """批量修改悬浮弹出层"""

    def __init__(self, master, submissions: List[Dict], on_update: Callable[[str, Any], None]):
        super().__init__(master)
        
        self.submissions = submissions
        self.on_update = on_update
        
        # 1. 基础配置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 380)
        
        # 2. UI 布局
        self._init_ui()
        
        # 3. 定位到鼠标位置
        self._position_to_mouse()

    def _init_ui(self):
        # 主容器（圆角卡片效果）
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.card = QFrame()
        self.card.setObjectName("BatchCard")
        self.card.setStyleSheet(f"""
            QFrame#BatchCard {{
                background-color: {palette.SURFACE};
                border: 1px solid {palette.BORDER};
                border-radius: 12px;
            }}
        """)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        
        # 4. 标题栏
        header = QFrame()
        header.setFixedHeight(45)
        header.setStyleSheet(f"background-color: {palette.BORDER}; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 10, 0)
        
        title_label = QLabel(f"批量修改 ({len(self.submissions)} 项)")
        title_label.setStyleSheet(f"color: {palette.TEXT_PRIMARY}; font-weight: bold; font-size: 13px; border: none;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {palette.TEXT_SECONDARY};
                background-color: transparent;
                border: none;
                font-size: 16px;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: #FF4D4F;
                color: white;
            }}
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        card_layout.addWidget(header)
        
        # 5. 堆栈视图
        self.stack = QStackedWidget()
        
        # 视图1：字段选择列表
        self.field_list_view = self._create_field_list_view()
        self.stack.addWidget(self.field_list_view)
        
        # 视图2：编辑视图（动态更新）
        self.edit_view = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_view)
        self.stack.addWidget(self.edit_view)
        
        card_layout.addWidget(self.stack)
        self.main_layout.addWidget(self.card)

    def _create_field_list_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        hint = QLabel("选择要修改的字段:")
        hint.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 12px; border: none;")
        layout.addWidget(hint)
        
        fields = [
            ("学号", "student_id", "text"),
            ("姓名", "name", "text"),
            ("作业名称", "assignment_name", "dropdown"),
            ("状态", "status", "dropdown")
        ]
        
        for label, field_id, field_type in fields:
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {palette.TEXT_PRIMARY};
                    border: 1px solid {palette.BORDER};
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 15px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {palette.BORDER};
                    border-color: {palette.PRIMARY};
                }}
            """)
            btn.clicked.connect(lambda checked=False, l=label, i=field_id, t=field_type: self._show_edit_view(l, i, t))
            layout.addWidget(btn)
        
        layout.addStretch()
        return view

    def _show_edit_view(self, label: str, field_id: str, field_type: str):
        """切换到编辑视图"""
        # 清空旧内容
        while self.edit_layout.count():
            item = self.edit_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.edit_layout.setContentsMargins(20, 20, 20, 20)
        self.edit_layout.setSpacing(15)
        
        # 返回按钮
        back_btn = QPushButton("← 返回列表")
        back_btn.setStyleSheet(f"QPushButton {{ color: {palette.PRIMARY}; background: transparent; border: none; text-align: left; font-size: 12px; }}")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.edit_layout.addWidget(back_btn)
        
        title = QLabel(f"修改 {label} 为:")
        title.setStyleSheet(f"color: {palette.TEXT_PRIMARY}; font-size: 14px; font-weight: bold; margin-top: 10px; border: none;")
        self.edit_layout.addWidget(title)
        
        # 输入控件
        self.input_widget = None
        if field_type == "text":
            self.input_widget = QLineEdit()
            self.input_widget.setPlaceholderText(f"请输入新{label}...")
            self.input_widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {palette.BACKGROUND};
                    border: 1px solid {palette.BORDER};
                    border-radius: 4px;
                    color: {palette.TEXT_PRIMARY};
                    padding: 8px;
                    font-size: 13px;
                }}
                QLineEdit:focus {{ border: 1px solid {palette.PRIMARY}; }}
            """)
            self.edit_layout.addWidget(self.input_widget)
        else:
            self.input_widget = QComboBox()
            values = []
            if field_id == "status":
                if hasattr(self.parent(), 'STATUS_MAP'):
                    values = list(self.parent().STATUS_MAP.values())
                else:
                    values = ["未处理", "识别异常", "下载失败", "未回复", "已完成", "已忽略"]
            elif field_id == "assignment_name":
                try:
                    from database.operations import db
                    assignments = db.get_all_assignments()
                    values = [a.name for a in assignments] if assignments else ["默认作业"]
                except Exception:
                    values = ["默认作业"]
            
            self.input_widget.addItems(values)
            self.input_widget.setStyleSheet(f"""
                QComboBox {{
                    background-color: {palette.BACKGROUND};
                    border: 1px solid {palette.BORDER};
                    border-radius: 4px;
                    color: {palette.TEXT_PRIMARY};
                    padding: 8px;
                    min-height: 20px;
                }}
                QComboBox::drop-down {{ border: none; }}
                QComboBox QAbstractItemView {{
                    background-color: {palette.SURFACE};
                    color: {palette.TEXT_PRIMARY};
                    selection-background-color: {palette.PRIMARY};
                    border: 1px solid {palette.BORDER};
                }}
            """)
            self.edit_layout.addWidget(self.input_widget)
            
        self.edit_layout.addStretch()
        
        # 确认按钮
        confirm_btn = QPushButton(f"确认修改 {len(self.submissions)} 项")
        confirm_btn.setFixedHeight(40)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {palette.SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #69DB7C; }}
            QPushButton:pressed {{ background-color: #2F9E44; }}
        """)
        confirm_btn.clicked.connect(lambda: self._on_confirm(field_id))
        self.edit_layout.addWidget(confirm_btn)
        
        self.stack.setCurrentIndex(1)

    def _on_confirm(self, field_id: str):
        if isinstance(self.input_widget, QLineEdit):
            val = self.input_widget.text().strip()
        else:
            val = self.input_widget.currentText()
            
        if not val and isinstance(self.input_widget, QLineEdit):
            # 简单反馈，实际应用中可以使用更优雅的提示
            self.input_widget.setStyleSheet(self.input_widget.styleSheet() + f"border: 1px solid {palette.ERROR};")
            return
            
        self.on_update(field_id, val)
        self.accept()

    def _position_to_mouse(self):
        """将窗口定位到鼠标位置，并确保不超出屏幕"""
        cursor_pos = self.cursor().pos()
        screen = QApplication.primaryScreen().geometry()
        
        x = cursor_pos.x()
        y = cursor_pos.y()
        
        if x + self.width() > screen.width():
            x = screen.width() - self.width() - 10
        if y + self.height() > screen.height():
            y = screen.height() - self.height() - 10
            
        self.move(x, y)
