# tests/unit/test_attachment_config_manager.py
import pytest
import yaml
import tempfile
from pathlib import Path
from core.attachment_config_manager import AttachmentConfigManager

@pytest.fixture
def temp_yaml_file():
    """Create a temporary YAML config file"""
    config_content = """
categories:
  document:
    display_name: "文档"
    extensions: [.pdf, .doc]
  image:
    display_name: "图片"
    extensions: [.png, .jpg]

default_enabled_categories:
  - document
  - image

default_size_limits:
  max_file_size_mb: 25
  max_total_size_mb: 100
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()

def test_load_preset_categories_from_file(temp_yaml_file):
    """Test loading preset categories from YAML file"""
    manager = AttachmentConfigManager(presets_config_path=temp_yaml_file)
    presets = manager.load_preset_categories()

    assert 'document' in presets
    assert 'image' in presets
    assert presets['document']['display_name'] == "文档"
    assert '.pdf' in presets['document']['extensions']
    assert '.png' in presets['image']['extensions']

def test_load_preset_categories_fallback_to_builtin():
    """Test fallback to builtin presets when file doesn't exist"""
    manager = AttachmentConfigManager(
        presets_config_path=Path('/nonexistent/path.yaml')
    )
    presets = manager.load_preset_categories()

    # Should have builtin defaults
    assert 'document' in presets
    assert 'image' in presets
    assert 'archive' in presets

def test_get_preset_extensions(temp_yaml_file):
    """Test getting extensions for specific categories"""
    manager = AttachmentConfigManager(presets_config_path=temp_yaml_file)
    extensions = manager.get_preset_extensions(['document', 'image'])

    assert '.pdf' in extensions
    assert '.doc' in extensions
    assert '.png' in extensions
    assert '.jpg' in extensions

def test_reload_presets(temp_yaml_file):
    """Test reloading presets"""
    manager = AttachmentConfigManager(presets_config_path=temp_yaml_file)

    # Initial load
    presets1 = manager.load_preset_categories()
    assert presets1 is not None

    # Modify file
    config_content = """
categories:
  test:
    display_name: "测试"
    extensions: [.xyz]
"""
    with open(temp_yaml_file, 'w') as f:
        f.write(config_content)

    # Reload
    manager.reload_presets()
    presets2 = manager.load_preset_categories()

    # Should have new content
    assert 'test' in presets2
    assert presets2['test']['extensions'] == ['.xyz']

def test_validate_presets_file(temp_yaml_file):
    """Test YAML file validation"""
    manager = AttachmentConfigManager(presets_config_path=temp_yaml_file)
    result = manager.validate_presets_file()

    assert result['is_valid'] is True
    assert len(result['errors']) == 0

def test_validate_presets_file_invalid_yaml():
    """Test validation with invalid YAML"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_path = Path(f.name)

    manager = AttachmentConfigManager(presets_config_path=temp_path)
    result = manager.validate_presets_file()

    assert result['is_valid'] is False
    assert len(result['errors']) > 0

    temp_path.unlink()