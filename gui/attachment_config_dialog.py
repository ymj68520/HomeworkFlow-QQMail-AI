# gui/attachment_config_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QSpinBox, QPushButton, QLabel, QGroupBox,
    QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import asyncio
from core.attachment_config_manager import AttachmentConfigManager

class AttachmentConfigDialog(QWidget):
    """Attachment configuration dialog"""

    config_updated = pyqtSignal()  # Signal when config is updated

    def __init__(self, config_manager: AttachmentConfigManager):
        super().__init__()
        self.config_mgr = config_manager
        self.setup_ui()
        self.load_current_config()

    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("附件验证规则配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Preset categories group
        preset_group = QGroupBox("预设文件类型")
        preset_layout = QVBoxLayout()

        # Load presets
        presets = self.config_mgr.load_preset_categories()
        self.category_checkboxes = {}

        for cat_name, cat_config in presets.items():
            display_name = cat_config.get('display_name', cat_name)
            checkbox = QCheckBox(display_name)
            checkbox.setObjectName(f"cb_{cat_name}")
            preset_layout.addWidget(checkbox)
            self.category_checkboxes[cat_name] = checkbox

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Custom extensions
        custom_group = QGroupBox("自定义扩展名 (每行一个，如 .xyz)")
        custom_layout = QVBoxLayout()
        self.custom_extensions = QTextEdit()
        self.custom_extensions.setMaximumHeight(100)
        self.custom_extensions.setPlaceholderText(".xyz\n.abc")
        custom_layout.addWidget(self.custom_extensions)
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        # Size limits
        size_group = QGroupBox("大小限制")
        size_layout = QVBoxLayout()

        # Max file size
        file_size_layout = QHBoxLayout()
        file_size_layout.addWidget(QLabel("单文件最大大小:"))
        self.max_file_size = QSpinBox()
        self.max_file_size.setRange(1, 500)
        self.max_file_size.setSuffix(" MB")
        self.max_file_size.setValue(25)
        file_size_layout.addWidget(self.max_file_size)
        file_size_layout.addStretch()
        size_layout.addLayout(file_size_layout)

        # Max total size
        total_size_layout = QHBoxLayout()
        total_size_layout.addWidget(QLabel("总大小最大值:"))
        self.max_total_size = QSpinBox()
        self.max_total_size.setRange(1, 1000)
        self.max_total_size.setSuffix(" MB")
        self.max_total_size.setValue(100)
        total_size_layout.addWidget(self.max_total_size)
        total_size_layout.addStretch()
        size_layout.addLayout(total_size_layout)

        size_group.setLayout(size_layout)
        layout.addWidget(size_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.clicked.connect(self.on_save)
        button_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("重置为默认")
        self.reset_btn.clicked.connect(self.on_reset)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()

    def load_current_config(self):
        """Load current configuration from database"""
        # This needs to be async, so we'll use a separate method
        asyncio.create_task(self._load_config_async())

    async def _load_config_async(self):
        """Load configuration asynchronously"""
        try:
            rules = await self.config_mgr.get_current_rules()
            if rules:
                import json
                allowed_exts = json.loads(rules.allowed_extensions)

                # Update size limits
                self.max_file_size.setValue(int(rules.max_file_size_mb))
                self.max_total_size.setValue(int(rules.max_total_size_mb))

                # Update checkboxes based on current rules
                presets = self.config_mgr.load_preset_categories()
                for cat_name, checkbox in self.category_checkboxes.items():
                    cat_exts = presets[cat_name]['extensions']
                    # Check if all extensions in this category are allowed
                    all_allowed = all(ext in allowed_exts for ext in cat_exts)
                    checkbox.setChecked(all_allowed)
        except Exception as e:
            print(f"Error loading config: {e}")

    def on_save(self):
        """Save configuration"""
        asyncio.create_task(self._save_config_async())

    async def _save_config_async(self):
        """Save configuration asynchronously"""
        try:
            # Collect allowed extensions
            allowed_exts = []

            # From presets
            presets = self.config_mgr.load_preset_categories()
            for cat_name, checkbox in self.category_checkboxes.items():
                if checkbox.isChecked():
                    allowed_exts.extend(presets[cat_name]['extensions'])

            # From custom input
            custom_text = self.custom_extensions.toPlainText().strip()
            if custom_text:
                for line in custom_text.split('\n'):
                    ext = line.strip()
                    if ext and ext not in allowed_exts:
                        allowed_exts.append(ext)

            # Update rules
            success = await self.config_mgr.update_rules(
                allowed_extensions=allowed_exts,
                max_file_size_mb=float(self.max_file_size.value()),
                max_total_size_mb=float(self.max_total_size.value())
            )

            if success:
                QMessageBox.information(self, "成功", "配置已保存并应用")
                self.config_updated.emit()
            else:
                QMessageBox.critical(self, "错误", "保存配置失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置时出错: {e}")

    def on_reset(self):
        """Reset to default configuration"""
        reply = QMessageBox.question(
            self, "确认", "确定要重置为默认配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self._reset_config_async())

    async def _reset_config_async(self):
        """Reset configuration asynchronously"""
        try:
            # Get defaults from YAML
            import json
            presets = self.config_mgr.load_preset_categories()

            # Get default enabled categories
            default_exts = []
            for cat_name in ['document', 'image', 'archive']:
                if cat_name in presets:
                    default_exts.extend(presets[cat_name]['extensions'])

            # Reset to defaults
            success = await self.config_mgr.update_rules(
                allowed_extensions=default_exts,
                max_file_size_mb=25.0,
                max_total_size_mb=100.0
            )

            if success:
                QMessageBox.information(self, "成功", "已重置为默认配置")
                # Reload UI
                await self._load_config_async()
            else:
                QMessageBox.critical(self, "错误", "重置配置失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重置配置时出错: {e}")