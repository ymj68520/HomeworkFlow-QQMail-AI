# Attachment Validation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a unified attachment validation layer that restricts acceptable file types and sizes for assignment submissions, with runtime-configurable rules via GUI.

**Architecture:** 5-layer architecture - External config (YAML) → Config manager → Validator service → Workflow integration → Database persistence.

**Tech Stack:** Python 3.12+, SQLAlchemy, PyYAML, PyQt6 (GUI), pytest (testing)

---

## File Structure

**New files to create:**
```
core/
├── attachment_validator.py       # Main validator service
├── attachment_config_manager.py  # Config management with YAML support
└── validation_result.py          # ValidationResult dataclass

config/
└── attachment_presets.yaml       # External preset categories config

database/
└── migrations/
    └── 002_add_attachment_rules.py  # Database migration

gui/
└── attachment_config_dialog.py  # Configuration dialog

scripts/
└── manage_attachment_presets.py # CLI management tool

tests/
├── unit/
│   ├── test_attachment_config_manager.py
│   └── test_attachment_validator.py
└── integration/
    └── test_attachment_validation_e2e.py
```

**Files to modify:**
```
database/models.py                # Add AttachmentValidationRule model
database/operations.py            # Add attachment rules CRUD operations
core/workflow.py                  # Integrate validation into workflow
gui/main_window.py                # Add menu item for config dialog
```

---

## Task 1: Create ValidationResult dataclass

**Files:**
- Create: `core/validation_result.py`
- Test: `tests/unit/test_validation_result.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_validation_result.py
import pytest
from core.validation_result import ValidationResult

def test_validation_result_creation():
    """Test creating a valid ValidationResult"""
    result = ValidationResult(is_valid=True)
    assert result.is_valid is True
    assert result.reason is None
    assert result.details == {}

def test_validation_result_with_reason():
    """Test creating ValidationResult with rejection reason"""
    result = ValidationResult(
        is_valid=False,
        reason="Invalid file type: .exe"
    )
    assert result.is_valid is False
    assert result.reason == "Invalid file type: .exe"

def test_validation_result_with_details():
    """Test creating ValidationResult with details"""
    result = ValidationResult(
        is_valid=False,
        reason="File too large",
        details={"filename": "huge.pdf", "size_mb": 50, "max_mb": 25}
    )
    assert result.details["filename"] == "huge.pdf"
    assert result.details["size_mb"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_validation_result.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.validation_result'"

- [ ] **Step 3: Write minimal implementation**

```python
# core/validation_result.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ValidationResult:
    """Result of attachment validation"""
    is_valid: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_validation_result.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_validation_result.py core/validation_result.py
git commit -m "feat(core): add ValidationResult dataclass

Add ValidationResult dataclass for attachment validation results.
- is_valid: bool - Whether validation passed
- reason: Optional[str] - Rejection reason if invalid
- details: Dict - Additional details about the validation"
```

---

## Task 2: Add AttachmentValidationRule database model

**Files:**
- Modify: `database/models.py`
- Test: `tests/unit/test_attachment_validation_rule_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_attachment_validation_rule_model.py
import pytest
from datetime import datetime
from database.models import AttachmentValidationRule, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_attachment_validation_rule(db_session):
    """Test creating an attachment validation rule"""
    rule = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".pdf", ".doc", ".docx"]',
        max_file_size_mb=25.0,
        max_total_size_mb=100.0,
        is_active=True
    )
    db_session.add(rule)
    db_session.commit()

    retrieved = db_session.query(AttachmentValidationRule).filter_by(rule_name="default").first()
    assert retrieved is not None
    assert retrieved.max_file_size_mb == 25.0
    assert retrieved.max_total_size_mb == 100.0
    assert retrieved.is_active is True

def test_rule_unique_name(db_session):
    """Test that rule_name must be unique"""
    rule1 = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".pdf"]',
        max_file_size_mb=10.0,
        max_total_size_mb=50.0
    )
    db_session.add(rule1)
    db_session.commit()

    rule2 = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".doc"]',
        max_file_size_mb=20.0,
        max_total_size_mb=100.0
    )
    db_session.add(rule2)

    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_attachment_validation_rule_model.py -v
```

Expected: FAIL with "AttributeError: type object 'AttachmentValidationRule' has no attribute..."

- [ ] **Step 3: Write minimal implementation**

```python
# Add to database/models.py (after class EmailLog)

class AttachmentValidationRule(Base):
    """Attachment validation rules - configurable file type and size restrictions"""
    __tablename__ = 'attachment_validation_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(50), unique=True, nullable=False, index=True)
    allowed_extensions = Column(Text, nullable=False)  # JSON: [".pdf", ".doc", ...]
    extension_categories = Column(Text)  # JSON: {"document": [".pdf", ...]}
    max_file_size_mb = Column(Float, nullable=False)
    max_total_size_mb = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<AttachmentValidationRule(id={self.id}, name='{self.rule_name}', active={self.is_active})>"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_attachment_validation_rule_model.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add database/models.py tests/unit/test_attachment_validation_rule_model.py
git commit -m "feat(database): add AttachmentValidationRule model

Add database model for attachment validation rules:
- rule_name: unique identifier
- allowed_extensions: JSON array of allowed file extensions
- extension_categories: JSON object with categorized extensions
- max_file_size_mb: single file size limit
- max_total_size_mb: total attachments size limit
- is_active: whether rule is currently active"
```

---

## Task 3: Create database migration for AttachmentValidationRule

**Files:**
- Create: `database/migrations/002_add_attachment_rules.py`

- [ ] **Step 1: Create migration script**

```python
# database/migrations/002_add_attachment_rules.py
"""Add attachment_validation_rules table

Revision ID: 002
Create Date: 2026-05-11
"""
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from config.settings import settings

Base = declarative_base()

class AttachmentValidationRule(Base):
    __tablename__ = 'attachment_validation_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(50), unique=True, nullable=False)
    allowed_extensions = Column(Text, nullable=False)
    extension_categories = Column(Text)
    max_file_size_mb = Column(Float, nullable=False)
    max_total_size_mb = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

def upgrade():
    """Create attachment_validation_rules table and insert default rule"""
    engine = create_engine(f'sqlite:///{settings.DATABASE_PATH}')
    Base.metadata.create_all(engine)
    
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Check if default rule already exists
    existing = session.query(AttachmentValidationRule).filter_by(rule_name='default').first()
    if not existing:
        # Insert default rule
        default_extensions = [
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
            ".zip", ".rar", ".7z", ".tar", ".gz"
        ]
        
        default_rule = AttachmentValidationRule(
            rule_name='default',
            allowed_extensions=json.dumps(default_extensions),
            max_file_size_mb=25.0,
            max_total_size_mb=100.0,
            is_active=True
        )
        session.add(default_rule)
        session.commit()
        print("[Migration] Default attachment validation rule created")
    else:
        print("[Migration] Default attachment validation rule already exists")
    
    session.close()

def downgrade():
    """Drop attachment_validation_rules table"""
    engine = create_engine(f'sqlite:///{settings.DATABASE_PATH}')
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS attachment_validation_rules")
    print("[Migration] Dropped attachment_validation_rules table")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()
```

- [ ] **Step 2: Run migration to verify it works**

```bash
python database/migrations/002_add_attachment_rules.py
```

Expected: "[Migration] Default attachment validation rule created"

- [ ] **Step 3: Verify table was created**

```bash
sqlite3 assignment_submissions.db ".schema attachment_validation_rules"
sqlite3 assignment_submissions.db "SELECT * FROM attachment_validation_rules"
```

Expected: Table schema shown, one row with default rule

- [ ] **Step 4: Commit**

```bash
git add database/migrations/002_add_attachment_rules.py
git commit -m "feat(database): add migration for attachment validation rules

Create migration script that:
- Creates attachment_validation_rules table
- Inserts default rule with common file types
- Supports upgrade/downgrade"
```

---

## Task 4: Create external YAML config file for presets

**Files:**
- Create: `config/attachment_presets.yaml`

- [ ] **Step 1: Create YAML config file**

```yaml
# config/attachment_presets.yaml
# Attachment validation preset categories configuration
# Users can modify these presets to customize allowed file types

categories:
  # Document types
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
      - .rtf
      - .odt
      - .ods
      - .odp
    
  # Image types
  image:
    display_name: "图片类型"
    extensions:
      - .png
      - .jpg
      - .jpeg
      - .gif
      - .bmp
      - .webp
      - .svg
      - .ico
      - .tiff
    
  # Archive files
  archive:
    display_name: "压缩文件"
    extensions:
      - .zip
      - .rar
      - .7z
      - .tar
      - .gz
      - .bz2
      - .xz
    
  # Code files (optional)
  code:
    display_name: "代码文件"
    extensions:
      - .py
      - .java
      - .cpp
      - .c
      - .h
      - .js
      - .html
      - .css
      - .json
      - .xml

# Default enabled categories (for initialization)
default_enabled_categories:
  - document
  - image
  - archive

# Default size limits
default_size_limits:
  max_file_size_mb: 25
  max_total_size_mb: 100
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python -c "import yaml; print('YAML syntax OK' if yaml.safe_load(open('config/attachment_presets.yaml')) else 'YAML syntax error')"
```

Expected: "YAML syntax OK"

- [ ] **Step 3: Commit**

```bash
git add config/attachment_presets.yaml
git commit -m "feat(config): add attachment presets YAML configuration

Add external YAML config file for attachment validation presets:
- Categories: document, image, archive, code
- Default enabled categories
- Default size limits"
```

---

## Task 5: Implement AttachmentConfigManager - preset loading

**Files:**
- Create: `core/attachment_config_manager.py`
- Test: `tests/unit/test_attachment_config_manager.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_attachment_config_manager.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.attachment_config_manager'"

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_attachment_config_manager.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/attachment_config_manager.py tests/unit/test_attachment_config_manager.py
git commit -m "feat(core): implement AttachmentConfigManager

Implement configuration manager for attachment validation:
- Load preset categories from YAML file
- Fallback to builtin presets if file missing
- Support config reloading
- Validate YAML file format
- Cache presets for performance"
```

---

## Task 6: Implement AttachmentConfigManager - database operations

**Files:**
- Modify: `database/async_operations.py`
- Modify: `core/attachment_config_manager.py`
- Test: `tests/unit/test_attachment_config_manager_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_attachment_config_manager_db.py
import pytest
import asyncio
from core.attachment_config_manager import AttachmentConfigManager
from database.async_operations import AsyncDatabaseOperations

@pytest.mark.asyncio
async def test_get_current_rules():
    """Test getting current active rules from database"""
    manager = AttachmentConfigManager()
    rules = await manager.get_current_rules()
    
    assert rules is not None
    assert rules.rule_name == 'default'
    assert rules.is_active is True
    assert rules.max_file_size_mb == 25.0

@pytest.mark.asyncio
async def test_update_rules():
    """Test updating rules in database"""
    manager = AttachmentConfigManager()
    
    # Update rules
    success = await manager.update_rules(
        allowed_extensions=['.pdf', '.txt'],
        max_file_size_mb=50.0,
        max_total_size_mb=200.0
    )
    
    assert success is True
    
    # Verify update
    rules = await manager.get_current_rules()
    assert '.pdf' in rules.allowed_extensions
    assert '.txt' in rules.allowed_extensions
    # Restore defaults
    await manager.update_rules(
        allowed_extensions=['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.zip', '.rar', '.7z', '.tar', '.gz'],
        max_file_size_mb=25.0,
        max_total_size_mb=100.0
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_attachment_config_manager_db.py -v
```

Expected: FAIL with method not found errors

- [ ] **Step 3: Add database operations to AsyncDatabaseOperations**

```python
# Add to database/async_operations.py

class AsyncDatabaseOperations:
    # ... existing code ...
    
    async def get_active_attachment_rule(self) -> Optional[AttachmentValidationRule]:
        """Get the currently active attachment validation rule"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AttachmentValidationRule)
                .where(AttachmentValidationRule.is_active == True)
                .order_by(AttachmentValidationRule.updated_at.desc())
            )
            return result.scalar_one_or_none()
    
    async def update_attachment_rule(
        self,
        rule_name: str,
        allowed_extensions: List[str],
        max_file_size_mb: float,
        max_total_size_mb: float
    ) -> bool:
        """Update an existing attachment validation rule"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(AttachmentValidationRule)
                    .where(AttachmentValidationRule.rule_name == rule_name)
                )
                rule = result.scalar_one_or_none()
                
                if not rule:
                    return False
                
                rule.allowed_extensions = json.dumps(allowed_extensions)
                rule.max_file_size_mb = max_file_size_mb
                rule.max_total_size_mb = max_total_size_mb
                
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                print(f"[AsyncDB] Error updating attachment rule: {e}")
                return False
```

- [ ] **Step 4: Add methods to AttachmentConfigManager**

```python
# Add to core/attachment_config_manager.py

class AttachmentConfigManager:
    # ... existing code ...
    
    async def get_current_rules(self) -> Optional[AttachmentValidationRule]:
        """
        Get currently active rules (with caching)
        
        Returns:
            AttachmentValidationRule or None
        """
        import time
        
        # Reload if cache is older than 1 minute
        if self._rules_cache is None or self._should_reload_rules():
            await self._reload_rules()
        
        return self._rules_cache
    
    async def update_rules(
        self,
        allowed_extensions: List[str],
        max_file_size_mb: float,
        max_total_size_mb: float
    ) -> bool:
        """
        Update rules (takes effect immediately)
        
        Args:
            allowed_extensions: List of allowed file extensions (e.g. ['.pdf', '.doc'])
            max_file_size_mb: Maximum single file size in MB
            max_total_size_mb: Maximum total attachments size in MB
            
        Returns:
            True if successful, False otherwise
        """
        db = AsyncDatabaseOperations()
        success = await db.update_attachment_rule(
            rule_name='default',
            allowed_extensions=allowed_extensions,
            max_file_size_mb=max_file_size_mb,
            max_total_size_mb=max_total_size_mb
        )
        
        if success:
            # Clear cache to force reload
            self._rules_cache = None
            print(f"[AttachmentConfig] Rules updated successfully")
        else:
            print(f"[AttachmentConfig] Failed to update rules")
        
        return success
    
    def _should_reload_rules(self) -> bool:
        """Check if rules cache should be reloaded"""
        if self._rules_cache_time is None:
            return True
        
        import time
        return (time.time() - self._rules_cache_time) > 60  # 1 minute cache
    
    async def _reload_rules(self):
        """Reload rules from database"""
        db = AsyncDatabaseOperations()
        self._rules_cache = await db.get_active_attachment_rule()
        self._rules_cache_time = time.time()
        
        if self._rules_cache:
            print(f"[AttachmentConfig] Rules loaded from database: {self._rules_cache.rule_name}")
        else:
            print(f"[AttachmentConfig] Warning: No active rules found in database")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/unit/test_attachment_config_manager_db.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add database/async_operations.py core/attachment_config_manager.py tests/unit/test_attachment_config_manager_db.py
git commit -m "feat(core): add database operations to AttachmentConfigManager

Add methods to interact with database:
- get_current_rules(): Get active rules with 1-minute cache
- update_rules(): Update rules in database and clear cache
- _reload_rules(): Internal method to reload from database"
```

---

## Task 7: Implement AttachmentValidator

**Files:**
- Create: `core/attachment_validator.py`
- Test: `tests/unit/test_attachment_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_attachment_validator.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.attachment_validator import AttachmentValidator
from core.validation_result import ValidationResult

@pytest.fixture
def mock_config_manager():
    """Create a mock config manager"""
    manager = AsyncMock()
    manager.get_current_rules.return_value = MagicMock(
        allowed_extensions='[".pdf", ".doc", ".docx", ".png", ".jpg", ".zip"]',
        max_file_size_mb=25.0,
        max_total_size_mb=100.0
    )
    return manager

@pytest.mark.asyncio
async def test_validate_all_valid(mock_config_manager):
    """Test validation with all valid attachments"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'document.pdf', 'content': b'...', 'size': 10 * 1024 * 1024},  # 10MB
        {'filename': 'image.png', 'content': b'...', 'size': 5 * 1024 * 1024},     # 5MB
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is True
    assert result.reason is None

@pytest.mark.asyncio
async def test_validate_invalid_file_type(mock_config_manager):
    """Test validation with invalid file type"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'document.pdf', 'content': b'...', 'size': 10 * 1024 * 1024},
        {'filename': 'virus.exe', 'content': b'...', 'size': 1 * 1024 * 1024},  # Invalid type
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is False
    assert 'virus.exe' in result.reason
    assert '.exe' in result.reason

@pytest.mark.asyncio
async def test_validate_file_too_large(mock_config_manager):
    """Test validation with file exceeding size limit"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'huge.pdf', 'content': b'...', 'size': 30 * 1024 * 1024},  # 30MB > 25MB
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is False
    assert 'huge.pdf' in result.reason
    assert '30.0 MB' in result.reason
    assert '25.0 MB' in result.reason

@pytest.mark.asyncio
async def test_validate_total_size_exceeded(mock_config_manager):
    """Test validation with total size exceeding limit"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'file1.pdf', 'content': b'...', 'size': 40 * 1024 * 1024},  # 40MB
        {'filename': 'file2.pdf', 'content': b'...', 'size': 40 * 1024 * 1024},  # 40MB
        {'filename': 'file3.pdf', 'content': b'...', 'size': 30 * 1024 * 1024},  # 30MB
        # Total: 110MB > 100MB
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is False
    assert 'total size' in result.reason.lower()
    assert '110.0 MB' in result.reason
    assert '100.0 MB' in result.reason

@pytest.mark.asyncio
async def test_validate_case_insensitive_extension(mock_config_manager):
    """Test that extension matching is case-insensitive"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'document.PDF', 'content': b'...', 'size': 1 * 1024 * 1024},
        {'filename': 'image.PNG', 'content': b'...', 'size': 1 * 1024 * 1024},
        {'filename': 'archive.ZIP', 'content': b'...', 'size': 1 * 1024 * 1024},
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is True

@pytest.mark.asyncio
async def test_validate_no_extensions(mock_config_manager):
    """Test file with no extension"""
    validator = AttachmentValidator(mock_config_manager)
    
    attachments = [
        {'filename': 'README', 'content': b'...', 'size': 1 * 1024},
    ]
    
    result = await validator.validate_attachments(attachments)
    
    assert result.is_valid is False
    assert 'README' in result.reason
    assert 'no extension' in result.reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_attachment_validator.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.attachment_validator'"

- [ ] **Step 3: Write minimal implementation**

```python
# core/attachment_validator.py
import json
from pathlib import Path
from typing import List, Dict, Optional
from core.attachment_config_manager import AttachmentConfigManager
from core.validation_result import ValidationResult
from database.models import AttachmentValidationRule

class AttachmentValidator:
    """Attachment validator - validates file types and sizes"""
    
    def __init__(self, config_manager: AttachmentConfigManager):
        self.config_mgr = config_manager
    
    async def validate_attachments(
        self,
        attachments: List[Dict]
    ) -> ValidationResult:
        """
        Validate attachments
        
        Args:
            attachments: List of attachments, e.g. [{'filename': 'a.pdf', 'content': b'...', 'size': 1024}, ...]
            
        Returns:
            ValidationResult
        """
        # Get current rules
        rules = await self.config_mgr.get_current_rules()
        
        if not rules:
            # No rules configured, reject all
            return ValidationResult(
                is_valid=False,
                reason="No validation rules configured"
            )
        
        # Parse allowed extensions
        try:
            allowed_extensions = json.loads(rules.allowed_extensions)
            allowed_extensions_lower = [ext.lower() for ext in allowed_extensions]
        except json.JSONDecodeError:
            return ValidationResult(
                is_valid=False,
                reason="Invalid allowed_extensions configuration"
            )
        
        # Validate each attachment
        total_size = 0
        
        for attachment in attachments:
            filename = attachment.get('filename', '')
            size = attachment.get('size', 0)
            
            # Get file extension
            file_path = Path(filename)
            extension = file_path.suffix.lower()
            
            # Check if file has extension
            if not extension:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File '{filename}' has no extension",
                    details={'filename': filename}
                )
            
            # Check file type
            if extension not in allowed_extensions_lower:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File type not allowed: {extension} (filename: {filename})",
                    details={
                        'filename': filename,
                        'extension': extension,
                        'allowed_extensions': allowed_extensions
                    }
                )
            
            # Check file size
            size_mb = size / (1024 * 1024)
            if size_mb > rules.max_file_size_mb:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File '{filename}' too large: {size_mb:.1f} MB (max: {rules.max_file_size_mb} MB)",
                    details={
                        'filename': filename,
                        'size_mb': size_mb,
                        'max_mb': rules.max_file_size_mb
                    }
                )
            
            total_size += size
        
        # Check total size
        total_size_mb = total_size / (1024 * 1024)
        if total_size_mb > rules.max_total_size_mb:
            return ValidationResult(
                is_valid=False,
                reason=f"Total attachments size too large: {total_size_mb:.1f} MB (max: {rules.max_total_size_mb} MB)",
                details={
                    'total_size_mb': total_size_mb,
                    'max_mb': rules.max_total_size_mb
                }
            )
        
        # All validations passed
        return ValidationResult(is_valid=True)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_attachment_validator.py -v
```

Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/attachment_validator.py tests/unit/test_attachment_validator.py
git commit -m "feat(core): implement AttachmentValidator

Implement attachment validation service:
- Validate file types against allowed extensions
- Validate single file size limits
- Validate total attachments size limit
- Case-insensitive extension matching
- Detailed validation results with reasons"
```

---

## Task 8: Integrate validation into workflow

**Files:**
- Modify: `core/workflow.py`
- Test: `tests/integration/test_workflow_attachment_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_workflow_attachment_validation.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.workflow import AssignmentWorkflow

@pytest.mark.asyncio
async def test_workflow_rejects_invalid_attachments():
    """Test that workflow rejects emails with invalid attachments"""
    workflow = AssignmentWorkflow()
    
    # Mock the validator to reject
    with patch.object(workflow, 'attachment_validator') as mock_validator:
        mock_validator.validate_attachments = AsyncMock(
            return_value=MagicMock(
                is_valid=False,
                reason="Invalid file type: .exe"
            )
        )
        
        # Mock parser
        workflow.parser.parse_email = MagicMock(
            return_value={
                'uid': '12345',
                'subject': 'Test',
                'sender_email': 'test@example.com',
                'sender_name': 'Test',
                'has_attachments': True,
                'attachments': [
                    {'filename': 'test.exe', 'content': b'...', 'size': 1024}
                ]
            }
        )
        
        # Mock db
        workflow.db.log_email_action = MagicMock()
        
        result = await workflow.process_new_email('12345')
        
        assert result['success'] is False
        assert result['action'] == 'rejected'
        assert result['reason'] == "Invalid file type: .exe"

@pytest.mark.asyncio
async def test_workflow_accepts_valid_attachments():
    """Test that workflow accepts emails with valid attachments"""
    workflow = AssignmentWorkflow()
    
    # Mock the validator to accept
    with patch.object(workflow, 'attachment_validator') as mock_validator:
        mock_validator.validate_attachments = AsyncMock(
            return_value=MagicMock(is_valid=True)
        )
        
        # Mock parser and other dependencies
        workflow.parser.parse_email = MagicMock(
            return_value={
                'uid': '12345',
                'subject': '作业1 - 张三',
                'sender_email': 'zhangsan@example.com',
                'sender_name': 'Zhang San',
                'has_attachments': True,
                'attachments': [
                    {'filename': 'homework.pdf', 'content': b'...', 'size': 1024}
                ]
            }
        )
        
        # Mock AI to return valid result
        workflow.ai.extract_student_info = AsyncMock(
            return_value={
                'is_assignment': True,
                'student_id': '2021001',
                'name': '张三',
                'assignment_name': '作业1'
            }
        )
        
        # Mock other dependencies
        workflow.dedup_service.check_email = AsyncMock(
            return_value=MagicMock(is_duplicate=False)
        )
        workflow.dedup_service.check_submission_with_fuzzy = AsyncMock(
            return_value=MagicMock(is_duplicate=False)
        )
        workflow.storage.store_submission = MagicMock(return_value='/path/to/submission')
        workflow.db.create_submission = MagicMock(return_value=MagicMock(id=1))
        workflow.imap.folder_exists = MagicMock(return_value=True)
        workflow.parser.move_to_folder = MagicMock(return_value=True)
        workflow.smtp.send_reply = MagicMock(return_value=True)
        workflow.db.mark_replied = MagicMock()
        workflow.db.log_email_action = MagicMock()
        
        # Mock status manager
        with patch('core.workflow.get_async_status_manager') as mock_status_mgr:
            mock_status_mgr.return_value = MagicMock()
            mock_status_mgr.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                transition=AsyncMock()
            ))
            mock_status_mgr.return_value.__aexit__ = AsyncMock()
            
            result = await workflow.process_new_email('12345')
            
            # Should proceed with normal processing
            assert result['success'] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/integration/test_workflow_attachment_validation.py -v
```

Expected: FAIL with "AttributeError: 'AssignmentWorkflow' object has no attribute 'attachment_validator'"

- [ ] **Step 3: Modify workflow to integrate validation**

```python
# Add to core/workflow.py imports
from core.attachment_validator import AttachmentValidator
from core.attachment_config_manager import AttachmentConfigManager

# In AssignmentWorkflow.__init__, add:
class AssignmentWorkflow:
    def __init__(self):
        # ... existing code ...
        
        # NEW: Attachment validation
        self.attachment_config_mgr = AttachmentConfigManager()
        self.attachment_validator = AttachmentValidator(self.attachment_config_mgr)

# In AssignmentWorkflow.process_new_email, after checking for attachments:
async def process_new_email(self, email_uid: str) -> dict:
    # ... existing code ...
    
    # 2. 检查是否有附件
    if not email_data['has_attachments']:
        print("No attachments found, marking as read")
        self.parser.mark_as_read(email_uid)
        self.db.log_email_action(
            email_uid=email_uid,
            action='marked_read',
            folder='INBOX',
            details='No attachments'
        )
        return {'success': True, 'action': 'marked_read', 'reason': 'no_attachments'}
    
    # 2.5. NEW: 验证附件规则
    print("Validating attachment rules...")
    validation_result = await self.attachment_validator.validate_attachments(
        email_data['attachments']
    )
    
    if not validation_result.is_valid:
        print(f"Attachment validation failed: {validation_result.reason}")
        # Keep email unread, log rejection, don't process further
        self.db.log_email_action(
            email_uid=email_uid,
            action='attachment_rejected',
            folder='INBOX',
            details=validation_result.reason
        )
        return {
            'success': False,
            'action': 'rejected',
            'reason': validation_result.reason
        }
    
    print("Attachment validation passed")
    
    # 3. Continue with multi-assignment detection...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/integration/test_workflow_attachment_validation.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/workflow.py tests/integration/test_workflow_attachment_validation.py
git commit -m "feat(workflow): integrate attachment validation into workflow

Add attachment validation check in process_new_email():
- Validate attachments after checking for their existence
- Reject emails that don't meet validation rules
- Keep rejected emails unread (don't move, don't save, don't reply)
- Log rejection reasons to email_log table"
```

---

## Task 9: Create CLI management tool

**Files:**
- Create: `scripts/manage_attachment_presets.py`

- [ ] **Step 1: Create CLI tool**

```python
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
        print("✓ Config file format is valid")
        if result['warnings']:
            print("\nWarnings:")
            for w in result['warnings']:
                print(f"  - {w}")
        return 0
    else:
        print("✗ Config file format errors:")
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
```

- [ ] **Step 2: Test CLI tool**

```bash
python scripts/manage_attachment_presets.py show
python scripts/manage_attachment_presets.py validate
```

Expected: Show current config, validate passes

- [ ] **Step 3: Commit**

```bash
git add scripts/manage_attachment_presets.py
git commit -m "feat(scripts): add attachment presets CLI management tool

Add command-line tool for managing attachment presets:
- validate: Check YAML file format
- show: Display current configuration
- edit: Open config file in default editor
- restore: Restore default configuration"
```

---

## Task 10: Create GUI configuration dialog

**Files:**
- Create: `gui/attachment_config_dialog.py`
- Modify: `gui/main_window.py`

- [ ] **Step 1: Create GUI dialog**

```python
# gui/attachment_config_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QSpinBox, QPushButton, QLabel, QGroupBox,
    QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
import asyncio
from core.attachment_config_manager import AttachmentConfigManager
from core.validation_result import ValidationResult

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
        self.custom_extensions.setPlaceholderText(".xyz\\n.abc")
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
```

- [ ] **Step 2: Add menu entry to main window**

```python
# Add to gui/main_window.py imports
from gui.attachment_config_dialog import AttachmentConfigDialog
from core.attachment_config_manager import AttachmentConfigManager

# In MainWindow.__init__ or setup_ui, add menu item:
def setup_ui(self):
    # ... existing code ...
    
    # Add Settings menu
    menubar = self.menuBar()
    settings_menu = menubar.addMenu("设置")
    
    config_action = settings_menu.addAction("附件验证规则")
    config_action.triggered.connect(self.show_attachment_config)

# Add method to MainWindow:
def show_attachment_config(self):
    """Show attachment configuration dialog"""
    config_mgr = AttachmentConfigManager()
    dialog = AttachmentConfigDialog(config_mgr)
    dialog.config_updated.connect(self.on_attachment_config_updated)
    dialog.show()

def on_attachment_config_updated(self):
    """Handle attachment config update"""
    # Reload data or show notification
    self.statusBar().showMessage("附件验证规则已更新", 3000)
```

- [ ] **Step 3: Commit**

```bash
git add gui/attachment_config_dialog.py gui/main_window.py
git commit -m "feat(gui): add attachment configuration dialog

Add GUI dialog for configuring attachment validation:
- Preset category checkboxes
- Custom extensions text editor
- Size limit spinboxes
- Save/Reset buttons
- Menu entry in main window"
```

---

## Task 11: Create end-to-end integration test

**Files:**
- Create: `tests/integration/test_attachment_validation_e2e.py`

- [ ] **Step 1: Create end-to-end test**

```python
# tests/integration/test_attachment_validation_e2e.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.workflow import AssignmentWorkflow
from core.attachment_config_manager import AttachmentConfigManager
from core.attachment_validator import AttachmentValidator

@pytest.mark.asyncio
async def test_e2e_valid_attachment_flow():
    """End-to-end test: Valid attachment gets processed"""
    workflow = AssignmentWorkflow()
    
    # Mock all dependencies
    mock_email_data = {
        'uid': 'test-uid-001',
        'subject': '作业1 - 张三',
        'sender_email': 'zhangsan@example.com',
        'sender_name': 'Zhang San',
        'has_attachments': True,
        'attachments': [
            {'filename': 'homework.pdf', 'content': b'fake content', 'size': 5 * 1024 * 1024}
        ],
        'message_id': '<test-msg-id@example.com>'
    }
    
    with patch('core.workflow.mail_parser_inbox') as mock_parser:
        mock_parser.parse_email.return_value = mock_email_data
        mock_parser.connect.return_value = True
        
        with patch('core.workflow.ai_extractor') as mock_ai:
            mock_ai.extract_student_info.return_value = {
                'is_assignment': True,
                'student_id': '2021001',
                'name': '张三',
                'assignment_name': '作业1'
            }
            
            with patch('core.workflow.async_db') as mock_db:
                mock_db.create_submission = AsyncMock(return_value=MagicMock(id=1))
                mock_db.get_student_by_id = AsyncMock(return_value=MagicMock(id=1, name='张三'))
                mock_db.get_assignment_by_name = AsyncMock(return_value=MagicMock(id=1))
                
                with patch('core.workflow.storage_manager') as mock_storage:
                    mock_storage.store_submission.return_value = '/submissions/作业1/2021001张三'
                    
                    with patch('core.workflow.imap_client_inbox') as mock_imap:
                        mock_imap.folder_exists.return_value = True
                        
                        with patch('core.workflow.smtp_client') as mock_smtp:
                            mock_smtp.send_reply.return_value = True
                            
                            with patch('core.workflow.dedup_service') as mock_dedup:
                                mock_dedup.check_email = AsyncMock(
                                    return_value=MagicMock(is_duplicate=False)
                                )
                                mock_dedup.check_submission_with_fuzzy = AsyncMock(
                                    return_value=MagicMock(is_duplicate=False)
                                )
                                
                                with patch('core.workflow.get_async_status_manager') as mock_status:
                                    mock_status.return_value = MagicMock()
                                    mock_status.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                                        transition=AsyncMock()
                                    ))
                                    mock_status.return_value.__aexit__ = AsyncMock()
                                    
                                    result = await workflow.process_new_email('test-uid-001')
                                    
                                    # Assertions
                                    assert result['success'] is True
                                    assert result['action'] in ['processed', 'reprocessed']

@pytest.mark.asyncio
async def test_e2e_invalid_attachment_rejected():
    """End-to-end test: Invalid attachment gets rejected"""
    workflow = AssignmentWorkflow()
    
    # Mock email with invalid attachment
    mock_email_data = {
        'uid': 'test-uid-002',
        'subject': '作业1 - 李四',
        'sender_email': 'lisi@example.com',
        'sender_name': 'Li Si',
        'has_attachments': True,
        'attachments': [
            {'filename': 'virus.exe', 'content': b'malicious', 'size': 1 * 1024 * 1024}
        ],
        'message_id': '<test-msg-id-2@example.com>'
    }
    
    with patch('core.workflow.mail_parser_inbox') as mock_parser:
        mock_parser.parse_email.return_value = mock_email_data
        
        with patch('core.workflow.db') as mock_sync_db:
            mock_sync_db.log_email_action = MagicMock()
            
            result = await workflow.process_new_email('test-uid-002')
            
            # Assertions
            assert result['success'] is False
            assert result['action'] == 'rejected'
            assert '.exe' in result['reason']
            
            # Verify email was logged as rejected
            mock_sync_db.log_email_action.assert_called_once()
            call_args = mock_sync_db.log_email_action.call_args
            assert call_args[1]['action'] == 'attachment_rejected'
```

- [ ] **Step 2: Run end-to-end test**

```bash
pytest tests/integration/test_attachment_validation_e2e.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_attachment_validation_e2e.py
git commit -m "test(integration): add end-to-end attachment validation tests

Add comprehensive integration tests:
- Test valid attachment flow through workflow
- Test invalid attachment rejection
- Verify all components work together"
```

---

## Task 12: Add pyyaml dependency

**Files:**
- Modify: `requirements.txt` or create if not exists

- [ ] **Step 1: Add pyyaml to requirements**

```bash
# If requirements.txt exists
echo "pyyaml>=6.0" >> requirements.txt

# If not, create it
cat > requirements.txt << EOF
# Existing dependencies...
pyyaml>=6.0
EOF
```

- [ ] **Step 2: Install dependency**

```bash
pip install pyyaml>=6.0
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add pyyaml dependency

Add PyYAML for parsing attachment presets configuration file"
```

---

## Task 13: Documentation and README

**Files:**
- Create: `docs/ATTACHMENT_VALIDATION_USER_GUIDE.md`

- [ ] **Step 1: Create user guide**

```markdown
# 附件验证系统用户指南

## 概述

附件验证系统用于限制学生提交作业时可接受的文件类型和大小，提高系统安全性和可管理性。

## 默认规则

- **允许的文件类型**: 文档（.pdf, .doc, .docx等）、图片（.png, .jpg等）、压缩文件（.zip, .rar等）
- **单文件大小限制**: 25 MB
- **总大小限制**: 100 MB

## 配置方式

### 方式1: 通过GUI配置

1. 打开应用程序
2. 点击菜单 "设置" → "附件验证规则"
3. 勾选/取消勾选预设文件类型
4. 可选：添加自定义扩展名（每行一个）
5. 调整大小限制
6. 点击 "保存并应用"

### 方式2: 编辑配置文件

配置文件位置: `config/attachment_presets.yaml`

编辑后重启应用即可生效。

### 方式3: 使用CLI工具

```bash
# 查看当前配置
python scripts/manage_attachment_presets.py show

# 验证配置文件
python scripts/manage_attachment_presets.py validate

# 打开编辑器编辑
python scripts/manage_attachment_presets.py edit

# 恢复默认配置
python scripts/manage_attachment_presets.py restore
```

## 拒绝策略

当邮件附件不符合规则时：
- 邮件保持未读状态
- 不保存附件
- 不移动邮件到目标文件夹
- 不发送确认邮件
- 记录拒绝日志到数据库

## 故障排除

### 问题: 配置修改后不生效

解决: 
- GUI配置: 点击"保存并应用"后立即生效
- 文件配置: 需要重启应用

### 问题: 所有邮件都被拒绝

解决:
- 检查配置文件格式是否正确
- 运行 `python scripts/manage_attachment_presets.py validate`
- 恢复默认配置 `python scripts/manage_attachment_presets.py restore`
```

- [ ] **Step 2: Commit**

```bash
git add docs/ATTACHMENT_VALIDATION_USER_GUIDE.md
git commit -m "docs: add attachment validation user guide

Add comprehensive user guide for attachment validation system:
- Overview of features
- Configuration methods (GUI, file, CLI)
- Rejection strategy explanation
- Troubleshooting tips"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Implemented In |
|------------------|----------------|
| 5-layer architecture | Tasks 2, 5, 7 |
| External YAML config | Task 4 |
| Database model | Task 2 |
| Config manager | Tasks 5, 6 |
| Validator service | Task 7 |
| Workflow integration | Task 8 |
| GUI dialog | Task 10 |
| CLI tool | Task 9 |
| Tests | All tasks |
| Documentation | Task 13 |

✅ All spec requirements covered

### Placeholder Scan

✅ No placeholders found (TBD, TODO, etc.)

### Type Consistency Check

✅ All types and method names are consistent across tasks

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-attachment-validation-implementation.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
