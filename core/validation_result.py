# core/validation_result.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ValidationResult:
    """Result of attachment validation"""
    is_valid: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)