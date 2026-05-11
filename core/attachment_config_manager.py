# core/attachment_config_manager.py
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional
from database.models import AttachmentValidationRule
from database.async_operations import AsyncDatabaseOperations

class AttachmentConfigManager:
    """Attachment configuration manager - supports runtime dynamic configuration"""

    # Built-in default presets (used when config file doesn't exist)
    BUILTIN_PRESETS = {
        'document': {
            'display_name': '文档类型',
            'extensions': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
        },
        'image': {
            'display_name': '图片类型',
            'extensions': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
        },
        'archive': {
            'display_name': '压缩文件',
            'extensions': ['.zip', '.rar', '.7z', '.tar', '.gz']
        }
    }

    def __init__(self, presets_config_path: Optional[Path] = None):
        if presets_config_path is None:
            presets_config_path = Path(__file__).parent.parent / 'config' / 'attachment_presets.yaml'

        self.presets_config_path = presets_config_path
        self._rules_cache = None
        self._rules_cache_time = None
        self._presets_cache = None

    def load_preset_categories(self) -> Dict[str, dict]:
        """
        Load preset categories from external YAML config file

        Returns:
            {
                'document': {
                    'display_name': '文档类型',
                    'extensions': ['.pdf', '.doc', ...]
                },
                ...
            }
        """
        # Return cached if available
        if self._presets_cache is not None:
            return self._presets_cache

        # Try to load from external config file
        if self.presets_config_path.exists():
            try:
                with open(self.presets_config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self._presets_cache = config.get('categories', {})
                    print(f"[AttachmentConfig] Loaded presets from {self.presets_config_path}")
                    return self._presets_cache
            except Exception as e:
                print(f"[AttachmentConfig] Failed to load presets file: {e}")
                print(f"[AttachmentConfig] Falling back to builtin presets")

        # File doesn't exist or load failed, use builtin defaults
        self._presets_cache = self.BUILTIN_PRESETS
        print(f"[AttachmentConfig] Using builtin presets")
        return self._presets_cache

    def get_preset_extensions(self, category_names: List[str]) -> List[str]:
        """
        Get extension list for specified category names

        Args:
            category_names: List of category names, e.g. ['document', 'image']

        Returns:
            List of extensions, e.g. ['.pdf', '.doc', '.png', ...]
        """
        presets = self.load_preset_categories()
        extensions = []

        for name in category_names:
            if name in presets:
                extensions.extend(presets[name]['extensions'])

        return extensions

    def reload_presets(self):
        """
        Reload preset configuration (used after config file is modified)

        Use cases:
        1. User manually edited the YAML file
        2. GUI provides a "reload config" button
        """
        self._presets_cache = None
        print(f"[AttachmentConfig] Presets reloaded from {self.presets_config_path}")

    def validate_presets_file(self) -> dict:
        """
        Validate preset config file format

        Returns:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str]
            }
        """
        result = {'is_valid': True, 'errors': [], 'warnings': []}

        if not self.presets_config_path.exists():
            result['errors'].append(f"Config file not found: {self.presets_config_path}")
            result['is_valid'] = False
            return result

        try:
            with open(self.presets_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Validate required top-level fields
            if 'categories' not in config:
                result['errors'].append("Missing required field: categories")
                result['is_valid'] = False

            # Validate category format
            if 'categories' in config:
                for cat_name, cat_config in config['categories'].items():
                    if not isinstance(cat_config, dict):
                        result['errors'].append(f"Category '{cat_name}' format error: should be object")
                        result['is_valid'] = False
                        continue

                    if 'extensions' not in cat_config:
                        result['errors'].append(f"Category '{cat_name}' missing 'extensions' field")
                        result['is_valid'] = False
                    elif not isinstance(cat_config['extensions'], list):
                        result['errors'].append(f"Category '{cat_name}' 'extensions' should be array")
                        result['is_valid'] = False

                    if 'display_name' not in cat_config:
                        result['warnings'].append(f"Category '{cat_name}' missing 'display_name' field")

        except yaml.YAMLError as e:
            result['errors'].append(f"YAML parse error: {e}")
            result['is_valid'] = False
        except Exception as e:
            result['errors'].append(f"Error reading config file: {e}")
            result['is_valid'] = False

        return result