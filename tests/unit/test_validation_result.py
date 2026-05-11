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