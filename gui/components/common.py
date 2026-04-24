from PySide6.QtWidgets import QLabel, QPushButton
from PySide6.QtCore import Qt
from gui.styles import palette

class Badge(QLabel):
    """
    状态标签组件，支持不同颜色类型
    """
    def __init__(self, text="", color_type="primary", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.color_type = color_type
        self._apply_style()
        
    def _apply_style(self):
        bg_color = palette.PRIMARY
        if self.color_type == "success":
            bg_color = palette.SUCCESS
        elif self.color_type == "error":
            bg_color = palette.ERROR
            
        style = f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
                min-width: 40px;
            }}
        """
        self.setStyleSheet(style)
        self.setFixedHeight(20)

class PrimaryButton(QPushButton):
    """
    主操作按钮，符合方案 A 的现代蓝风格
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")
        self.setFixedHeight(36)
        # 样式已经在 theme.qss 中定义，这里可以做一些额外的初始化
