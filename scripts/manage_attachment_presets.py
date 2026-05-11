#!/usr/bin/env python3
"""Attachment preset configuration management tool

Usage:
    python scripts/manage_attachment_presets.py validate    # Validate config file
    python scripts/manage_attachment_presets.py show        # Show current config
    python scripts/manage_attachment_presets.py edit        # Open editor to edit config
    python scripts/manage_attachment_presets.py restore     # Restore default config
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def validate_config():
    """Validate config file format"""
    from core.attachment_config_manager import AttachmentConfigManager

    mgr = AttachmentConfigManager()
    result = mgr.validate_presets_file()

    if result['is_valid']:
        print("[PASS] Config file format is valid")
        if result['warnings']:
            print("\nWarnings:")
            for w in result['warnings']:
                print(f"  - {w}")
        return 0
    else:
        print("[FAIL] Config file format errors:")
        for e in result['errors']:
            print(f"  - {e}")
        return 1

def show_config():
    """Show current configuration"""
    from core.attachment_config_manager import AttachmentConfigManager

    mgr = AttachmentConfigManager()
    presets = mgr.load_preset_categories()

    print("Current preset categories:")
    for cat_name, cat_config in presets.items():
        display_name = cat_config.get('display_name', cat_name)
        extensions = ', '.join(cat_config['extensions'])
        print(f"\n  [{cat_name}] {display_name}")
        print(f"    Extensions: {extensions}")

    return 0

def edit_config():
    """Open editor to edit config"""
    import subprocess
    from core.attachment_config_manager import AttachmentConfigManager

    mgr = AttachmentConfigManager()
    config_path = mgr.presets_config_path

    # Create file if it doesn't exist
    if not config_path.exists():
        print(f"Config file doesn't exist, creating: {config_path}")
        create_default_config(config_path)

    # Open default editor
    try:
        if sys.platform == 'win32':
            os.startfile(str(config_path))
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(config_path)])
        else:
            subprocess.run(['xdg-open', str(config_path)])
        print(f"Opened config file: {config_path}")
        return 0
    except Exception as e:
        print(f"Failed to open config file: {e}")
        return 1

def create_default_config(path: Path):
    """Create default config file"""
    default_content = """# Attachment validation preset categories configuration
# Users can modify these presets to customize allowed file types

categories:
  document:
    display_name: "文档类型"
    extensions:
      - .pdf
      - .doc
      - .docx
      - .xls
      - .xlsx
      - .ppt
      - .pptx
      - .txt

  image:
    display_name: "图片类型"
    extensions:
      - .png
      - .jpg
      - .jpeg
      - .gif
      - .bmp
      - .webp

  archive:
    display_name: "压缩文件"
    extensions:
      - .zip
      - .rar
      - .7z
      - .tar
      - .gz

default_enabled_categories:
  - document
  - image
  - archive

default_size_limits:
  max_file_size_mb: 25
  max_total_size_mb: 100
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(default_content)
    print(f"Created default config file: {path}")

def restore_config():
    """Restore default config"""
    from core.attachment_config_manager import AttachmentConfigManager

    mgr = AttachmentConfigManager()
    create_default_config(mgr.presets_config_path)
    print("Restored default config")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    commands = {
        'validate': validate_config,
        'show': show_config,
        'edit': edit_config,
        'restore': restore_config
    }

    if command in commands:
        sys.exit(commands[command]())
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)